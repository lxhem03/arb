import os
import re
import time
import shutil
import asyncio
import json
import logging
from datetime import datetime
from PIL import Image
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, FileReferenceExpired
from pyrogram.types import Message
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from plugins.antinsfw import check_anti_nsfw
from helper.utils import progress_for_pyrogram, humanbytes
from helper.database import codeflixbots
from config import Config

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

renaming_operations = {}
user_queues = {}

# Season/Episode patterns
SEASON_EPISODE_PATTERNS = [

    (re.compile(r'\b[Ss](\d{1,2})[Ee](\d{1,3})\b'),
     ('season', 'episode')),

    (re.compile(r'\b[Ss](\d{1,2})[._\s-]+(\d{1,3})\b'),
     ('season', 'episode')),

    (re.compile(
        r'\b(\d{1,2})(?:st|nd|rd|th)[._\s]+Season[._\s]+(\d{1,3})\b',
        re.IGNORECASE
    ), ('season', 'episode')),

    (re.compile(
        r'\b(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)'
        r'[._\s]+Season[._\s]+(\d{1,3})\b',
        re.IGNORECASE
    ), ('season_word', 'episode')),

    (re.compile(r'(?<!\d)[._\s]+(\d{1,3})[._\s]+(?!\d)'),
     (None, 'episode')),
]
WORD_TO_SEASON = {k.lower(): v for k, v in {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10
}.items()}

QUALITY_PATTERNS = [
    (re.compile(r'\b(2160p|4k)\b', re.IGNORECASE), lambda m: '2160p'),
    (re.compile(r'\b(1440p|2k)\b', re.IGNORECASE), lambda m: '1440p'),
    (re.compile(r'\b1080p\b', re.IGNORECASE), lambda m: '1080p'),
    (re.compile(r'\b720p\b', re.IGNORECASE), lambda m: '720p'),
    (re.compile(r'\b480p\b', re.IGNORECASE), lambda m: '480p'),
    (re.compile(r'\b360p\b', re.IGNORECASE), lambda m: '360p'),
    (re.compile(r'\b240p\b', re.IGNORECASE), lambda m: '240p'),
    (re.compile(r'\b144p\b', re.IGNORECASE), lambda m: '144p'),
    (re.compile(r'\bUHD\b', re.IGNORECASE), lambda m: '2160p'),
    (re.compile(r'\bFHD\b', re.IGNORECASE), lambda m: '1080p'),
    (re.compile(r'\bHD\b', re.IGNORECASE), lambda m: '720p'),
    (re.compile(r'\bSD\b', re.IGNORECASE), lambda m: '480p'),
    (re.compile(r'\b(\d{3,4})[pP]\b'), lambda m: f"{m.group(1)}p"),
]

def extract_season_episode(filename):
    season = episode = None
    for pattern, fields in SEASON_EPISODE_PATTERNS:
        match = pattern.search(filename)
        if not match:
            continue
        groups = match.groups()
        for idx, field in enumerate(fields):
            if not groups[idx]:
                continue
            if field == "season":
                season = int(groups[idx])
            elif field == "episode":
                episode = int(groups[idx])
            elif field == "season_word":
                season = WORD_TO_SEASON.get(groups[idx].lower())
        if season is not None or episode is not None:
            break
    return season, episode

async def cmd_exec(cmd: list):
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode().strip(), stderr.decode().strip()

