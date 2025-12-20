from helper.database import codeflixbots as db
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import MessageNotModified
import asyncio
import logging

user_states = {}

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

logger.info("Metadata plugin reloaded")

async def build_main_menu(user_id):
    metadata_on = await db.get_metadata(user_id)
    current = "On" if metadata_on else "Off"

    title = await db.get_title(user_id)
    author = await db.get_author(user_id)
    artist = await db.get_artist(user_id)
    video = await db.get_video(user_id)
    audio = await db.get_audio(user_id)
    subtitle = await db.get_subtitle(user_id)

    text = f"""
**㊋ Your Metadata is currently: {current}**

**◈ Title ▹** `{title if title else 'Not found'}`
**◈ Author ▹** `{author if author else 'Not found'}`
**◈ Artist ▹** `{artist if artist else 'Not found'}`
**◈ Audio ▹** `{audio if audio else 'Not found'}`
**◈ Subtitle ▹** `{subtitle if subtitle else 'Not found'}`
**◈ Video ▹** `{video if video else 'Not found'}`
    """

    buttons = [
        [
            InlineKeyboardButton(f"On{' ✅' if metadata_on else ''}", callback_data='on_metadata'),
            InlineKeyboardButton(f"Off{' ✅' if not metadata_on else ''}", callback_data='off_metadata')
        ],
        [InlineKeyboardButton("Set/Change Metadata", callback_data="metainfo")]
    ]
    return text, InlineKeyboardMarkup(buttons)

async def build_field_menu(user_id, meta_type):
    getters = {
        "title": db.get_title, "author": db.get_author, "artist": db.get_artist,
        "audio": db.get_audio, "subtitle": db.get_subtitle, "video": db.get_video
    }
    meta_value = await getters[meta_type](user_id)

    text = f"""
**Set your metadata for {meta_type.capitalize()}!**

Your current value: `{meta_value if meta_value else 'Not set'}`
    """

    buttons = [[InlineKeyboardButton("Set/Change", callback_data=f"set_{meta_type}")]]
    if meta_value:
        buttons.append([InlineKeyboardButton("Delete", callback_data=f"delete_{meta_type}")])

    if meta_type in ["audio", "subtitle"] and not meta_value:
        remove_getter = db.get_remove_audio_metadata if meta_type == "audio" else db.get_remove_subtitle_metadata
        remove_status = await remove_getter(user_id)
        status_emoji = " ✅" if remove_status else ""
        buttons.append([InlineKeyboardButton(f"Remove metadata{status_emoji}", callback_data=f"toggle_remove_{meta_type}")])

    buttons.append([InlineKeyboardButton("Back", callback_data="metainfo")])
    return text, InlineKeyboardMarkup(buttons)

@Client.on_message(filters.command("metadata"))
async def metadata(client, message):
    user_id = message.from_user.id
    logger.info(f"User {user_id} used /metadata")
    text, markup = await build_main_menu(user_id)
    await message.reply_text(text=text, reply_markup=markup, disable_web_page_preview=True)

