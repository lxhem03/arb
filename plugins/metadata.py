from helper.database import codeflixbots as db
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from config import Txt
import asyncio
import logging

# State dictionary to track user input state
user_states = {}

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@Client.on_message(filters.command("metadata"))
async def metadata(client, message):
    user_id = message.from_user.id

    # Fetch current status and values
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
        [
            InlineKeyboardButton("Set/Change Metadata", callback_data="metainfo")
        ]
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await message.reply_text(text=text, reply_markup=keyboard, disable_web_page_preview=True)


@Client.on_callback_query(filters.regex(r"on_metadata|off_metadata|metainfo|meta_(title|author|artist|audio|subtitle|video)|set_(title|author|artist|audio|subtitle|video)|delete_(title|author|artist|audio|subtitle|video)|toggle_remove_(audio|subtitle)|back_main|cancel_(title|author|artist|audio|subtitle|video)"))
async def metadata_callback(client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    # Toggle On/Off
    if data in ["on_metadata", "off_metadata"]:
        await db.set_metadata(user_id, data == "on_metadata")
        await metadata(client, query.message)  # Refresh full menu
        return

    # Select metadata type
    if data == "metainfo":
        buttons = [
            [
                InlineKeyboardButton("Title", callback_data="meta_title"),
                InlineKeyboardButton("Author", callback_data="meta_author")
            ],
            [
                InlineKeyboardButton("Artist", callback_data="meta_artist"),
                InlineKeyboardButton("Audio", callback_data="meta_audio")
            ],
            [
                InlineKeyboardButton("Subtitle", callback_data="meta_subtitle"),
                InlineKeyboardButton("Video", callback_data="meta_video")
            ],
            [
                InlineKeyboardButton("Back", callback_data="back_main")
            ]
        ]
        await query.message.edit_text(
            text="**Select a metadata type to set or change:**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    # Back to main menu
    if data == "back_main":
        await metadata(client, query.message)
        return

    # Individual metadata field view
    if data.startswith("meta_"):
        meta_type = data.split("_")[1]
        getters = {
            "title": db.get_title,
            "author": db.get_author,
            "artist": db.get_artist,
            "audio": db.get_audio,
            "subtitle": db.get_subtitle,
            "video": db.get_video
        }
        meta_value = await getters[meta_type](user_id)

        text = f"""
**Set your metadata for {meta_type.capitalize()}!**

Your current value: `{meta_value if meta_value else 'Not set'}`
        """

        buttons = [[InlineKeyboardButton("Set/Change", callback_data=f"set_{meta_type}")]]
        if meta_value:
            buttons.append([InlineKeyboardButton("Delete", callback_data=f"delete_{meta_type}")])

        # Special button: Only for audio/subtitle AND when no custom value is set
        if meta_type in ["audio", "subtitle"] and not meta_value:
            remove_getter = db.get_remove_audio_metadata if meta_type == "audio" else db.get_remove_subtitle_metadata
            current_remove = await remove_getter(user_id)
            status = " ✅" if current_remove else ""
            buttons.append([InlineKeyboardButton(f"Remove metadata{status}", callback_data=f"toggle_remove_{meta_type}")])

        buttons.append([InlineKeyboardButton("Back", callback_data="metainfo")])

        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))
        return

    # Toggle Remove Metadata (only audio/subtitle)
    if data.startswith("toggle_remove_"):
        meta_type = data.split("_")[-1]
        if meta_type == "audio":
            current = await db.get_remove_audio_metadata(user_id)
            await db.set_remove_audio_metadata(user_id, not current)
        elif meta_type == "subtitle":
            current = await db.get_remove_subtitle_metadata(user_id)
            await db.set_remove_subtitle_metadata(user_id, not current)

        # Refresh the current field page
        await metadata_callback(client, query)  # Re-process same callback to refresh
        return

    # Set/Change prompt
    if data.startswith("set_"):
        meta_type = data.split("_")[1]
        getters = {
            "title": db.get_title,
            "author": db.get_author,
            "artist": db.get_artist,
            "audio": db.get_audio,
            "subtitle": db.get_subtitle,
            "video": db.get_video
        }
        meta_value = await getters[meta_type](user_id)

        text = f"""
**Set your metadata for {meta_type.capitalize()}!**

__Please reply to this message with the new value.__
For example: [TG: @Animes_Guy]

__**Your current value**__: `{meta_value if meta_value else 'Not set'}`
**Timeout: 30 seconds...**
        """
        buttons = [[InlineKeyboardButton("Cancel", callback_data=f"cancel_{meta_type}")]]
        prompt_message = await query.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))

        user_states[user_id] = {
            "state": f"set_{meta_type}",
            "prompt_message_id": prompt_message.id,
            "menu_message_id": query.message.id
        }
        asyncio.create_task(timeout_handler(client, user_id, meta_type, meta_value))
        return

    # Cancel setting
    if data.startswith("cancel_"):
        meta_type = data.split("_")[1]
        if user_id in user_states:
            del user_states[user_id]
        # Refresh field page
        await metadata_callback(client, query)  # Simulate going back to meta_ page
        return

    # Delete metadata value
    if data.startswith("delete_"):
        meta_type = data.split("_")[1]
        delete_functions = {
            "title": db.delete_title,
            "author": db.delete_author,
            "artist": db.delete_artist,
            "audio": db.delete_audio,
            "subtitle": db.delete_subtitle,
            "video": db.delete_video
        }
        if meta_type in delete_functions:
            try:
                await delete_functions[meta_type](user_id)
                await query.message.edit_text(
                    f"**✅ {meta_type.capitalize()} metadata deleted**",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="metainfo")]])
                )
            except Exception as e:
                logger.error(f"Error deleting {meta_type} for user {user_id}: {e}")
                await query.message.edit_text("**❌ Error deleting metadata.**")
        return


