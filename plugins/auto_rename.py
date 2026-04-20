from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from helper.database import codeflixbots
from pyrogram.enums import ParseMode

@Client.on_message(filters.private & filters.command("autorename"))
async def auto_rename_command(client, message):
    user_id = message.from_user.id

    # Extract and validate the format from the command
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2 or not command_parts[1].strip():
        await message.reply_text(
            """
            <b>ᴘʟᴀᴄᴇʜᴏʟᴅᴇʀꜱ ʏᴏᴜ ᴄᴀɴ ᴜꜱᴇ:</b>

<code>{episode}</code>  — ᴇᴘɪꜱᴏᴅᴇ ɴᴜᴍʙᴇʀ
<code>{season}</code>   — ꜱᴇᴀꜱᴏɴ ɴᴜᴍʙᴇʀ
<code>{quality}</code>  — ᴠɪᴅᴇᴏ ǫᴜᴀʟɪᴛʏ ꜰʀᴏᴍ ꜱᴛʀᴇᴀᴍ (ᴇɢ. 1080ᴘ)
<code>{resolution}</code> — ǫᴜᴀʟɪᴛʏ ꜰʀᴏᴍ ꜰɪʟᴇɴᴀᴍᴇ
<code>{audio}</code>    — Sᴜʙ / Dᴜᴀʟ / Mᴜʟᴛɪ
<code>{codec}</code>    — ᴠɪᴅᴇᴏ ᴄᴏᴅᴇᴄ (ᴇɢ. H.265, AV1)
<code>{filesize}</code> — ꜰɪʟᴇ ꜱɪᴢᴇ (ᴇɢ. 2.4 Gʙ)

<b>‣ ᴇxᴀᴍᴘʟᴇ:</b>
<code>/autorename Anime Name S{season}E{episode} [{quality} {audio} {codec}]</code>

<b>‣ ᴏᴜᴛᴘᴜᴛ:</b> <code>Anime Name S01E04 [1080p Dual H.265].mkv</code>""",
            parse_mode=ParseMode.HTML
        )
        return

    format_template = command_parts[1].strip()

    # Save the format template in the database
    await codeflixbots.set_format_template(user_id, format_template)

    # Send confirmation message with the template in monospaced font
    await message.reply_text(
        f"**🌟 Fantastic! You're ready to auto-rename your files.**\n\n"
        "📩 Simply send the file(s) you want to rename.\n\n"
        f"**Your saved template:** `{format_template}`\n\n"
        "Remember, it might take some time, but I'll ensure your files are renamed perfectly!✨"
    )
