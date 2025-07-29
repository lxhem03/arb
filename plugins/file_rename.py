# --- unchanged imports ---
import os
import re
import time
import shutil
import asyncio
import logging
from datetime import datetime
from PIL import Image
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InputMediaDocument, Message
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from plugins.antinsfw import check_anti_nsfw
from helper.utils import progress_for_pyrogram, humanbytes, convert
from helper.database import codeflixbots
from config import Config
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata

# --- logging & global setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
renaming_operations = {}

# --- regex patterns ---
SEASON_EPISODE_PATTERNS = [
    (re.compile(r'S(\d+)(?:E|EP)(\d+)'), ('season', 'episode')),
    (re.compile(r'S(\d+)[\s-]*(?:E|EP)(\d+)'), ('season', 'episode')),
    (re.compile(r'Season\s*(\d+)\s*Episode\s*(\d+)', re.IGNORECASE), ('season', 'episode')),
    (re.compile(r'\[S(\d+)\]\[E(\d+)\]'), ('season', 'episode')),
    (re.compile(r'S(\d+)[^\d]*(\d+)'), ('season', 'episode')),
    (re.compile(r'(?:E|EP|Episode)\s*(\d+)', re.IGNORECASE), (None, 'episode')),
    (re.compile(r'\b(\d+)\b'), (None, 'episode'))
]

QUALITY_PATTERNS = [
    (re.compile(r'\b(\d{3,4}[pi])\b', re.IGNORECASE), lambda m: m.group(1)),
    (re.compile(r'\b(4k|2160p)\b', re.IGNORECASE), lambda m: "4k"),
    (re.compile(r'\b(2k|1440p)\b', re.IGNORECASE), lambda m: "2k"),
    (re.compile(r'\b(HDRip|HDTV)\b', re.IGNORECASE), lambda m: m.group(1)),
    (re.compile(r'\b(4kX264|4kx265)\b', re.IGNORECASE), lambda m: m.group(1)),
    (re.compile(r'\[(\d{3,4}[pi])\]', re.IGNORECASE), lambda m: m.group(1))
]

# --- helper functions ---
def extract_season_episode(filename):
    for pattern, (season_group, episode_group) in SEASON_EPISODE_PATTERNS:
        match = pattern.search(filename)
        if match:
            season = match.group(1) if season_group else None
            episode = match.group(2) if episode_group else match.group(1)
            logger.info(f"Extracted season: {season}, episode: {episode} from {filename}")
            return season, episode
    logger.warning(f"No season/episode pattern matched for {filename}")
    return None, None


async def cmd_exec(cmd: list):
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode(), stderr.decode()

async def get_media_quality(path):
    try:
        result = await cmd_exec([
            "ffprobe", "-hide_banner", "-loglevel", "error", "-print_format", "json",
            "-show_format", "-show_streams", path
        ])
        if res := result[1]:
            logger.warning(f'Media Info FF: {res}')
        ffresult = eval(result[0])
        streams = ffresult.get('streams', [])
        for stream in streams:
            if stream.get('codec_type') == 'video':
                height = int(stream.get('height', 0))
                return f"{480 if height <= 480 else 540 if height <= 540 else 720 if height <= 720 else 1080 if height <= 1080 else 2160 if height <= 2160 else 4320 if height <= 4320 else 8640}p"
    except Exception as e:
        logger.error(f'Media Quality Error: {e}')
    return None
    

async def cleanup_files(*paths):
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.error(f"Error removing {path}: {e}")

async def process_thumbnail(thumb_path):
    if not thumb_path or not os.path.exists(thumb_path):
        return None
    try:
        with Image.open(thumb_path) as img:
            img = img.convert("RGB").resize((320, 320))
            img.save(thumb_path, "JPEG")
        return thumb_path
    except Exception as e:
        logger.error(f"Thumbnail processing failed: {e}")
        await cleanup_files(thumb_path)
        return None

