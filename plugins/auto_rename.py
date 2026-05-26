import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from helper.database import codeflixbots
from pyrogram.enums import ParseMode

# Validates a single triplet like "25:2:1"
_TRIPLET_RE = re.compile(r'^\d+:\d+:\d+$')

def _parse_map_flag(text: str):
    """
    Extracts --map <triplets> from the command text.
    Returns (clean_template, map_str_or_None, error_msg_or_None).

    Accepted formats:
        --map 25:2:1
        --map 25:2:1 49:3:1 73:4:1   (multiple ranges, space-separated)
    """
    map_match = re.search(r'--map\s+((?:\d+:\d+:\d+\s*)+)', text)
    if not map_match:
        # No --map flag at all — clear any existing map
        clean = re.sub(r'--map.*', '', text).strip()
        return clean, None, None

    raw_triplets = map_match.group(1).strip().split()

    # Validate every triplet
    for t in raw_triplets:
        if not _TRIPLET_RE.match(t):
            return None, None, (
                f"❌ Invalid --map value: <code>{t}</code>\n"
                "Each entry must be <code>START_EP:TARGET_SEASON:TARGET_EP</code>\n"
                "Example: <code>--map 25:2:1 49:3:1</code>"
            )

    # Extra sanity: start episodes must be strictly increasing
    starts = [int(t.split(':')[0]) for t in raw_triplets]
    if starts != sorted(starts):
        return None, None, (
            "❌ --map ranges must be in ascending order of start episode.\n"
            "Example: <code>--map 25:2:1 49:3:1</code>"
        )

    map_str   = ' '.join(raw_triplets)          # normalised, stored in DB
    clean_tpl = re.sub(r'--map\s+(?:\d+:\d+:\d+\s*)+', '', text).strip()
    return clean_tpl, map_str, None


@Client.on_message(filters.private & filters.command("autorename"))
async def auto_rename_command(client, message):
    user_id = message.from_user.id

    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2 or not command_parts[1].strip():
        await message.reply_text(
            """<b>ᴘʟᴀᴄᴇʜᴏʟᴅᴇʀꜱ ʏᴏᴜ ᴄᴀɴ ᴜꜱᴇ:</b>

<code>{episode}</code>  — ᴇᴘɪꜱᴏᴅᴇ ɴᴜᴍʙᴇʀ
<code>{season}</code>   — ꜱᴇᴀꜱᴏɴ ɴᴜᴍʙᴇʀ
<code>{quality}</code>  — ᴠɪᴅᴇᴏ ǫᴜᴀʟɪᴛʏ ꜰʀᴏᴍ ꜱᴛʀᴇᴀᴍ (ᴇɢ. 1080ᴘ)
<code>{resolution}</code> — ǫᴜᴀʟɪᴛʏ ꜰʀᴏᴍ ꜰɪʟᴇɴᴀᴍᴇ
<code>{audio}</code>    — Sᴜʙ / Dᴜᴀʟ / Mᴜʟᴛɪ
<code>{codec}</code>    — ᴠɪᴅᴇᴏ ᴄᴏᴅᴇᴄ (ᴇɢ. H.265, AV1)
<code>{filesize}</code> — ꜰɪʟᴇ ꜱɪᴢᴇ (ᴇɢ. 2.4 Gʙ)

<b>‣ ᴇxᴀᴍᴘʟᴇ:</b>
<code>/autorename Anime Name S{season}E{episode} [{quality} {audio} {codec}]</code>

<b>‣ ᴏᴜᴛᴘᴜᴛ:</b> <code>Anime Name S01E04 [1080p Dual H.265].mkv</code>

<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>
<b>ᴇᴘɪꜱᴏᴅᴇ ᴍᴀᴘᴘɪɴɢ (optional):</b>

Use <code>--map START:SEASON:EP ...</code> to remap absolute episode numbers
to the correct season and episode.

<b>‣ ꜰᴏʀᴍᴀᴛ:</b> <code>--map &lt;abs_ep&gt;:&lt;season&gt;:&lt;ep_start&gt;</code>

<b>‣ ᴇxᴀᴍᴘʟᴇ (2 ꜱᴇᴀꜱᴏɴꜱ, 24 ᴇᴘ ᴇᴀᴄʜ):</b>
<code>/autorename Anime S{season}E{episode} --map 1:1:1 25:2:1</code>

<b>‣ ᴇxᴀᴍᴘʟᴇ (3 ꜱᴇᴀꜱᴏɴꜱ):</b>
<code>/autorename Anime S{season}E{episode} --map 1:1:1 25:2:1 49:3:1</code>

E25 → S02E01 · E26 → S02E02 · E48 → S02E24 · E49 → S03E01""",
            parse_mode=ParseMode.HTML
        )
        return

    full_args = command_parts[1].strip()

    # Parse out --map flag
    format_template, map_str, err = _parse_map_flag(full_args)
    if err:
        return await message.reply_text(err, parse_mode=ParseMode.HTML)

    if not format_template:
        return await message.reply_text(
            "❌ Template cannot be empty. Please provide a rename format.",
            parse_mode=ParseMode.HTML
        )

    # Persist both template and map
    await codeflixbots.set_format_template(user_id, format_template)
    await codeflixbots.set_episode_map(user_id, map_str)  # None = cleared

    # Build confirmation
    map_info = ""
    if map_str:
        triplets = map_str.split()
        lines = []
        for i, t in enumerate(triplets):
            start, season, ep_start = map(int, t.split(':'))
            # Find end of this range
            if i + 1 < len(triplets):
                next_start = int(triplets[i + 1].split(':')[0])
                end = next_start - 1
                ep_end = ep_start + (end - start)
                lines.append(f"  E{start}–E{end} → S{season:02d}E{ep_start:02d}–S{season:02d}E{ep_end:02d}")
            else:
                lines.append(f"  E{start}+ → S{season:02d}E{ep_start:02d}+")
        map_info = "\n\n🗺 **Episode map saved:**\n" + "\n".join(lines)
    else:
        map_info = "\n\n🗺 **Episode map:** none (cleared)"

    await message.reply_text(
        f"**🌟 Fantastic! You're ready to auto-rename your files.**\n\n"
        "📩 Simply send the file(s) you want to rename.\n\n"
        f"**Your saved template:** `{format_template}`"
        f"{map_info}\n\n"
        "Remember, it might take some time, but I'll ensure your files are renamed perfectly!✨"
    )