@Client.on_callback_query(filters.regex(r"on_metadata|off_metadata|metainfo|meta_(title|author|artist|audio|subtitle|video)|set_(title|author|artist|audio|subtitle|video)|delete_(title|author|artist|audio|subtitle|video)|toggle_remove_(audio|subtitle)|back_main|cancel_(title|author|artist|audio|subtitle|video)"))
async def metadata_callback(client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data
    logger.info(f"Callback {data} from user {user_id}")

    try:
        if data in ["on_metadata", "off_metadata"]:
            await db.set_metadata(user_id, data == "on_metadata")
            logger.info(f"Metadata toggled to {'On' if data == 'on_metadata' else 'Off'}")
            text, markup = await build_main_menu(user_id)
            await query.message.edit_text(text=text, reply_markup=markup, disable_web_page_preview=True)
            return

        if data == "metainfo":
            buttons = [
                [InlineKeyboardButton("Title", callback_data="meta_title"), InlineKeyboardButton("Author", callback_data="meta_author")],
                [InlineKeyboardButton("Artist", callback_data="meta_artist"), InlineKeyboardButton("Audio", callback_data="meta_audio")],
                [InlineKeyboardButton("Subtitle", callback_data="meta_subtitle"), InlineKeyboardButton("Video", callback_data="meta_video")],
                [InlineKeyboardButton("Back", callback_data="back_main")]
            ]
            await query.message.edit_text(
                text="**Select a metadata type to set or change:**",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return

        if data == "back_main":
            text, markup = await build_main_menu(user_id)
            await query.message.edit_text(text=text, reply_markup=markup, disable_web_page_preview=True)
            return

        if data.startswith("meta_"):
            meta_type = data.split("_")[1]
            text, markup = await build_field_menu(user_id, meta_type)
            await query.message.edit_text(text=text, reply_markup=markup)
            return

        if data.startswith("toggle_remove_"):
            meta_type = data.split("_")[-1]
            getter = db.get_remove_audio_metadata if meta_type == "audio" else db.get_remove_subtitle_metadata
            setter = db.set_remove_audio_metadata if meta_type == "audio" else db.set_remove_subtitle_metadata
            current = await getter(user_id)
            await setter(user_id, not current)
            logger.info(f"Remove {meta_type} toggled to {not current}")

            text, markup = await build_field_menu(user_id, meta_type)
            await query.message.edit_text(text=text, reply_markup=markup)
            return

        if data.startswith("set_"):
            meta_type = data.split("_")[1]
            current_value = await {
                "title": db.get_title, "author": db.get_author, "artist": db.get_artist,
                "audio": db.get_audio, "subtitle": db.get_subtitle, "video": db.get_video
            }[meta_type](user_id)

            text = f"""
**Set your metadata for {meta_type.capitalize()}!**

__Please reply to this message with the new value.__
Example: [TG: @Animes_Guy]

**Current value**: `{current_value if current_value else 'Not set'}`
**Timeout: 30 seconds...**
            """
            buttons = [[InlineKeyboardButton("Cancel", callback_data=f"cancel_{meta_type}")]]
            prompt = await query.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))

            user_states[user_id] = {
                "state": f"set_{meta_type}",
                "prompt_message_id": prompt.id,
                "menu_message_id": query.message.id
            }
            asyncio.create_task(timeout_handler(client, user_id, meta_type, current_value))
            return

        if data.startswith("cancel_"):
            meta_type = data.split("_")[1]
            if user_id in user_states:
                del user_states[user_id]
            text, markup = await build_field_menu(user_id, meta_type)
            await query.message.edit_text(text=text, reply_markup=markup)
            return

        if data.startswith("delete_"):
            meta_type = data.split("_")[1]
            delete_funcs = {
                "title": db.delete_title, "author": db.delete_author, "artist": db.delete_artist,
                "audio": db.delete_audio, "subtitle": db.delete_subtitle, "video": db.delete_video
            }
            await delete_funcs[meta_type](user_id)
            logger.info(f"{meta_type.capitalize()} deleted for user {user_id}")
            await query.message.edit_text(
                f"**✅ {meta_type.capitalize()} metadata deleted!**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="metainfo")]])
            )
            return

    except MessageNotModified:
        logger.debug(f"Message not modified for {data} - ignoring (same content)")
        # Silently ignore - common when button state doesn't change visually
    except Exception as e:
        logger.error(f"Error in callback {data} for user {user_id}: {e}", exc_info=True)
        await query.answer("An error occurred. Please try again.", show_alert=True)

# timeout_handler and handle_metadata_input remain exactly as in the previous fixed version I sent

async def timeout_handler(client, user_id, meta_type, old_value):
    await asyncio.sleep(30)
    if user_id not in user_states or user_states[user_id]["state"] != f"set_{meta_type}":
        return
    try:
        await client.delete_messages(user_id, user_states[user_id]["prompt_message_id"])
        del user_states[user_id]
        text, markup = await build_field_menu(user_id, meta_type)
        await client.edit_message_text(user_id, user_states[user_id]["menu_message_id"], text=text, reply_markup=markup)
        await client.send_message(user_id, "**⏰ Timeout! Metadata setting cancelled.**")
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Timeout handler error: {e}")

@Client.on_message(filters.private & filters.text & filters.reply)
async def handle_metadata_input(client, message):
    user_id = message.from_user.id
    if user_id not in user_states or not user_states[user_id]["state"].startswith("set_"):
        return
    if message.reply_to_message.id != user_states[user_id]["prompt_message_id"]:
        return

    meta_type = user_states[user_id]["state"].split("_")[1]
    value = message.text.strip()
    if not value:
        await message.reply_text("**❌ Value cannot be empty!**")
        return

    set_funcs = {
        "title": db.set_title, "author": db.set_author, "artist": db.set_artist,
        "audio": db.set_audio, "subtitle": db.set_subtitle, "video": db.set_video
    }
    try:
        await set_funcs[meta_type](user_id, value)
        del user_states[user_id]
        await message.reply_text(f"**✅ {meta_type.capitalize()} saved!**")
        text, markup = await build_field_menu(user_id, meta_type)
        await client.edit_message_text(user_id, user_states[user_id]["menu_message_id"], text=text, reply_markup=markup)
    except Exception as e:
        logger.error(f"Save error for {meta_type}: {e}")
        await message.reply_text("**❌ Failed to save. Try again.**")