async def add_metadata(input_path, output_path, user_id):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError("FFmpeg not found in PATH")

    metadata = {
        'title': await codeflixbots.get_title(user_id),
        'artist': await codeflixbots.get_artist(user_id),
        'author': await codeflixbots.get_author(user_id),
        'video_title': await codeflixbots.get_video(user_id),
        'audio_title': await codeflixbots.get_audio(user_id),
        'subtitle': await codeflixbots.get_subtitle(user_id)
    }

    cmd = [ffmpeg, '-i', input_path, '-map', '0', '-c', 'copy']

    if metadata['title']:
        cmd += ['-metadata', f'title={metadata["title"]}']
    if metadata['artist']:
        cmd += ['-metadata', f'artist={metadata["artist"]}']
    if metadata['author']:
        cmd += ['-metadata', f'author={metadata["author"]}']
    if metadata['video_title']:
        cmd += ['-metadata:s:v', f'title={metadata["video_title"]}']
    if metadata['audio_title']:
        cmd += ['-metadata:s:a', f'title={metadata["audio_title"]}']
    if metadata['subtitle']:
        cmd += ['-metadata:s:s', f'title={metadata["subtitle"]}']

    cmd += ['-loglevel', 'error', output_path]

    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {stderr.decode()}")

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    format_template = await codeflixbots.get_format_template(user_id)
    if not format_template:
        return await message.reply_text("Please set a rename format using /autorename")

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        file_size = message.document.file_size
        media_type = "document"
    elif message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or "video"
        file_size = message.video.file_size
        media_type = "video"
    elif message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name or "audio"
        file_size = message.audio.file_size
        media_type = "audio"
    else:
        return await message.reply_text("Unsupported file type")

    if await check_anti_nsfw(file_name, message):
        return await message.reply_text("NSFW content detected")

    if file_id in renaming_operations:
        if (datetime.now() - renaming_operations[file_id]).seconds < 10:
            return
    renaming_operations[file_id] = datetime.now()

    try:
        season, episode = extract_season_episode(file_name)
        quality = await get_media_quality(file_path) or "Still failed"

        replacements = {
            '{season}': season or 'XX',
            '{episode}': episode or 'XX',
            '{quality}': quality,
            'Season': season or 'XX',
            'Episode': episode or 'XX',
            'QUALITY': quality
        }

        for placeholder, value in replacements.items():
            format_template = format_template.replace(placeholder, value)

        ext = os.path.splitext(file_name)[1] or ('.mp4' if media_type == 'video' else '.mp3')
        new_filename = f"{format_template}{ext}"
        download_path = f"downloads/{new_filename}"
        metadata_path = f"metadata/{new_filename}"

        os.makedirs(os.path.dirname(download_path), exist_ok=True)
        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)

        msg = await message.reply_text("**Downloading...**")
        try:
            file_path = await client.download_media(
                message,
                file_name=download_path,
                progress=progress_for_pyrogram,
                progress_args=("Downloading...", msg, time.time())
            )
        except Exception as e:
            await msg.edit(f"Download failed: {e}")
            raise

        await msg.edit("**Processing metadata...**")
        try:
            await add_metadata(file_path, metadata_path, user_id)
            file_path = metadata_path
        except Exception as e:
            await msg.edit(f"Metadata processing failed: {e}")
            raise

        await msg.edit("**Preparing upload...**")
        caption = await codeflixbots.get_caption(message.chat.id) or f"**{new_filename}**"
        thumb = await codeflixbots.get_thumbnail(message.chat.id)
        thumb_path = None

        if thumb:
            thumb_path = await client.download_media(thumb)
        elif media_type == "video" and message.video.thumbs:
            thumb_path = await client.download_media(message.video.thumbs[0].file_id)
        
        thumb_path = await process_thumbnail(thumb_path)

        await msg.edit("**Uploading...**")
        try:
            upload_params = {
                'chat_id': message.chat.id,
                'caption': caption,
                'thumb': thumb_path,
                'progress': progress_for_pyrogram,
                'progress_args': ("Uploading...", msg, time.time())
            }

            if media_type == "video":
                upload_params['duration'] = message.video.duration if message.video and message.video.duration else None
                await client.send_video(video=file_path, **upload_params)
            elif media_type == "document":
                await client.send_document(document=file_path, **upload_params)
            elif media_type == "audio":
                await client.send_audio(audio=file_path, **upload_params)

            await msg.delete()
        except Exception as e:
            await msg.edit(f"Upload failed: {e}")
            raise

    except Exception as e:
        logger.error(f"Processing error: {e}")
        await message.reply_text(f"Error: {str(e)}")
    finally:
        await cleanup_files(download_path, metadata_path, thumb_path)
        renaming_operations.pop(file_id, None)
