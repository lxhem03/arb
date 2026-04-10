#fv2-0 — queue fix, cancel button, cancel commands, session name support
import os, re, time, shutil, asyncio, json, logging
from datetime import datetime
from PIL import Image
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, FileReferenceExpired
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from plugins.antinsfw import check_anti_nsfw
from helper.utils import progress_for_pyrogram, humanbytes
from helper.database import codeflixbots
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─────────────────────────── shared state ────────────────────────────────────
renaming_operations = {}   # file_id → datetime (dedup guard)

# Per-user queue state:
# user_queues[user_id] = {
#   'queue': asyncio.Queue of (message, client),
#   'worker': asyncio.Task,
#   'cancel_current': asyncio.Event
# }
user_queues = {}

# ─────────────────────────── season/episode/quality ──────────────────────────
SEASON_EPISODE_PATTERNS = [
    (re.compile(r'[Ss](\d{1,2})[Ee](\d{1,3})'),          ('season', 'episode')),
    (re.compile(r'[Ss](\d{1,2})[._\s]+(\d{1,3})'),        ('season', 'episode')),
    (re.compile(r'(\d{1,2})(?:st|nd|rd|th)[._\s]+Season[._\s]+(\d{1,3})', re.IGNORECASE), ('season', 'episode')),
    (re.compile(r'(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)[._\s]+Season[._\s]+(\d{1,3})', re.IGNORECASE), ('season_word', 'episode')),
]

WORD_TO_SEASON = {k.lower(): v for k, v in {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10
}.items()}


def extract_season_episode(filename):
    season = episode = None
    name = re.sub(r'[\.\s]+', '_', filename)
    for pattern, fields in SEASON_EPISODE_PATTERNS:
        match = pattern.search(name)
        if not match:
            continue
        groups = match.groups()
        for idx, field in enumerate(fields):
            if idx >= len(groups) or not field:
                continue
            value = groups[idx]
            if not value:
                continue
            if field == "season":
                season = int(value)
            elif field == "episode":
                episode = int(value)
            elif field == "season_word":
                season = WORD_TO_SEASON.get(value.lower())
        if season is not None or episode is not None:
            return season, episode
    m = re.search(r'(?<!\d)[_](\d{1,3})(?!\d)', name)
    if m:
        episode = int(m.group(1))
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

    title    = await codeflixbots.get_title(user_id)
    author   = await codeflixbots.get_author(user_id)
    artist   = await codeflixbots.get_artist(user_id)
    video    = await codeflixbots.get_video(user_id)
    audio    = await codeflixbots.get_audio(user_id)
    subtitle = await codeflixbots.get_subtitle(user_id)
    remove_audio    = await codeflixbots.get_remove_audio_metadata(user_id)
    remove_subtitle = await codeflixbots.get_remove_subtitle_metadata(user_id)

    cmd = [ffmpeg, '-i', input_path, '-map', '0', '-c', 'copy']
    if title:    cmd += ['-metadata', f'title={title}']
    if author:   cmd += ['-metadata', f'author={author}']
    if artist:   cmd += ['-metadata', f'artist={artist}']
    if video:    cmd += ['-metadata:s:v', f'title={video}']
    if audio:    cmd += ['-metadata:s:a', f'title={audio}']
    elif remove_audio:    cmd += ['-metadata:s:a', 'title=']
    if subtitle: cmd += ['-metadata:s:s', f'title={subtitle}']
    elif remove_subtitle: cmd += ['-metadata:s:s', 'title=']
    cmd += ['-loglevel', 'error', output_path]

    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Metadata processing failed")


# ─────────────────────────── cancel helpers ──────────────────────────────────
def _get_or_create_user_queue(user_id):
    if user_id not in user_queues:
        cancel_event = asyncio.Event()
        q = asyncio.Queue()
        user_queues[user_id] = {
            'queue': q,
            'worker': None,
            'cancel_current': cancel_event,
        }
        task = asyncio.create_task(user_queue_worker(user_id))
        user_queues[user_id]['worker'] = task
    return user_queues[user_id]


