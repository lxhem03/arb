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
from pyrogram.errors import FloodWait
from pyrogram.types import InputMediaDocument, Message
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from plugins.antinsfw import check_anti_nsfw
from helper.utils import progress_for_pyrogram, humanbytes, convert
from helper.database import codeflixbots
from config import Config

# logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
renaming_operations = {}

# regex patterns
SEASON_EPISODE_PATTERNS = [
    (re.compile(r'S(\d+)(?:E|EP)(\d+)'), ('season', 'episode')),
    (re.compile(r'Season\s*(\d+)\sEpisode\s(\d+)', re.IGNORECASE), ('season', 'episode')),
    (re.compile(r'\bE(\d{1,3})\b'), (None, 'episode'))
]

QUALITY_PATTERNS = [
    (re.compile(r'\b(\d{3,4}[pi])\b', re.IGNORECASE), lambda m: m.group(1)),
    (re.compile(r'\b(4k|2160p)\b', re.IGNORECASE), lambda m: "4k"),
    (re.compile(r'\b(2k|1440p)\b', re.IGNORECASE), lambda m: "2k")
]

# helper functions

def extract_season_episode(filename):
    for pattern, (season_group, episode_group) in SEASON_EPISODE_PATTERNS:
        match = pattern.search(filename)
        if match:
            groups = match.groups()
            season = groups[0] if season_group else None
            episode = groups[1] if episode_group and len(groups) > 1 else groups[0]
            return season, episode
    return None, None

async def cmd_exec(cmd: list):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode(), stderr.decode()

async def get_media_quality(path):
    try:
        stdout, stderr = await cmd_exec([
            "ffprobe", "-hide_banner", "-loglevel", "error", "-print_format", "json", "-show_format", "-show_streams", path
        ])
        if stderr:
            logger.warning(f'ffprobe stderr: {stderr}')
        ffresult = json.loads(stdout)
        for stream in ffresult.get("streams", []):
            if stream.get("codec_type") == "video":
                height = stream.get("height")
                if height:
                    return f"{int(height)}p"
    except Exception as e:
        logger.error(f'Error detecting quality: {e}')
    return "Unknown"

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
        raise RuntimeError("FFmpeg not found")

    metadata = {
        'title': await codeflixbots.get_title(user_id),
        'artist': await codeflixbots.get_artist(user_id),
        'author': await codeflixbots.get_author(user_id),
        'video_title': await codeflixbots.get_video(user_id),
        'audio_title': await codeflixbots.get_audio(user_id),
        'subtitle': await codeflixbots.get_subtitle(user_id)
    }

    cmd = [ffmpeg, '-i', input_path, '-map', '0', '-c', 'copy']
    for key, value in metadata.items():
        if value:
            if key.startswith('video_'):
                cmd += ['-metadata:s:v', f'title={value}']
            elif key.startswith('audio_'):
                cmd += ['-metadata:s:a', f'title={value}']
            elif key.startswith('sub'):
                cmd += ['-metadata:s:s', f'title={value}']
            else:
                cmd += ['-metadata', f'{key}={value}']
        else:
            if key.startswith('video_'):
                cmd += ['-metadata:s:v', 'title=']
            elif key.startswith('audio_'):
                cmd += ['-metadata:s:a', 'title=']
            elif key.startswith('sub'):
                cmd += ['-metadata:s:s', 'title=']
            else:
                cmd += ['-metadata', f'{key}=']

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

    media_type = None
    file_id = None
    file_name = "media"
    file_size = 0

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "document"
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

    if file_id in renaming_operations and (datetime.now() - renaming_operations[file_id]).seconds < 10:
        return
    renaming_operations[file_id] = datetime.now()

    download_path = metadata_path = file_path = thumb_path = None

    try:
        ext = os.path.splitext(file_name)[1] or '.mp4'
        new_filename = f"temp{ext}"
        download_path = f"downloads/{new_filename}"

        os.makedirs("downloads", exist_ok=True)
        msg = await message.reply_text("**Downloading...**")

        file_path = await client.download_media(
            message,
            file_name=download_path,
            progress=progress_for_pyrogram,
            progress_args=("Downloading...", msg, time.time())
        )

        season, episode = extract_season_episode(file_name)
        quality = await get_media_quality(file_path)

        replacements = {
            '{season}': season or '1',
            '{episode}': episode or '01',
            '{quality}': quality,
            'Season': season or '1',
            'Episode': episode or '01',
            'QUALITY': quality
        }

        for placeholder, value in replacements.items():
            format_template = format_template.replace(placeholder, value)

        new_filename = f"{format_template}{ext}"
        metadata_path = f"metadata/{new_filename}"
        os.makedirs("metadata", exist_ok=True)

        await msg.edit("**Processing metadata...**")
        await add_metadata(file_path, metadata_path, user_id)
        file_path = metadata_path

        caption = await codeflixbots.get_caption(message.chat.id) or f"**{new_filename}**"
        thumb = await codeflixbots.get_thumbnail(message.chat.id)
        thumb_path = None

        if thumb:
            thumb_path = await client.download_media(thumb)
        elif media_type == "video" and getattr(message.video, 'thumbs', None):
            thumb_path = await client.download_media(message.video.thumbs[0].file_id)
        thumb_path = await process_thumbnail(thumb_path)

        await msg.edit("**Uploading...**")
        upload_args = {
            "caption": caption,
            "thumb": thumb_path,
            "progress": progress_for_pyrogram,
            "progress_args": ("Uploading...", msg, time.time())
        }

        if media_type == "video":
            await client.send_video(message.chat.id, file_path, duration=getattr(message.video, 'duration', 0), **upload_args)
        elif media_type == "audio":
            await client.send_audio(message.chat.id, file_path, **upload_args)
        else:
            await client.send_document(message.chat.id, file_path, **upload_args)

        await msg.delete()

    except Exception as e:
        logger.error(f"Processing error: {e}")
        await message.reply_text(f"Error: {str(e)}")

    finally:
        await cleanup_files(download_path, metadata_path, thumb_path)
        renaming_operations.pop(file_id, None)