async def get_media_quality(path):
    try:
        stdout, _ = await cmd_exec([
            "ffprobe", "-hide_banner", "-loglevel", "error",
            "-print_format", "json", "-show_streams", path
        ])
        data = json.loads(stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                height = stream.get("height")
                if height:
                    return f"{height}p"
    except Exception as e:
        logger.error(f"Error detecting quality: {e}")
    return "Unknown"

async def cleanup_files(*paths):
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.error(f"Error removing {path}: {e}")

async def process_thumbnail(thumb_path):
    if not thumb_path or not os.path.exists(thumb_path):
        return None
    try:
        with Image.open(thumb_path) as img:
            img = img.convert("RGB").resize((320, 320), Image.LANCZOS)
            img.save(thumb_path, "JPEG", quality=95)
        return thumb_path
    except Exception as e:
        logger.error(f"Thumbnail processing failed: {e}")
        await cleanup_files(thumb_path)
        return None

# Safe download with FileReferenceExpired handling
async def safe_download_media(client, message, file_name):
    while True:
        try:
            return await client.download_media(
                message=message,
                file_name=file_name,
                progress=progress_for_pyrogram,
                progress_args=("Downloading...", message, time.time())
            )
        except FileReferenceExpired:
            logger.warning(f"File reference expired for {message.id}, refreshing...")
            # Refresh message to get new file_reference
            message = await client.get_messages(message.chat.id, message.id)
        except FloodWait as e:
            logger.warning(f"FloodWait: {e.x} seconds")
            await asyncio.sleep(e.x)
        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise

# Metadata function (already fixed in previous messages)
async def add_metadata(input_path, output_path, user_id):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError("FFmpeg not found")

    metadata_enabled = await codeflixbots.get_metadata(user_id)
    if not metadata_enabled:
        cmd = [ffmpeg, '-i', input_path, '-map', '0', '-c', 'copy', '-loglevel', 'error', output_path]
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.wait()
        if proc.returncode != 0:
            raise RuntimeError("Stream copy failed")
        return

    title = await codeflixbots.get_title(user_id)
    author = await codeflixbots.get_author(user_id)
    artist = await codeflixbots.get_artist(user_id)
    video = await codeflixbots.get_video(user_id)
    audio = await codeflixbots.get_audio(user_id)
    subtitle = await codeflixbots.get_subtitle(user_id)
    remove_audio = await codeflixbots.get_remove_audio_metadata(user_id)
    remove_subtitle = await codeflixbots.get_remove_subtitle_metadata(user_id)

    cmd = [ffmpeg, '-i', input_path, '-map', '0', '-c', 'copy']

    if title: cmd += ['-metadata', f'title={title}']
    if author: cmd += ['-metadata', f'author={author}']
    if artist: cmd += ['-metadata', f'artist={artist}']
    if video: cmd += ['-metadata:s:v', f'title={video}']
    if audio: cmd += ['-metadata:s:a', f'title={audio}']
    elif remove_audio: cmd += ['-metadata:s:a', 'title=']
    if subtitle: cmd += ['-metadata:s:s', f'title={subtitle}']
    elif remove_subtitle: cmd += ['-metadata:s:s', 'title=']

    cmd += ['-loglevel', 'error', output_path]
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Metadata processing failed")

# Worker
async def user_queue_worker(user_id):
    queue = user_queues[user_id]['queue']
    while True:
        message, client = await queue.get()
        try:
            await process_auto_rename_files(client, message)
        except Exception as e:
            logger.error(f"Error in worker for user {user_id}: {e}", exc_info=True)
            try:
                await message.reply_text(f"**Error processing file:** `{str(e)}`")
            except:
                pass
        finally:
            queue.task_done()

# Main processing function
async def process_auto_rename_files(client, message: Message):
    user_id = message.from_user.id
    format_template = await codeflixbots.get_format_template(user_id)
    if not format_template:
        return await message.reply_text("⚠️ Please set a rename format using /autorename")

    # Determine media
    media = message.document or message.video or message.audio
    if not media:
        return await message.reply_text("❌ Unsupported file type")

    file_name = getattr(media, 'file_name', 'Unknown')
    ext = os.path.splitext(file_name)[1] or '.mp4'

    if await check_anti_nsfw(file_name, message):
        return await message.reply_text("🚫 NSFW content detected and blocked.")

    file_id = media.file_id
    if file_id in renaming_operations and (datetime.now() - renaming_operations[file_id]).seconds < 10:
        return await message.reply_text("⏳ This file is already being processed.")

    renaming_operations[file_id] = datetime.now()

    download_path = metadata_path = thumb_path = None
    status_msg = await message.reply_text("⬇️ **Downloading...**")

    try:
        os.makedirs("downloads", exist_ok=True)
        os.makedirs("metadata", exist_ok=True)

        download_path = f"downloads/{user_id}_{int(time.time())}{ext}"

        # Safe download
        file_path = await safe_download_media(client, message, download_path)
        if not file_path:
            raise Exception("Download failed")

        await status_msg.edit_text("🔍 **Detecting season/episode & quality...**")
        season, episode = extract_season_episode(file_name)
        quality = await get_media_quality(file_path)

        # Safe replacements (convert to str, fallback to empty)
        replacements = {
            '{season}': str(season or ''),
            '{episode}': str(episode or '').zfill(2),
            '{quality}': str(quality or ''),
            'Season': str(season or ''),
            'Episode': str(episode or '').zfill(2),
            'QUALITY': str(quality or '')
        }

        new_name_base = format_template
        for placeholder, value in replacements.items():
            new_name_base = new_name_base.replace(placeholder, value)

        new_filename = f"{new_name_base}{ext}"
        metadata_path = f"metadata/{user_id}_{int(time.time())}_{new_filename}"

        await status_msg.edit_text("🖊️ **Applying metadata...**")
        await add_metadata(file_path, metadata_path, user_id)
        file_path = metadata_path

        caption = await codeflixbots.get_caption(user_id) or f"**{new_filename}**"

        # Thumbnail
        custom_thumb = await codeflixbots.get_thumbnail(user_id)
        if custom_thumb:
            thumb_path = await safe_download_media(client, custom_thumb, f"thumbs/{user_id}.jpg")
        elif hasattr(message.video, 'thumbs') and message.video.thumbs:
            thumb_path = await safe_download_media(client, message.video.thumbs[0], f"thumbs/temp_{user_id}.jpg")
        thumb_path = await process_thumbnail(thumb_path)

        await status_msg.edit_text("⬆️ **Uploading...**")

        upload_kwargs = {
            "caption": caption,
            "thumb": thumb_path,
            "progress": progress_for_pyrogram,
            "progress_args": ("Uploading...", status_msg, time.time())
        }

        if message.video:
            await client.send_video(message.chat.id, file_path, **upload_kwargs)
        elif message.audio:
            await client.send_audio(message.chat.id, file_path, **upload_kwargs)
        else:
            await client.send_document(message.chat.id, file_path, **upload_kwargs)

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Processing failed for user {user_id}: {e}", exc_info=True)
        error_text = str(e)
        if "FILE_REFERENCE_EXPIRED" in error_text:
            error_text = "File is too old or forwarded too many times. Please send it again."
        await message.reply_text(f"❌ **Error:** `{error_text}`")

    finally:
        await cleanup_files(download_path, metadata_path, thumb_path)
        renaming_operations.pop(file_id, None)

# Queue handler
@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def queue_auto_rename_files(client, message):
    user_id = message.from_user.id
    if user_id not in user_queues:
        user_queues[user_id] = {
            'queue': asyncio.Queue(),
            'worker': asyncio.create_task(user_queue_worker(user_id))
        }
    queue = user_queues[user_id]['queue']
    await queue.put((message, client))
    position = queue.qsize()
    text = "Starting processing now!" if position == 1 else f"Added to queue. Position: **{position}**"
    await message.reply_text(text)