def _signal_cancel(user_id):
    if user_id in user_queues:
        user_queues[user_id]['cancel_current'].set()


# ─────────────────────────── upload helper ───────────────────────────────────
async def upload_with_retry(client, chat_id, file_path, caption, thumb, status_msg, cancel_event=None):
    max_retries = 4

    for attempt in range(1, max_retries + 1):
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError()

        try:
            last_progress_time = [time.time()]

            async def progress(current, total):
                if cancel_event and cancel_event.is_set():
                    raise asyncio.CancelledError()
                now = time.time()
                if now - last_progress_time[0] < 3:
                    return
                last_progress_time[0] = now
                percent = current * 100 / total
                text = f"⬆️ **Uploading...** {percent:.1f}%"
                if percent >= 100:
                    text = "📤 **Upload complete. Waiting for Telegram processing...**"
                try:
                    await status_msg.edit_text(
                        text,
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_task_{chat_id}")
                        ]])
                    )
                except Exception:
                    pass

            await asyncio.wait_for(
                client.send_document(
                    chat_id, file_path,
                    caption=caption, thumb=thumb,
                    progress=progress
                ),
                timeout=900
            )
            try:
                await status_msg.delete()
            except Exception:
                pass
            return True

        except FloodWait as e:
            wait_time = e.value + 5
            try:
                await status_msg.edit_text(f"⏳ **FloodWait detected. Waiting {wait_time}s...**")
            except Exception:
                pass
            await asyncio.sleep(wait_time)

        except asyncio.TimeoutError:
            if attempt == max_retries:
                raise Exception("Upload timeout after multiple retries.")
            try:
                await status_msg.edit_text(f"⚠️ **Upload stuck. Retrying... ({attempt}/{max_retries})**")
            except Exception:
                pass
            await asyncio.sleep(5)

        except asyncio.CancelledError:
            raise

        except Exception:
            if attempt == max_retries:
                raise
            try:
                await status_msg.edit_text(f"⚠️ **Upload failed. Retrying... ({attempt}/{max_retries})**")
            except Exception:
                pass
            await asyncio.sleep(5)

    return False


async def safe_download_media(client, message, file_name, status_msg=None, cancel_event=None):
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError()
        try:
            progress_args = None
            if status_msg:
                progress_args = ("Downloading...", status_msg, time.time())

            file_path = await client.download_media(
                message=message,
                file_name=file_name,
                progress=progress_for_pyrogram if status_msg else None,
                progress_args=progress_args
            )

            if file_path and os.path.getsize(file_path) == 0:
                logger.warning(f"Downloaded file is 0KB on attempt {attempt} — treating as failure")
                os.remove(file_path)
                raise Exception("Empty file downloaded")

            if file_path:
                logger.info(f"Download successful on attempt {attempt}: {file_path}")
                return file_path

        except asyncio.CancelledError:
            raise

        except FileReferenceExpired:
            logger.warning(f"FileReferenceExpired on attempt {attempt}/{max_retries} — refreshing message")
            try:
                message = await client.get_messages(message.chat.id, message.id)
            except Exception as refresh_error:
                logger.error(f"Failed to refresh message: {refresh_error}")
                if attempt == max_retries:
                    raise
            await asyncio.sleep(attempt * 2)

        except FloodWait as e:
            logger.warning(f"FloodWait {e.value}s on attempt {attempt} — sleeping")
            await asyncio.sleep(e.value + 5)

        except Exception as e:
            logger.error(f"Download error on attempt {attempt}: {type(e).__name__}: {e}")
            if attempt == max_retries:
                raise
            await asyncio.sleep(attempt * 3)

    logger.error(f"Download permanently failed after {max_retries} attempts for message {message.id}")
    return None


