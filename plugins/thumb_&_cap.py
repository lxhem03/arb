# thumb_&_cap.py — caption commands + thumbnail view/delete
from pyrogram import Client, filters
from helper.database import codeflixbots


@Client.on_message(filters.private & filters.command('set_caption'))
async def add_caption(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            """
            <b>ᴘʟᴀᴄᴇʜᴏʟᴅᴇʀꜱ ꜰᴏʀ ᴄᴀᴘᴛɪᴏɴ:</b>
<code>{filename}</code>   — ꜰɪɴᴀʟ ʀᴇɴᴀᴍᴇᴅ ꜰɪʟᴇɴᴀᴍᴇ
<code>{filesize}</code>   — ꜰɪʟᴇ ꜱɪᴢᴇ
<code>{audio}</code>      — Sᴜʙ / Dᴜᴀʟ / Mᴜʟᴛɪ
<code>{languages}</code>  — ᴀᴜᴅɪᴏ ʟᴀɴɢᴜᴀɢᴇꜱ
<code>{subtitles}</code>  — ꜱᴜʙᴛɪᴛʟᴇ ʟᴀɴɢᴜᴀɢᴇꜱ
<code>{quality}</code>    — ᴠɪᴅᴇᴏ ǫᴜᴀʟɪᴛʏ
<code>{codec}</code>      — ᴠɪᴅᴇᴏ ᴄᴏᴅᴇᴄ
<code>{episode}</code>    — ᴇᴘɪꜱᴏᴅᴇ ɴᴜᴍʙᴇʀ
<code>{season}</code>     — ꜱᴇᴀꜱᴏɴ ɴᴜᴍʙᴇʀ

<b>‣ ᴇxᴀᴍᴘʟᴇ:</b>
<code>/set_caption 🎬 {filename}
📦 Size: {filesize} | 🎵 {audio} | 🔤 {subtitles}</code>""",
            parse_mode="html"
        )
    caption = message.text.split(" ", 1)[1]
    await codeflixbots.set_caption(message.from_user.id, caption=caption)
    await message.reply_text("**Your Caption Successfully Added ✅**")


@Client.on_message(filters.private & filters.command('del_caption'))
async def delete_caption(client, message):
    caption = await codeflixbots.get_caption(message.from_user.id)
    if not caption:
        return await message.reply_text("**You Don't Have Any Caption ❌**")
    await codeflixbots.set_caption(message.from_user.id, caption=None)
    await message.reply_text("**Your Caption Successfully Deleted 🗑️**")


@Client.on_message(filters.private & filters.command(['see_caption', 'view_caption']))
async def see_caption(client, message):
    caption = await codeflixbots.get_caption(message.from_user.id)
    if caption:
        await message.reply_text(f"**Your Caption :**\n\n`{caption}`")
    else:
        await message.reply_text("**You Don't Have Any Caption ❌**")


@Client.on_message(filters.private & filters.command(['view_thumb', 'viewthumb']))
async def viewthumb(client, message):
    thumb = await codeflixbots.get_thumbnail(message.from_user.id)
    if thumb:
        await client.send_photo(chat_id=message.chat.id, photo=thumb,
                                caption="🖼️ **Your current thumbnail**")
    else:
        await message.reply_text(
            "**You Don't Have Any Thumbnail ❌**\n\n"
            "Send a photo and reply to it with `/setthumb` to set one."
        )


@Client.on_message(filters.private & filters.command(['del_thumb', 'delthumb']))
async def removethumb(client, message):
    await codeflixbots.set_thumbnail(message.from_user.id, file_id=None)
    await message.reply_text("**Thumbnail Deleted Successfully 🗑️**")
