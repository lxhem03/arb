import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import UserNotParticipant, ChatAdminRequired, ChannelPrivate, PeerIdInvalid
from config import Config

FORCE_SUB_CHANNELS = Config.FORCE_SUB_CHANNELS
IMAGE_URL = "https://graph.org/file/a27d85469761da836337c.jpg"


async def _is_subscribed(client, channel, user_id) -> bool:
    """
    Returns True if the user is a member of the channel.
    Returns True (silently passes) if the bot lacks admin rights or the
    channel ID is invalid — so a misconfigured FORCE_SUB_CHANNELS never
    blocks all users.
    """
    try:
        member = await client.get_chat_member(channel, user_id)
        return member.status not in {"kicked", "left"}
    except UserNotParticipant:
        return False
    except (ChatAdminRequired, ChannelPrivate, PeerIdInvalid):
        # Bot isn't admin / channel doesn't exist — don't block users
        return True
    except Exception:
        return True


async def not_subscribed(_, client, message):
    for channel in FORCE_SUB_CHANNELS:
        if not channel or channel.strip() == "":
            continue
        if not await _is_subscribed(client, channel.strip(), message.from_user.id):
            return True
    return False


@Client.on_message(filters.private & filters.create(not_subscribed))
async def forces_sub(client, message):
    not_joined_channels = []
    for channel in FORCE_SUB_CHANNELS:
        if not channel or channel.strip() == "":
            continue
        ch = channel.strip()
        if not await _is_subscribed(client, ch, message.from_user.id):
            not_joined_channels.append(ch)

    if not not_joined_channels:
        return   # All joined — let the message through

    buttons = [
        [InlineKeyboardButton(
            text=f"• ᴊᴏɪɴ {ch.lstrip('@').capitalize()} •",
            url=f"https://t.me/{ch.lstrip('@')}"
        )]
        for ch in not_joined_channels
    ]
    buttons.append([
        InlineKeyboardButton(text="• ᴊᴏɪɴᴇᴅ •", callback_data="check_subscription")
    ])

    await message.reply_photo(
        photo=IMAGE_URL,
        caption="**ʙᴀᴋᴋᴀ!!, ʏᴏᴜ'ʀᴇ ɴᴏᴛ ᴊᴏɪɴᴇᴅ ᴛᴏ ᴀʟʟ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟs**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@Client.on_callback_query(filters.regex("check_subscription"))
async def check_subscription(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    not_joined_channels = []

    for channel in FORCE_SUB_CHANNELS:
        if not channel or channel.strip() == "":
            continue
        ch = channel.strip()
        if not await _is_subscribed(client, ch, user_id):
            not_joined_channels.append(ch)

    if not not_joined_channels:
        await callback_query.message.edit_caption(
            caption="**ʏᴏᴜ ʜᴀᴠᴇ ᴊᴏɪɴᴇᴅ ᴀʟʟ ᴛʜᴇ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟs. ᴛʜᴀɴᴋ ʏᴏᴜ! 😊 /start ɴᴏᴡ**",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("• ɴᴏᴡ ᴄʟɪᴄᴋ ʜᴇʀᴇ •", callback_data='help')
            ]])
        )
    else:
        buttons = [
            [InlineKeyboardButton(
                text=f"• ᴊᴏɪɴ {ch.lstrip('@').capitalize()} •",
                url=f"https://t.me/{ch.lstrip('@')}"
            )]
            for ch in not_joined_channels
        ]
        buttons.append([
            InlineKeyboardButton(text="• ᴊᴏɪɴᴇᴅ •", callback_data="check_subscription")
        ])
        await callback_query.message.edit_caption(
            caption="**ʏᴏᴜ ʜᴀᴠᴇ ɴᴏᴛ ᴊᴏɪɴᴇᴅ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ʏᴇᴛ.**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