# ─────────────────────────── core rename logic ───────────────────────────────
async def process_auto_rename_files(client, message: Message, cancel_event: asyncio.Event):
    user_id = message.from_user.id
    format_template = await codeflixbots.get_format_template(user_id)
    if not format_template:
        return await message.reply_text("⚠️ Please set a rename format using /autorename")

    media = message.document or message.video or message.audio
    if not media:
        return await message.reply_text("❌ Unsupported file type")

    original_file_name = getattr(media, 'file_name', 'Unknown.file')
    ext = os.path.splitext(original_file_name)[1] or '.mkv'

    if await check_anti_nsfw(original_file_name, message):
        return await message.reply_text("🚫 NSFW content detected and blocked.")

    file_id = media.file_id
    if file_id in renaming_operations and (datetime.now() - renaming_operations[file_id]).seconds < 10:
        return await message.reply_text("⏳ This file is already being processed.")

    renaming_operations[file_id] = datetime.now()

    download_path = metadata_path = thumb_path = None
    status_msg = await message.reply_text(
        "⬇️ **Downloading... 0%**",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_task_{user_id}")
        ]])
    )

    try:
        os.makedirs("downloads", exist_ok=True)
        os.makedirs("metadata",  exist_ok=True)
        os.makedirs("thumbs",    exist_ok=True)

        temp_download = f"downloads/{user_id}_{int(time.time())}{ext}"

        file_path = await safe_download_media(
            client=client,
            message=message,
            file_name=temp_download,
            status_msg=status_msg,
            cancel_event=cancel_event
        )

        if not file_path or (os.path.exists(file_path) and os.path.getsize(file_path) == 0):
            raise Exception(
                "File could not be downloaded — it may be too old, heavily forwarded, or restricted. "
                "Please send the file directly (not forwarded)."
            )

        download_path = file_path

        if cancel_event.is_set():
            raise asyncio.CancelledError()

        await status_msg.edit_text(
            "🔍 **Analyzing filename & quality...**",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_task_{user_id}")
            ]])
        )

        season, episode = extract_season_episode(original_file_name)
        quality = await get_media_quality(file_path)

        detected_season  = season  or 1
        detected_episode = episode or 1

        replacements = {
            '{season}':  str(detected_season),
            '{episode}': str(detected_episode).zfill(2),
            '{quality}': str(quality or 'Unknown'),
        }

        new_name_base = format_template
        for placeholder, value in replacements.items():
            new_name_base = new_name_base.replace(placeholder, value)

        final_filename = f"{new_name_base}{ext}"
        metadata_path  = f"metadata/{final_filename}"

        if cancel_event.is_set():
            raise asyncio.CancelledError()

        await status_msg.edit_text(
            "🖊️ **Applying metadata...**",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_task_{user_id}")
            ]])
        )
        await add_metadata(file_path, metadata_path, user_id)

        if cancel_event.is_set():
            raise asyncio.CancelledError()

        caption = await codeflixbots.get_caption(user_id) or f"**{final_filename}**"

        custom_thumb = await codeflixbots.get_thumbnail(user_id)
        if custom_thumb:
            thumb_path = await safe_download_media(
                client, custom_thumb,
                f"thumbs/custom_{user_id}.jpg",
                cancel_event=cancel_event
            )
        elif message.video and getattr(message.video, 'thumbs', None):
            thumb_path = await safe_download_media(
                client, message.video.thumbs[0],
                f"thumbs/temp_{user_id}.jpg",
                cancel_event=cancel_event
            )
        thumb_path = await process_thumbnail(thumb_path)

        await status_msg.edit_text(
            "⬆️ **Uploading...**",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_task_{user_id}")
            ]])
        )

        await upload_with_retry(
            client=client,
            chat_id=message.chat.id,
            file_path=metadata_path,
            caption=caption,
            thumb=thumb_path,
            status_msg=status_msg,
            cancel_event=cancel_event
        )

    except asyncio.CancelledError:
        logger.info(f"Task cancelled for user {user_id}")
        try:
            await status_msg.edit_text("🚫 **Task cancelled.**", reply_markup=None)
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Processing failed for user {user_id}: {e}", exc_info=True)
        error_msg = str(e)
        if "FILE_REFERENCE_EXPIRED" in error_msg:
            error_msg = "File is too old/forwarded. Please send again."
        try:
            await status_msg.edit_text(f"❌ **Error:** `{error_msg}`", reply_markup=None)
        except Exception:
            await message.reply_text(f"❌ **Error:** `{error_msg}`")

    finally:
        await cleanup_files(download_path, metadata_path, thumb_path)
        renaming_operations.pop(file_id, None)
        # Reset so the next task in the queue starts cleanly
        cancel_event.clear()


