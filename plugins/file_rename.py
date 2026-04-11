#fv2-1 — per-user queue, cancel button/commands, /queue, /cancelall with DM notify
import os, re, time, shutil, asyncio, json, logging
from datetime import datetime
from PIL import Image
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, FileReferenceExpired
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
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

# ══════════════════════════ SHARED STATE ══════════════════════════════════════
# Dedup guard: file_id → datetime
renaming_operations = {}

# Per-user queue:
#   user_queues[user_id] = {
#       'queue':          asyncio.Queue   ← pending (message, client) tuples
#       'worker':         asyncio.Task    ← one long-running worker per user
#       'cancel_current': asyncio.Event   ← set to abort the running task only
#       'active_client':  Client|None     ← the client used in the current task
#   }
user_queues: dict = {}

# ══════════════════════════ SEASON/EPISODE/QUALITY ════════════════════════════
SEASON_EPISODE_PATTERNS = [
    (re.compile(r'[Ss](\d{1,2})[Ee](\d{1,3})'),                               ('season', 'episode')),
    (re.compile(r'[Ss](\d{1,2})[._\s]+(\d{1,3})'),                            ('season', 'episode')),
    (re.compile(r'(\d{1,2})(?:st|nd|rd|th)[._\s]+Season[._\s]+(\d{1,3})',     re.IGNORECASE), ('season', 'episode')),
    (re.compile(r'(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)[._\s]+Season[._\s]+(\d{1,3})', re.IGNORECASE), ('season_word', 'episode')),
]
WORD_TO_SEASON = {k.lower(): v for k, v in {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}.items()}


def extract_season_episode(filename):
    season = episode = None
    name = re.sub(r'[\.\s]+', '_', filename)
    for pattern, fields in SEASON_EPISODE_PATTERNS:
        match = pattern.search(name)
        if not match:
            continue
        for idx, field in enumerate(fields):
            if idx >= len(match.groups()) or not field:
                continue
            value = match.groups()[idx]
            if not value:
                continue
            if field == "season":        season  = int(value)
            elif field == "episode":     episode = int(value)
            elif field == "season_word": season  = WORD_TO_SEASON.get(value.lower())
        if season is not None or episode is not None:
            return season, episode
    m = re.search(r'(?<!\d)[_](\d{1,3})(?!\d)', name)
    if m:
        episode = int(m.group(1))
    return season, episode


async def cmd_exec(cmd: list):
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode().strip(), stderr.decode().strip()


async def get_media_quality(path):
    try:
        stdout, _ = await cmd_exec([
            "ffprobe", "-hide_banner", "-loglevel", "error",
            "-print_format", "json", "-show_streams", path
        ])
        for stream in json.loads(stdout).get("streams", []):
            if stream.get("codec_type") == "video":
                h = stream.get("height")
                if h:
                    return f"{h}p"
    except Exception as e:
        logger.error(f"Quality detection error: {e}")
    return "Unknown"


async def cleanup_files(*paths):
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.error(f"Cleanup error for {path}: {e}")


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

    if not await codeflixbots.get_metadata(user_id):
        cmd = [ffmpeg, '-i', input_path, '-map', '0', '-c', 'copy',
               '-loglevel', 'error', output_path]
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
    rm_audio = await codeflixbots.get_remove_audio_metadata(user_id)
    rm_sub   = await codeflixbots.get_remove_subtitle_metadata(user_id)

    cmd = [ffmpeg, '-i', input_path, '-map', '0', '-c', 'copy']
    if title:    cmd += ['-metadata', f'title={title}']
    if author:   cmd += ['-metadata', f'author={author}']
    if artist:   cmd += ['-metadata', f'artist={artist}']
    if video:    cmd += ['-metadata:s:v', f'title={video}']
    if audio:    cmd += ['-metadata:s:a', f'title={audio}']
    elif rm_audio: cmd += ['-metadata:s:a', 'title=']
    if subtitle: cmd += ['-metadata:s:s', f'title={subtitle}']
    elif rm_sub:   cmd += ['-metadata:s:s', 'title=']
    cmd += ['-loglevel', 'error', output_path]

    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Metadata processing failed")


