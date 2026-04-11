#fv2-2 — dump fix, {audio}/{languages}/{subtitles}/{resolution} placeholders
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

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ══════════════════════════ SHARED STATE ══════════════════════════════════════
renaming_operations = {}
user_queues: dict   = {}

# ══════════════════════════ SEASON / EPISODE PATTERNS ════════════════════════
SEASON_EPISODE_PATTERNS = [
    (re.compile(r'[Ss](\d{1,2})[Ee](\d{1,3})'),                               ('season', 'episode')),
    (re.compile(r'[Ss](\d{1,2})[._\s]+(\d{1,3})'),                            ('season', 'episode')),
    (re.compile(r'(\d{1,2})(?:st|nd|rd|th)[._\s]+Season[._\s]+(\d{1,3})',     re.IGNORECASE), ('season', 'episode')),
    (re.compile(r'(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)'
                r'[._\s]+Season[._\s]+(\d{1,3})',                              re.IGNORECASE), ('season_word', 'episode')),
]
WORD_TO_SEASON = {k.lower(): v for k, v in {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}.items()}

# Quality patterns used for {resolution} — scans the *filename* not the file
QUALITY_PATTERNS = [
    re.compile(r'\b(2160p|4K|UHD)\b',  re.IGNORECASE),
    re.compile(r'\b(1440p|2K)\b',       re.IGNORECASE),
    re.compile(r'\b(1080p|FHD)\b',      re.IGNORECASE),
    re.compile(r'\b(720p|HD)\b',        re.IGNORECASE),
    re.compile(r'\b(480p|SD)\b',        re.IGNORECASE),
    re.compile(r'\b(360p)\b',           re.IGNORECASE),
    re.compile(r'\b(240p)\b',           re.IGNORECASE),
    re.compile(r'\b(144p)\b',           re.IGNORECASE),
    re.compile(r'\b(\d{3,4})[pP]\b'),
]
QUALITY_NORMALISE = {
    '4k': '2160p', 'uhd': '2160p',
    '2k': '1440p',
    'fhd': '1080p',
    'hd': '720p',
    'sd': '480p',
}

