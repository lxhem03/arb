import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from helper.database import codeflixbots
from config import Config, Txt

LOG_CHANNEL = Config.LOG_CHANNEL

# ══════════════════════════ /start ════════════════════════════════════════════
@Client.on_message(filters.private & filters.command("start"))
async def start(client, message: Message):
    user = message.from_user
    await codeflixbots.add_user(client, message)

    m = await message.reply_text("👀")
    await asyncio.sleep(0.4)
    await m.edit_text("🎊")
    await asyncio.sleep(0.5)
    await m.edit_text("⚡")
    await asyncio.sleep(0.5)
    await m.edit_text("Hola!...")
    await asyncio.sleep(0.4)
    await m.delete()

    s = await message.reply_sticker("CAACAgIAAxkBAALAlWnlvhggEAv5oNGqVWRH7mwRfixbAAIDRwACt6TpSKLqrZMGoYzqOwQ")

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("• ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs •", callback_data='help')],
        [
            InlineKeyboardButton('• ᴜᴘᴅᴀᴛᴇs', url='https://t.me/The_TGguy'),
            InlineKeyboardButton('sᴜᴘᴘᴏʀᴛ •',  url='https://t.me/TGXNectar')
        ],
        [
            InlineKeyboardButton('• ᴀʙᴏᴜᴛ',  callback_data='about')
        ],
    ])

    if Config.START_PIC:
        await message.reply_photo(
            Config.START_PIC,
            caption=Txt.START_TXT.format(user.mention),
            reply_markup=buttons
        )
    else:
        await message.reply_text(
            text=Txt.START_TXT.format(user.mention),
            reply_markup=buttons,
            disable_web_page_preview=True
        )
    await s.delete()


# ══════════════════════════ /help ════════════════════════════════════════════
@Client.on_message(filters.private & filters.command("help"))
async def help_command(client, message: Message):
    bot = await client.get_me()
    await message.reply_text(
        text=Txt.HELP_TXT.format(mention=bot.mention),
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("• ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ •", callback_data='file_names')],
            [
                InlineKeyboardButton('• ᴛʜᴜᴍʙɴᴀɪʟ', callback_data='thumbnail'),
                InlineKeyboardButton('ᴄᴀᴘᴛɪᴏɴ •',    callback_data='caption')
            ],
            [
                InlineKeyboardButton('• ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='meta')
            ],
            [InlineKeyboardButton('• ʜᴏᴍᴇ', callback_data='home')],
        ])
    )



# ══════════════════════════ CALLBACKS (only this plugin's own data) ══════════
# IMPORTANT: this handler ONLY matches callbacks it owns explicitly.
# All other callbacks (settings_, dump_, cancel_task_, metadata, etc.)
# are handled by their own plugins and must NOT be caught here.
_OWN_CALLBACKS = {
    "home", "help", "caption", "thumbnail", "meta", "metadatax",
    "donate", "file_names", "source", "premiumx", "plans", "about",
    "close", "close_data",
}

@Client.on_callback_query(filters.regex(
    r"^(home|help|caption|thumbnail|meta|metadatax|donate|file_names|"
    r"source|premiumx|plans|about|close|close_data)$"
))
async def cb_handler(client, query: CallbackQuery):
    data    = query.data
    user_id = query.from_user.id

    if data == "home":
        await query.message.edit_text(
            text=Txt.START_TXT.format(query.from_user.mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs •", callback_data='help')],
                [
                    InlineKeyboardButton('• ᴜᴘᴅᴀᴛᴇs', url='https://t.me/Codeflix_Bots'),
                    InlineKeyboardButton('sᴜᴘᴘᴏʀᴛ •',  url='https://t.me/CodeflixSupport')
                ],
                [
                    InlineKeyboardButton('• ᴀʙᴏᴜᴛ',  callback_data='about'),
                    InlineKeyboardButton('sᴏᴜʀᴄᴇ •', callback_data='source')
                ],
            ])
        )

    elif data == "caption":
        await query.message.edit_text(
            text=Txt.CAPTION_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("• sᴜᴘᴘᴏʀᴛ", url='https://t.me/CodeflixSupport'),
                InlineKeyboardButton("ʙᴀᴄᴋ •",     callback_data="help")
            ]])
        )

    elif data == "help":
        bot = await client.get_me()
        await query.message.edit_text(
            text=Txt.HELP_TXT.format(mention=bot.mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ •", callback_data='file_names')],
                [
                    InlineKeyboardButton('• ᴛʜᴜᴍʙɴᴀɪʟ', callback_data='thumbnail'),
                    InlineKeyboardButton('ᴄᴀᴘᴛɪᴏɴ •',    callback_data='caption')
                ],
                [
                    InlineKeyboardButton('• ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='meta'),
                    InlineKeyboardButton('ᴅᴏɴᴀᴛᴇ •',   callback_data='donate')
                ],
                [InlineKeyboardButton('• ʜᴏᴍᴇ', callback_data='home')],
            ])
        )

    elif data == "meta":
        await query.message.edit_text(
            text=Txt.SEND_METADATA,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"),
                InlineKeyboardButton("ʙᴀᴄᴋ •",  callback_data="help")
            ]])
        )

    elif data == "donate":
        await query.message.edit_text(
            text=Txt.DONATE_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("• ʙᴀᴄᴋ", callback_data="help"),
                InlineKeyboardButton("ᴏᴡɴᴇʀ •", url='https://t.me/sewxiy')
            ]])
        )

    elif data == "file_names":
        format_template = await codeflixbots.get_format_template(user_id)
        await query.message.edit_text(
            text=Txt.FILE_NAME_TXT.format(format_template=format_template),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"),
                InlineKeyboardButton("ʙᴀᴄᴋ •",  callback_data="help")
            ]])
        )

    elif data == "thumbnail":
        try:
            await query.message.edit_caption(
                caption=Txt.THUMBNAIL_TXT,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"),
                    InlineKeyboardButton("ʙᴀᴄᴋ •",  callback_data="help")
                ]])
            )
        except Exception:
            await query.message.edit_text(
                text=Txt.THUMBNAIL_TXT,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"),
                    InlineKeyboardButton("ʙᴀᴄᴋ •",  callback_data="help")
                ]])
            )

    elif data == "source":
        try:
            await query.message.edit_caption(
                caption=Txt.SOURCE_TXT,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"),
                    InlineKeyboardButton("ʙᴀᴄᴋ •",  callback_data="home")
                ]])
            )
        except Exception:
            await query.message.edit_text(
                text=Txt.SOURCE_TXT,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"),
                    InlineKeyboardButton("ʙᴀᴄᴋ •",  callback_data="home")
                ]])
            )

    elif data == "about":
        await query.message.edit_text(
            text=Txt.ABOUT_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("• sᴜᴘᴘᴏʀᴛ",   url='https://t.me/CodeflixSupport'),
                    InlineKeyboardButton("ᴄᴏᴍᴍᴀɴᴅs •", callback_data="help")
                ],
                [
                    InlineKeyboardButton("• ᴅᴇᴠᴇʟᴏᴘᴇʀ", url='https://t.me/cosmic_freak'),
                    InlineKeyboardButton("ɴᴇᴛᴡᴏʀᴋ •",   url='https://t.me/otakuflix_network')
                ],
                [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="home")],
            ])
        )

    elif data in ("close", "close_data"):
        try:
            await query.message.delete()
            if query.message.reply_to_message:
                await query.message.reply_to_message.delete()
        except Exception:
            pass

    await query.answer()