# ══════════════════════════ CANCEL HELPERS ════════════════════════════════════
def _cancel_button(user_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_task_{user_id}")
    ]])


def _get_or_create_user_queue(user_id):
    if user_id not in user_queues:
        user_queues[user_id] = {
            'queue':          asyncio.Queue(),
            'worker':         None,
            'cancel_current': asyncio.Event(),
            'active_client':  None,
        }
        user_queues[user_id]['worker'] = asyncio.create_task(
            user_queue_worker(user_id)
        )
    return user_queues[user_id]


def _signal_cancel(user_id):
    if user_id in user_queues:
        user_queues[user_id]['cancel_current'].set()


# ══════════════════════════ UPLOAD / DOWNLOAD ════════════════════════════════
async def upload_with_retry(client, chat_id, file_path, caption,
                            thumb, status_msg, cancel_event=None):
    max_retries = 4
    for attempt in range(1, max_retries + 1):
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError()
        try:
            last_t = [time.time()]

            async def progress(current, total):
                if cancel_event and cancel_event.is_set():
                    raise asyncio.CancelledError()
                now = time.time()
                if now - last_t[0] < 3:
                    return
                last_t[0] = now
                pct = current * 100 / total
                txt = (
                    "📤 **Upload complete. Waiting for Telegram...**"
                    if pct >= 100
                    else f"⬆️ **Uploading...** {pct:.1f}%"
                )
                try:
                    await status_msg.edit_text(txt, reply_markup=_cancel_button(chat_id))
                except Exception:
                    pass

            await asyncio.wait_for(
                client.send_document(
                    chat_id, file_path,
                    caption=caption, thumb=thumb, progress=progress
                ),
                timeout=900
            )
            try:
                await status_msg.delete()
            except Exception:
                pass
            return True

        except FloodWait as e:
            await asyncio.sleep(e.value + 5)
        except asyncio.TimeoutError:
            if attempt == max_retries:
                raise Exception("Upload timeout after multiple retries.")
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            raise
        except Exception:
            if attempt == max_retries:
                raise
            await asyncio.sleep(5)
    return False


async def safe_download_media(client, message, file_name,
                              status_msg=None, cancel_event=None):
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError()
        try:
            file_path = await client.download_media(
                message=message,
                file_name=file_name,
                progress=progress_for_pyrogram if status_msg else None,
                progress_args=("Downloading...", status_msg, time.time()) if status_msg else None
            )
            if file_path and os.path.getsize(file_path) == 0:
                os.remove(file_path)
                raise Exception("Empty file downloaded")
            if file_path:
                return file_path
        except asyncio.CancelledError:
            raise
        except FileReferenceExpired:
            try:
                message = await client.get_messages(message.chat.id, message.id)
            except Exception:
                pass
            if attempt == max_retries:
                raise
            await asyncio.sleep(attempt * 2)
        except FloodWait as e:
            await asyncio.sleep(e.value + 5)
        except Exception as e:
            logger.error(f"Download error attempt {attempt}: {e}")
            if attempt == max_retries:
                raise
            await asyncio.sleep(attempt * 3)
    return None