# Language tag → human-readable name mapping (covers ISO 639-1/2/3 + common tags)
LANG_MAP = {
    'und': 'Unknown', 'mul': 'Multiple',
    'en': 'English',  'eng': 'English',
    'ja': 'Japanese', 'jpn': 'Japanese',
    'ko': 'Korean',   'kor': 'Korean',
    'zh': 'Chinese',  'zho': 'Chinese', 'chi': 'Chinese',
    'hi': 'Hindi',    'hin': 'Hindi',
    'ta': 'Tamil',    'tam': 'Tamil',
    'te': 'Telugu',   'tel': 'Telugu',
    'ml': 'Malayalam','mal': 'Malayalam',
    'kn': 'Kannada',  'kan': 'Kannada',
    'bn': 'Bengali',  'ben': 'Bengali',
    'mr': 'Marathi',  'mar': 'Marathi',
    'gu': 'Gujarati', 'guj': 'Gujarati',
    'pa': 'Punjabi',  'pan': 'Punjabi',
    'ur': 'Urdu',     'urd': 'Urdu',
    'fr': 'French',   'fra': 'French',  'fre': 'French',
    'de': 'German',   'deu': 'German',  'ger': 'German',
    'es': 'Spanish',  'spa': 'Spanish',
    'it': 'Italian',  'ita': 'Italian',
    'pt': 'Portuguese','por': 'Portuguese',
    'ru': 'Russian',  'rus': 'Russian',
    'ar': 'Arabic',   'ara': 'Arabic',
    'tr': 'Turkish',  'tur': 'Turkish',
    'pl': 'Polish',   'pol': 'Polish',
    'nl': 'Dutch',    'nld': 'Dutch',   'dut': 'Dutch',
    'sv': 'Swedish',  'swe': 'Swedish',
    'no': 'Norwegian','nor': 'Norwegian',
    'da': 'Danish',   'dan': 'Danish',
    'fi': 'Finnish',  'fin': 'Finnish',
    'cs': 'Czech',    'ces': 'Czech',   'cze': 'Czech',
    'sk': 'Slovak',   'slk': 'Slovak',  'slo': 'Slovak',
    'hu': 'Hungarian','hun': 'Hungarian',
    'ro': 'Romanian', 'ron': 'Romanian','rum': 'Romanian',
    'bg': 'Bulgarian','bul': 'Bulgarian',
    'hr': 'Croatian', 'hrv': 'Croatian',
    'sr': 'Serbian',  'srp': 'Serbian',
    'uk': 'Ukrainian','ukr': 'Ukrainian',
    'el': 'Greek',    'ell': 'Greek',   'gre': 'Greek',
    'he': 'Hebrew',   'heb': 'Hebrew',
    'th': 'Thai',     'tha': 'Thai',
    'vi': 'Vietnamese','vie': 'Vietnamese',
    'id': 'Indonesian','ind': 'Indonesian',
    'ms': 'Malay',    'msa': 'Malay',  'may': 'Malay',
    'fil': 'Filipino','tl': 'Filipino',
    'fa': 'Persian',  'fas': 'Persian', 'per': 'Persian',
    'az': 'Azerbaijani','aze': 'Azerbaijani',
    'ka': 'Georgian', 'kat': 'Georgian','geo': 'Georgian',
    'am': 'Amharic',  'amh': 'Amharic',
    'sw': 'Swahili',  'swa': 'Swahili',
    'zu': 'Zulu',     'zul': 'Zulu',
    'xh': 'Xhosa',   'xho': 'Xhosa',
    'af': 'Afrikaans','afr': 'Afrikaans',
    'sq': 'Albanian', 'sqi': 'Albanian','alb': 'Albanian',
    'hy': 'Armenian', 'hye': 'Armenian','arm': 'Armenian',
    'be': 'Belarusian','bel': 'Belarusian',
    'bs': 'Bosnian',  'bos': 'Bosnian',
    'ca': 'Catalan',  'cat': 'Catalan',
    'et': 'Estonian', 'est': 'Estonian',
    'lv': 'Latvian',  'lav': 'Latvian',
    'lt': 'Lithuanian','lit': 'Lithuanian',
    'mk': 'Macedonian','mkd': 'Macedonian','mac': 'Macedonian',
    'sl': 'Slovenian','slv': 'Slovenian',
    'is': 'Icelandic','isl': 'Icelandic','ice': 'Icelandic',
    'mt': 'Maltese',  'mlt': 'Maltese',
    'cy': 'Welsh',    'cym': 'Welsh',   'wel': 'Welsh',
    'ga': 'Irish',    'gle': 'Irish',
    'eu': 'Basque',   'eus': 'Basque',  'baq': 'Basque',
    'gl': 'Galician', 'glg': 'Galician',
    'lb': 'Luxembourgish','ltz': 'Luxembourgish',
    'mn': 'Mongolian','mon': 'Mongolian',
    'my': 'Burmese',  'mya': 'Burmese', 'bur': 'Burmese',
    'km': 'Khmer',    'khm': 'Khmer',
    'lo': 'Lao',      'lao': 'Lao',
    'si': 'Sinhala',  'sin': 'Sinhala',
    'ne': 'Nepali',   'nep': 'Nepali',
    'uz': 'Uzbek',    'uzb': 'Uzbek',
    'kk': 'Kazakh',   'kaz': 'Kazakh',
    'ky': 'Kyrgyz',   'kir': 'Kyrgyz',
    'tk': 'Turkmen',  'tuk': 'Turkmen',
    'tg': 'Tajik',    'tgk': 'Tajik',
    'ps': 'Pashto',   'pus': 'Pashto',
    'ku': 'Kurdish',  'kur': 'Kurdish',
    'so': 'Somali',   'som': 'Somali',
    'ha': 'Hausa',    'hau': 'Hausa',
    'yo': 'Yoruba',   'yor': 'Yoruba',
    'ig': 'Igbo',     'ibo': 'Igbo',
    'rw': 'Kinyarwanda','kin': 'Kinyarwanda',
}


def _resolve_lang(tag: str) -> str:
    """Convert an ISO language tag to a human-readable name."""
    if not tag:
        return 'Unknown'
    return LANG_MAP.get(tag.lower(), tag.capitalize())


# ══════════════════════════ MEDIA ANALYSIS ═══════════════════════════════════

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


def extract_resolution_from_filename(filename: str) -> str:
    """Scan the filename for a quality/resolution tag."""
    for pattern in QUALITY_PATTERNS:
        m = pattern.search(filename)
        if m:
            raw = m.group(1).lower()
            return QUALITY_NORMALISE.get(raw, m.group(1))
    return 'Unknown'


