# plugins/dump.py — /dump command: per-user dump channel management
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from pyrogram.errors import (
    ChatAdminRequired, ChannelPrivate, PeerIdInvalid,
    UsernameInvalid, UsernameNotOccupied, MessageNotModified
)
from helper.database import codeflixbots

logger = logging.getLogger(__name__)

# ── state tracking for users currently setting a dump channel ────────────────
# dump_states[user_id] = {'prompt_msg_id': int, 'menu_msg_id': int}
dump_states: dict = {}


# ── helpers ──────────────────────────────────────────────────────────────────
async def _build_dump_menu(user_id: int):
    dump_id = await codeflixbots.get_dump_channel(user_id)

    if dump_id:
        text = (
            f"📤 **Your Dump Channel**\n\n"
            f"**Current dump:** `{dump_id}`\n\n"
            f"Files you rename will also be forwarded to this channel."
        )
        buttons = [[
            InlineKeyboardButton("✏️ Change", callback_data="dump_set"),
            InlineKeyboardButton("🗑 Remove",  callback_data="dump_remove"),
        ]]
    else:
        text = (
            "📤 **Your Dump Channel**\n\n"
            "**Current dump:** `None`\n\n"
            "Set a dump channel and every renamed file will be "
            "forwarded there automatically."
        )
        buttons = [[
            InlineKeyboardButton("➕ Set", callback_data="dump_set"),
        ]]

    return text, InlineKeyboardMarkup(buttons)


# ── /dump command ─────────────────────────────────────────────────────────────
@Client.on_message(filters.private & filters.command("dump"))
async def dump_command(client: Client, message: Message):
    user_id = message.from_user.id
    text, markup = await _build_dump_menu(user_id)
    await message.reply_text(text, reply_markup=markup)


# ── callback: Set / Remove / Cancel ──────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^dump_(set|remove|cancel)$"))
async def dump_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    action  = query.matches[0].group(1)

    # ── Remove ───────────────────────────────────────────────────────────────
    if action == "remove":
        await codeflixbots.remove_dump_channel(user_id)
        text, markup = await _build_dump_menu(user_id)
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except MessageNotModified:
            pass
        await query.answer("✅ Dump channel removed.", show_alert=False)
        return

    # ── Cancel (go back to menu) ─────────────────────────────────────────────
    if action == "cancel":
        dump_states.pop(user_id, None)
        text, markup = await _build_dump_menu(user_id)
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except MessageNotModified:
            pass
        await query.answer()
        return

    # ── Set ───────────────────────────────────────────────────────────────────
    prompt_text = (
        "📤 **Set Dump Channel**\n\n"
        "Send me the **channel ID** (e.g. `-1001234567890`) or "
        "**@username** of the channel.\n\n"
        "⚠️ Make sure I am an **Admin** in that channel first!\n\n"
        "⏰ Timeout: **60 seconds**"
    )
    cancel_markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Cancel", callback_data="dump_cancel")
    ]])

    try:
        await query.message.edit_text(prompt_text, reply_markup=cancel_markup)
    except MessageNotModified:
        pass

    dump_states[user_id] = {
        'menu_msg_id': query.message.id,
    }

    await query.answer()

    # Auto-cancel after 60 s if user doesn't reply
    asyncio.create_task(_dump_timeout(client, user_id))


# ── handle user's reply with channel id/username ─────────────────────────────
@Client.on_message(filters.private & filters.text & ~filters.command([]))
async def dump_input_handler(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id not in dump_states:
        return

    state       = dump_states.pop(user_id)
    menu_msg_id = state['menu_msg_id']
    raw_input   = message.text.strip()

    # Try to parse as int (channel id) or keep as username
    try:
        channel_ref = int(raw_input)
    except ValueError:
        channel_ref = raw_input   # treat as @username

    # ── verification: try to send a test message then delete it ──────────────
    verify_msg = await message.reply_text("🔍 **Verifying channel access...**")

    try:
        test = await client.send_message(channel_ref, "🔄 _Test message — ignore this._")
        await asyncio.sleep(1)
        await test.delete()
    except (ChatAdminRequired, ChannelPrivate):
        await verify_msg.edit_text(
            "❌ **I'm not an admin in that channel.**\n\n"
            "Please make me an admin and try again."
        )
        # Restore menu
        text, markup = await _build_dump_menu(user_id)
        try:
            await client.edit_message_text(
                chat_id=user_id, message_id=menu_msg_id,
                text=text, reply_markup=markup
            )
        except Exception:
            pass
        return
    except (PeerIdInvalid, UsernameInvalid, UsernameNotOccupied):
        await verify_msg.edit_text(
            "❌ **Invalid channel ID or username.**\n\n"
            "Make sure you send a valid channel ID like `-1001234567890` "
            "or a public @username."
        )
        text, markup = await _build_dump_menu(user_id)
        try:
            await client.edit_message_text(
                chat_id=user_id, message_id=menu_msg_id,
                text=text, reply_markup=markup
            )
        except Exception:
            pass
        return
    except Exception as e:
        logger.error(f"Dump channel verification failed for user {user_id}: {e}")
        await verify_msg.edit_text(
            f"❌ **Could not access that channel.**\n\n"
            f"Error: `{e}`\n\n"
            f"Make sure the bot is an admin and the ID is correct."
        )
        text, markup = await _build_dump_menu(user_id)
        try:
            await client.edit_message_text(
                chat_id=user_id, message_id=menu_msg_id,
                text=text, reply_markup=markup
            )
        except Exception:
            pass
        return

    # ── save the verified channel id ─────────────────────────────────────────
    # Resolve to numeric id if a username was given
    try:
        chat = await client.get_chat(channel_ref)
        numeric_id = chat.id
    except Exception:
        numeric_id = channel_ref   # fall back to whatever was given

    await codeflixbots.set_dump_channel(user_id, numeric_id)

    # Clean up
    try:
        await verify_msg.delete()
    except Exception:
        pass
    try:
        await message.delete()
    except Exception:
        pass

    # Update the menu message to show the new dump
    text, markup = await _build_dump_menu(user_id)
    try:
        await client.edit_message_text(
            chat_id=user_id, message_id=menu_msg_id,
            text=text, reply_markup=markup
        )
    except MessageNotModified:
        pass

    await client.send_message(
        user_id,
        f"✅ **Dump channel set successfully!**\n"
        f"Channel ID: `{numeric_id}`\n\n"
        f"Every renamed file will now also be sent there."
    )


# ── timeout ───────────────────────────────────────────────────────────────────
async def _dump_timeout(client: Client, user_id: int):
    await asyncio.sleep(60)
    if user_id not in dump_states:
        return   # already handled

    state = dump_states.pop(user_id)
    menu_msg_id = state['menu_msg_id']

    try:
        text, markup = await _build_dump_menu(user_id)
        await client.edit_message_text(
            chat_id=user_id, message_id=menu_msg_id,
            text=text, reply_markup=markup
        )
    except Exception:
        pass

    try:
        await client.send_message(user_id, "⏰ **Timed out.** Dump channel setup cancelled.")
    except Exception:
        pass