# ══════════════════════════ CORE RENAME LOGIC ════════════════════════════════
async def process_auto_rename_files(client, message: Message,
                                    cancel_event: asyncio.Event):
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
    if file_id in renaming_operations and \
            (datetime.now() - renaming_operations[file_id]).seconds < 10:
        return await message.reply_text("⏳ This file is already being processed.")
    renaming_operations[file_id] = datetime.now()

    download_path = metadata_path = thumb_path = None
    status_msg = await message.reply_text(
        "⬇️ **Downloading... 0%**",
        reply_markup=_cancel_button(user_id)
    )

    try:
        for d in ("downloads", "metadata", "thumbs"):
            os.makedirs(d, exist_ok=True)

        temp_download = f"downloads/{user_id}_{int(time.time())}{ext}"
        file_path = await safe_download_media(
            client, message, temp_download,
            status_msg=status_msg, cancel_event=cancel_event
        )
        if not file_path or (os.path.exists(file_path) and os.path.getsize(file_path) == 0):
            raise Exception(
                "File could not be downloaded — it may be too old, heavily "
                "forwarded, or restricted. Please send the file directly."
            )
        download_path = file_path

        if cancel_event.is_set():
            raise asyncio.CancelledError()

        await status_msg.edit_text(
            "🔍 **Analyzing filename & quality...**",
            reply_markup=_cancel_button(user_id)
        )

        season, episode = extract_season_episode(original_file_name)
        quality         = await get_media_quality(file_path)

        replacements = {
            '{season}':  str(season  or 1),
            '{episode}': str(episode or 1).zfill(2),
            '{quality}': str(quality or 'Unknown'),
        }
        new_name_base = format_template
        for ph, val in replacements.items():
            new_name_base = new_name_base.replace(ph, val)

        final_filename = f"{new_name_base}{ext}"
        metadata_path  = f"metadata/{final_filename}"

        if cancel_event.is_set():
            raise asyncio.CancelledError()

        await status_msg.edit_text(
            "🖊️ **Applying metadata...**",
            reply_markup=_cancel_button(user_id)
        )
        await add_metadata(file_path, metadata_path, user_id)

        if cancel_event.is_set():
            raise asyncio.CancelledError()

        caption = await codeflixbots.get_caption(user_id) or f"**{final_filename}**"

        custom_thumb = await codeflixbots.get_thumbnail(user_id)
        if custom_thumb:
            thumb_path = await safe_download_media(
                client, custom_thumb, f"thumbs/custom_{user_id}.jpg",
                cancel_event=cancel_event
            )
        elif message.video and getattr(message.video, 'thumbs', None):
            thumb_path = await safe_download_media(
                client, message.video.thumbs[0], f"thumbs/temp_{user_id}.jpg",
                cancel_event=cancel_event
            )
        thumb_path = await process_thumbnail(thumb_path)

        await status_msg.edit_text(
            "⬆️ **Uploading...**",
            reply_markup=_cancel_button(user_id)
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
        err = str(e)
        if "FILE_REFERENCE_EXPIRED" in err:
            err = "File is too old/forwarded. Please send again."
        try:
            await status_msg.edit_text(f"❌ **Error:** `{err}`", reply_markup=None)
        except Exception:
            await message.reply_text(f"❌ **Error:** `{err}`")

    finally:
        await cleanup_files(download_path, metadata_path, thumb_path)
        renaming_operations.pop(file_id, None)
        cancel_event.clear()          # always reset so next task isn't pre-cancelled
        if user_id in user_queues:
            user_queues[user_id]['active_client'] = None


# ══════════════════════════ WORKER ═══════════════════════════════════════════
async def user_queue_worker(user_id):
    """One worker per user — serialises all tasks for that user."""
    entry = user_queues[user_id]
    queue = entry['queue']
    while True:
        message, client = await queue.get()
        entry['cancel_current'].clear()        # fresh start
        entry['active_client'] = client
        try:
            await process_auto_rename_files(client, message, entry['cancel_current'])
        except Exception as e:
            logger.error(f"Worker error for user {user_id}: {e}", exc_info=True)
            try:
                await message.reply_text(f"**Error processing file:** `{e}`")
            except Exception:
                pass
        finally:
            queue.task_done()
            entry['active_client'] = None


# ══════════════════════════ QUEUE HANDLER (incoming files) ═══════════════════
@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def queue_auto_rename_files(client, message):
    user_id = message.from_user.id
    entry   = _get_or_create_user_queue(user_id)
    await entry['queue'].put((message, client))
    position = entry['queue'].qsize()
    text = (
        "▶️ **Starting your file now!**"
        if position == 1
        else f"📋 **Added to queue.** Position: **{position}**"
    )
    await message.reply_text(text)


# ══════════════════════════ CANCEL BUTTON (inline) ═══════════════════════════
@Client.on_callback_query(filters.regex(r"^cancel_task_(\d+)$"))
async def cancel_task_callback(client, query: CallbackQuery):
    """
    Cancel button below the progress bar.
    ▸ Only the owner of the task can press it.
    ▸ Cancels ONLY the current task; the remaining queue keeps running.
    """
    requester_id   = query.from_user.id
    target_user_id = int(query.matches[0].group(1))

    if requester_id != target_user_id:
        return await query.answer("⛔ You can only cancel your own tasks.", show_alert=True)

    _signal_cancel(target_user_id)
    await query.answer("✅ Cancellation requested. Your remaining queue will continue.", show_alert=False)


# ══════════════════════════ /cancel (user) ════════════════════════════════════
@Client.on_message(filters.private & filters.command("cancel"))
async def cancel_command(client, message: Message):
    """
    /cancel       → cancel ONLY your current running task
                    (the remaining 24 tasks in your queue keep going)

    /cancel all   → cancel your current task AND clear your entire queue
                    (all your tasks are gone, nothing left to run)
    """
    user_id = message.from_user.id
    args    = message.command[1:]

    if user_id not in user_queues or user_queues[user_id]['queue'].empty():
        # Check if a task is actively running (queue may be empty but worker busy)
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
            f"🗑️ **Your current task has been cancelled and {drained} queued "
            f"task(s) have been removed.**\nYou have no more tasks in the bot."
        )

    # Default: cancel only the current task, queue continues
    _signal_cancel(user_id)
    remaining = entry['queue'].qsize()
    await message.reply_text(
        f"🚫 **Current task cancelled.**\n"
        f"▶️ Your remaining **{remaining}** task(s) will continue automatically."
    )