async def cmd_exec(cmd: list):
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode().strip(), stderr.decode().strip()


async def analyse_streams(file_path: str) -> dict:
    """
    Run ffprobe once and extract everything we need:
      - video height  → for {quality} from actual stream
      - audio tracks  → count + language list  → {audio} / {languages}
      - subtitle tracks → unique language list  → {subtitles}
    Returns a dict with keys: height, audio_count, audio_langs, sub_langs
    """
    result = {
        'height':      None,
        'audio_count': 0,
        'audio_langs': [],
        'sub_langs':   [],
    }
    try:
        stdout, _ = await cmd_exec([
            "ffprobe", "-hide_banner", "-loglevel", "error",
            "-print_format", "json", "-show_streams", file_path
        ])
        streams = json.loads(stdout).get("streams", [])

        seen_sub_langs = []   # ordered, deduped

        for s in streams:
            codec_type = s.get("codec_type", "")
            tags       = s.get("tags", {}) or {}
            lang_raw   = tags.get("language") or tags.get("LANGUAGE") or ""

            if codec_type == "video" and result['height'] is None:
                result['height'] = s.get("height")

            elif codec_type == "audio":
                result['audio_count'] += 1
                result['audio_langs'].append(_resolve_lang(lang_raw))

            elif codec_type == "subtitle":
                human = _resolve_lang(lang_raw)
                if human not in seen_sub_langs:
                    seen_sub_langs.append(human)

        result['sub_langs'] = seen_sub_langs

    except Exception as e:
        logger.error(f"Stream analysis error: {e}")

    return result


def _audio_label(count: int) -> str:
    if count <= 1:   return "Sub"
    if count == 2:   return "Dual"
    return "Multi"


# ══════════════════════════ FILE HELPERS ═════════════════════════════════════

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
    if title:      cmd += ['-metadata', f'title={title}']
    if author:     cmd += ['-metadata', f'author={author}']
    if artist:     cmd += ['-metadata', f'artist={artist}']
    if video:      cmd += ['-metadata:s:v', f'title={video}']
    if audio:      cmd += ['-metadata:s:a', f'title={audio}']
    elif rm_audio: cmd += ['-metadata:s:a', 'title=']
    if subtitle:   cmd += ['-metadata:s:s', f'title={subtitle}']
    elif rm_sub:   cmd += ['-metadata:s:s', 'title=']
    cmd += ['-loglevel', 'error', output_path]

    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Metadata processing failed")