# ─────────────────────────── worker ──────────────────────────────────────────
async def user_queue_worker(user_id):
    """One worker per user — processes files strictly one at a time."""
    entry  = user_queues[user_id]
    queue  = entry['queue']
    while True:
        message, client = await queue.get()
        cancel_event = entry['cancel_current']
        cancel_event.clear()  # fresh start for each task
        try:
            await process_auto_rename_files(client, message, cancel_event)
        except Exception as e:
            logger.error(f"Error in worker for user {user_id}: {e}", exc_info=True)
            try:
                await message.reply_text(f"**Error processing file:** `{str(e)}`")
            except Exception:
                pass
        finally:
            queue.task_done()


# ─────────────────────────── queue handler ───────────────────────────────────
@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def queue_auto_rename_files(client, message):
    user_id = message.from_user.id
    entry   = _get_or_create_user_queue(user_id)
    queue   = entry['queue']
    await queue.put((message, client))
    position = queue.qsize()
    text = (
        "▶️ **Starting your file now!**"
        if position == 1
        else f"📋 **Added to queue.** Position: **{position}**"
    )
    await message.reply_text(text)


# ─────────────────────────── cancel button (inline) ──────────────────────────
@Client.on_callback_query(filters.regex(r"^cancel_task_(\d+)$"))
async def cancel_task_callback(client, query: CallbackQuery):
    """Cancel button under the progress bar — only the task owner can cancel."""
    requester_id  = query.from_user.id
    target_user_id = int(query.matches[0].group(1))

    if requester_id != target_user_id:
        return await query.answer("⛔ You can only cancel your own tasks.", show_alert=True)

    _signal_cancel(target_user_id)
    await query.answer("✅ Cancellation requested.", show_alert=False)


# ─────────────────────────── /cancel command ─────────────────────────────────
@Client.on_message(filters.private & filters.command("cancel"))
async def cancel_command(client, message: Message):
    """
    /cancel       — cancel only your currently running task
    /cancel all   — cancel current task AND clear your entire queue
    """
    user_id = message.from_user.id
    args    = message.command[1:]

    if user_id not in user_queues:
        return await message.reply_text("📭 You have no active tasks.")

    entry = user_queues[user_id]

    if args and args[0].lower() == "all":
        q = entry['queue']
        drained = 0
        while not q.empty():
            try:
                q.get_nowait()
                q.task_done()
                drained += 1
            except asyncio.QueueEmpty:
                break
        _signal_cancel(user_id)
        return await message.reply_text(
            f"🗑️ **Cancelled your current task and removed {drained} queued item(s).**"
        )

    # Default: cancel only current task
    _signal_cancel(user_id)
    await message.reply_text("🚫 **Cancellation requested for your current task.**\n"
                             "The next task in your queue will start automatically.")


# ─────────────────────────── /cancelall command (admin/owner) ────────────────
@Client.on_message(filters.private & filters.command("cancelall") & filters.user(Config.ADMIN))
async def cancel_all_command(client, message: Message):
    """Admin-only: cancel every task from every user in the bot."""
    total_drained = 0
    total_users   = 0

    for uid, entry in list(user_queues.items()):
        q = entry['queue']
        drained = 0
        while not q.empty():
            try:
                q.get_nowait()
                q.task_done()
                drained += 1
            except asyncio.QueueEmpty:
                break
        _signal_cancel(uid)
        if drained:
            total_drained += drained
            total_users   += 1

    await message.reply_text(
        f"✅ **Universal cancel done.**\n"
        f"Cleared **{total_drained}** queued task(s) across **{total_users}** user(s).\n"
        f"All running tasks have been signalled to stop."
    )