# ══════════════════════════ /cancelall (admin) ════════════════════════════════
@Client.on_message(filters.private & filters.command("cancelall") & filters.user(Config.ADMIN))
async def cancel_all_command(client, message: Message):
    """
    Admin/owner only.
    Cancels every running task and clears every user's queue in the entire bot.
    Sends a DM to each affected user to inform them.
    """
    total_drained  = 0
    affected_users = []   # list of (user_id, drained_count, active_client)

    for uid, entry in list(user_queues.items()):
        q              = entry['queue']
        drained        = 0
        was_active     = entry['active_client'] is not None
        stored_client  = entry['active_client']   # may be None if idle

        while not q.empty():
            try:
                q.get_nowait()
                q.task_done()
                drained += 1
            except asyncio.QueueEmpty:
                break

        _signal_cancel(uid)

        if drained or was_active:
            total_drained += drained
            affected_users.append((uid, drained, stored_client or client))

    # Notify each affected user
    notified = 0
    for uid, drained, notify_client in affected_users:
        try:
            await notify_client.send_message(
                uid,
                "⚠️ **All your tasks have been cancelled by the Admin.**\n"
                f"**{drained} queued task(s)** were removed.\n\n"
                "Please add your files again if you wish to continue."
            )
            notified += 1
        except Exception as e:
            logger.warning(f"Could not notify user {uid}: {e}")

    await message.reply_text(
        f"✅ **Universal cancel complete.**\n"
        f"• Stopped tasks for **{len(affected_users)}** user(s)\n"
        f"• Cleared **{total_drained}** queued task(s)\n"
        f"• Notified **{notified}** user(s)"
    )


# ══════════════════════════ /queue ════════════════════════════════════════════
@Client.on_message(filters.private & filters.command("queue"))
async def queue_status(client, message: Message):
    """
    /queue — show overall bot queue status.

    Currently renaming: number of users with an active (running) task.
    Files left to rename: total tasks waiting across ALL users' queues.
    """
    currently_renaming = 0
    files_left         = 0

    for entry in user_queues.values():
        if entry['active_client'] is not None:   # a task is actively processing
            currently_renaming += 1
        files_left += entry['queue'].qsize()     # pending tasks in their queue

    await message.reply_text(
        f"📊 **Bot Queue Status**\n\n"
        f"🔄 **Currently renaming:** `{currently_renaming}`\n"
        f"📋 **Files left to rename:** `{files_left}`"
    )