async def timeout_handler(client, user_id, meta_type, meta_value):
    await asyncio.sleep(30)
    if user_id in user_states and user_states[user_id]["state"] == f"set_{meta_type}":
        try:
            await client.delete_messages(chat_id=user_id, message_ids=user_states[user_id]["prompt_message_id"])
            del user_states[user_id]

            menu_message_id = user_states[user_id]["menu_message_id"]  # Already deleted above
            text = f"""
**Set your metadata for {meta_type.capitalize()}!**

Your current value: `{meta_value if meta_value else 'Not set'}`
            """
            buttons = [[InlineKeyboardButton("Set/Change", callback_data=f"set_{meta_type}")]]
            if meta_value:
                buttons.append([InlineKeyboardButton("Delete", callback_data=f"delete_{meta_type}")])
            buttons.append([InlineKeyboardButton("Back", callback_data="metainfo")])
            await client.edit_message_text(
                chat_id=user_id,
                message_id=menu_message_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            await client.send_message(user_id, "**⏰ Timeout! Metadata setting cancelled.**")
        except Exception as e:
            logger.error(f"Error in timeout handler for user {user_id}: {e}")


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
        await message.reply_text("**❌ Input cannot be empty.**")
        return

    set_functions = {
        "title": db.set_title,
        "author": db.set_author,
        "artist": db.set_artist,
        "audio": db.set_audio,
        "subtitle": db.set_subtitle,
        "video": db.set_video
    }
    try:
        await set_functions[meta_type](user_id, value)
        del user_states[user_id]
        await message.reply_text(f"**✅ {meta_type.capitalize()} saved**")

        # Refresh menu
        new_value = await set_functions[meta_type](user_id, value)  # Just to get updated
        new_value = {
            "title": await db.get_title(user_id),
            "author": await db.get_author(user_id),
            "artist": await db.get_artist(user_id),
            "audio": await db.get_audio(user_id),
            "subtitle": await db.get_subtitle(user_id),
            "video": await db.get_video(user_id)
        }[meta_type]

        text = f"""
**Set your metadata for {meta_type.capitalize()}!**

Your current value: `{new_value if new_value else 'Not set'}`
        """
        buttons = [[InlineKeyboardButton("Set/Change", callback_data=f"set_{meta_type}")]]
        if new_value:
            buttons.append([InlineKeyboardButton("Delete", callback_data=f"delete_{meta_type}")])
        buttons.append([InlineKeyboardButton("Back", callback_data="metainfo")])
        await client.edit_message_text(
            chat_id=user_id,
            message_id=user_states[user_id]["menu_message_id"],
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        logger.error(f"Error saving {meta_type}: {e}")
        await message.reply_text("**❌ Error saving metadata.**")