# ══════════════════════════ PLACEHOLDER SUBSTITUTION ════════════════════════
def apply_placeholders(template: str, season, episode, streams: dict,
                        filename: str) -> str:
    """
    Replace all supported placeholders in a template string.

    Filename/episode placeholders:
      {season}      → season number (01, 02 …)
      {episode}     → episode number (01, 02 …)
      {resolution}  → quality tag found in the *filename* (e.g. 1080p)
      {quality}     → same as {resolution} (alias, kept for back-compat)

    Stream-based placeholders (require the downloaded file):
      {audio}       → Sub / Dual / Multi
      {languages}   → comma-separated audio language names
      {subtitles}   → comma-separated subtitle language names (deduped)
    """
    audio_count = streams.get('audio_count', 0)
    audio_langs = streams.get('audio_langs', [])
    sub_langs   = streams.get('sub_langs', [])
    height      = streams.get('height')

    # {quality} → prefer stream height, fall back to filename scan
    if height:
        quality_val = f"{height}p"
    else:
        quality_val = extract_resolution_from_filename(filename)

    resolution_val = extract_resolution_from_filename(filename)

    subs = {
        '{season}':      str(season  or 1).zfill(2),
        '{episode}':     str(episode or 1).zfill(2),
        '{quality}':     quality_val,
        '{resolution}':  resolution_val,
        '{audio}':       _audio_label(audio_count),
        '{languages}':   ', '.join(audio_langs) if audio_langs else 'Unknown',
        '{subtitles}':   ', '.join(sub_langs)   if sub_langs   else 'None',
    }

    result = template
    for ph, val in subs.items():
        result = result.replace(ph, val)
    return result


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

            sent_msg = await asyncio.wait_for(
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
            return sent_msg

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
    return None


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
            "🔍 **Analysing streams...**",
            reply_markup=_cancel_button(user_id)
        )

        season, episode = extract_season_episode(original_file_name)
        streams         = await analyse_streams(file_path)   # single ffprobe call

        # Build new filename
        new_name_base  = apply_placeholders(
            format_template, season, episode, streams, original_file_name
        )
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

        # Caption — also supports the same placeholders
        raw_caption = await codeflixbots.get_caption(user_id) or f"**{final_filename}**"
        caption = apply_placeholders(
            raw_caption, season, episode, streams, original_file_name
        )
        # Also substitute {filename} variable for captions
        caption = caption.replace('{filename}', final_filename)

        # Thumbnail
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

        user_dump   = await codeflixbots.get_dump_channel(user_id)
        global_dump = Config.DUMP_CHANNEL if Config.DUMP_CHANNEL else None

        # ── decide where to send the file ────────────────────────────────────
        # If user has a personal dump set, send THERE (not to PM).
        # Always also forward to the global dump channel (if configured).
        primary_chat = user_dump if user_dump else message.chat.id

        sent_msg = await upload_with_retry(
            client=client,
            chat_id=primary_chat,
            file_path=metadata_path,
            caption=caption,
            thumb=thumb_path,
            status_msg=status_msg,
            cancel_event=cancel_event
        )

        if sent_msg:
            # Forward to global dump if it's different from where we already sent
            if global_dump and global_dump != primary_chat:
                try:
                    await sent_msg.copy(global_dump)
                except Exception as e:
                    logger.warning(f"Failed to copy to global dump {global_dump}: {e}")

            # If we sent to user's dump (not PM), notify them in PM
            if user_dump:
                try:
                    await client.send_message(
                        message.chat.id,
                        "✅ **File renamed and sent to your dump channel!**"
                    )
                except Exception:
                    pass

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
        cancel_event.clear()
        if user_id in user_queues:
            user_queues[user_id]['active_client'] = None


# ══════════════════════════ WORKER ═══════════════════════════════════════════
async def user_queue_worker(user_id):
    entry = user_queues[user_id]
    queue = entry['queue']
    while True:
        message, client = await queue.get()
        entry['cancel_current'].clear()
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
    requester_id   = query.from_user.id
    target_user_id = int(query.matches[0].group(1))
    if requester_id != target_user_id:
        return await query.answer("⛔ You can only cancel your own tasks.", show_alert=True)
    _signal_cancel(target_user_id)
    await query.answer("✅ Cancellation requested. Your remaining queue will continue.",
                       show_alert=False)


# ══════════════════════════ /cancel (user) ════════════════════════════════════
@Client.on_message(filters.private & filters.command("cancel"))
async def cancel_command(client, message: Message):
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
                q.get_nowait(); q.task_done(); drained += 1
            except asyncio.QueueEmpty:
                break
        _signal_cancel(user_id)
        return await message.reply_text(
            f"🗑️ **Your current task has been cancelled and {drained} queued "
            f"task(s) have been removed.**\nYou have no more tasks in the bot."
        )
    _signal_cancel(user_id)
    remaining = entry['queue'].qsize()
    await message.reply_text(
        f"🚫 **Current task cancelled.**\n"
        f"▶️ Your remaining **{remaining}** task(s) will continue automatically."
    )


# ══════════════════════════ /cancelall (admin) ════════════════════════════════
@Client.on_message(filters.private & filters.command("cancelall") & filters.user(Config.ADMIN))
async def cancel_all_command(client, message: Message):
    total_drained  = 0
    affected_users = []
    for uid, entry in list(user_queues.items()):
        q           = entry['queue']
        drained     = 0
        was_active  = entry['active_client'] is not None
        stored_cli  = entry['active_client']
        while not q.empty():
            try:
                q.get_nowait(); q.task_done(); drained += 1
            except asyncio.QueueEmpty:
                break
        _signal_cancel(uid)
        if drained or was_active:
            total_drained += drained
            affected_users.append((uid, drained, stored_cli or client))
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
    currently_renaming = 0
    files_left         = 0
    for entry in user_queues.values():
        if entry['active_client'] is not None:
            currently_renaming += 1
        files_left += entry['queue'].qsize()
    await message.reply_text(
        f"📊 **Bot Queue Status**\n\n"
        f"🔄 **Currently renaming:** `{currently_renaming}`\n"
        f"📋 **Files left to rename:** `{files_left}`"
    )
