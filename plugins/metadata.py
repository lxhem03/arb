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

    # Fetch user metadata from the database
    current = await db.get_metadata(user_id)
    title = await db.get_title(user_id)
    author = await db.get_author(user_id)
    artist = await db.get_artist(user_id)
    video = await db.get_video(user_id)
    audio = await db.get_audio(user_id)
    subtitle = await db.get_subtitle(user_id)

    # Display the current metadata
    text = f"""
**㊋ Your Metadata is currently: {current}**

**◈ Title ▹** `{title if title else 'Not found'}`
**◈ Author ▹** `{author if author else 'Not found'}`
**◈ Artist ▹** `{artist if artist else 'Not found'}`
**◈ Audio ▹** `{audio if audio else 'Not found'}`
**◈ Subtitle ▹** `{subtitle if subtitle else 'Not found'}`
**◈ Video ▹** `{video if video else 'Not found'}`
    """

    # Inline buttons
    buttons = [
        [
            InlineKeyboardButton(f"On{' ✅' if current == 'On' else ''}", callback_data='on_metadata'),
            InlineKeyboardButton(f"Off{' ✅' if current == 'Off' else ''}", callback_data='off_metadata')
        ],
        [
            InlineKeyboardButton("Set/Change Metadata", callback_data="metainfo")
        ]
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await message.reply_text(text=text, reply_markup=keyboard, disable_web_page_preview=True)


@Client.on_callback_query(filters.regex(r"on_metadata|off_metadata|metainfo|meta_(title|author|artist|audio|subtitle|video)|set_(title|author|artist|audio|subtitle|video)|delete_(title|author|artist|audio|subtitle|video)|back_(main|types)|cancel_(title|author|artist|audio|subtitle|video)"))
async def metadata_callback(client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    # Handle On/Off metadata toggle
    if data in ["on_metadata", "off_metadata"]:
        await db.set_metadata(user_id, "On" if data == "on_metadata" else "Off")
        # Refresh metadata display
        current = await db.get_metadata(user_id)
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
                InlineKeyboardButton(f"On{' ✓' if current == 'On' else ''}", callback_data='on_metadata'),
                InlineKeyboardButton(f"Off{' ✓' if current == 'Off' else ''}", callback_data='off_metadata')
            ],
            [
                InlineKeyboardButton("Set/Change Metadata", callback_data="metainfo")
            ]
        ]
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
        return

    # Handle metadata type selection
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

    # Handle back to main metadata menu
    if data == "back_main":
        current = await db.get_metadata(user_id)
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
                InlineKeyboardButton(f"On{' ✓' if current == 'On' else ''}", callback_data='on_metadata'),
                InlineKeyboardButton(f"Off{' ✓' if current == 'Off' else ''}", callback_data='off_metadata')
            ],
            [
                InlineKeyboardButton("Set/Change Metadata", callback_data="metainfo")
            ]
        ]
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
        return

    # Handle metadata type selection (e.g., meta_title)
    if data.startswith("meta_"):
        meta_type = data.split("_")[1]
        meta_value = {
            "title": await db.get_title(user_id),
            "author": await db.get_author(user_id),
            "artist": await db.get_artist(user_id),
            "audio": await db.get_audio(user_id),
            "subtitle": await db.get_subtitle(user_id),
            "video": await db.get_video(user_id)
        }[meta_type]

        text = f"""
**Set your metadata for {meta_type.capitalize()}!**

Your current value: `{meta_value if meta_value else 'Not set'}`
        """
        buttons = [[InlineKeyboardButton("Set/Change", callback_data=f"set_{meta_type}")]]
        if meta_value:  # Add Delete button if metadata exists
            buttons.append([InlineKeyboardButton("Delete", callback_data=f"delete_{meta_type}")])
        buttons.append([InlineKeyboardButton("Back", callback_data="metainfo")])

        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))
        return

    # Handle set/change metadata
    if data.startswith("set_"):
        meta_type = data.split("_")[1]
        # Fetch the current metadata value
        meta_value = {
            "title": await db.get_title(user_id),
            "author": await db.get_author(user_id),
            "artist": await db.get_artist(user_id),
            "audio": await db.get_audio(user_id),
            "subtitle": await db.get_subtitle(user_id),
            "video": await db.get_video(user_id)
        }[meta_type]
        text = f"""
**Set your metadata for {meta_type.capitalize()}!**

__Please reply to this message with the new value.__
For example: [TG: @Animes_Guy]

__**Your current value**__: `{meta_value if meta_value else 'Not set'}`
**Timeout: 30 seconds...**
        """
        buttons = [
            [InlineKeyboardButton("Cancel", callback_data=f"cancel_{meta_type}")]
        ]
        prompt_message = await query.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))
        # Store both the prompt message ID and the original menu message ID
        user_states[user_id] = {
            "state": f"set_{meta_type}",
            "prompt_message_id": prompt_message.id,
            "menu_message_id": query.message.id
        }
        # Start timeout task
        asyncio.create_task(timeout_handler(client, user_id, meta_type, meta_value))
        return

    # Handle cancel
    if data.startswith("cancel_"):
        meta_type = data.split("_")[1]
        if user_id in user_states:
            del user_states[user_id]  # Clear state
        meta_value = {
            "title": await db.get_title(user_id),
            "author": await db.get_author(user_id),
            "artist": await db.get_artist(user_id),
            "audio": await db.get_audio(user_id),
            "subtitle": await db.get_subtitle(user_id),
            "video": await db.get_video(user_id)
        }[meta_type]
        text = f"""
**Set your metadata for {meta_type.capitalize()}!**

Your current value: `{meta_value if meta_value else 'Not set'}`
        """
        buttons = [[InlineKeyboardButton("Set/Change", callback_data=f"set_{meta_type}")]]
        if meta_value:
            buttons.append([InlineKeyboardButton("Delete", callback_data=f"delete_{meta_type}")])
        buttons.append([InlineKeyboardButton("Back", callback_data="metainfo")])
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))
        return

    # Handle delete metadata
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
                await query.message.edit_text(f"**✅ {meta_type.capitalize()} metadata deleted**", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Back", callback_data="metainfo")]
                ]))
            except Exception as e:
                logger.error(f"Error deleting {meta_type} for user {user_id}: {e}")
                await query.message.edit_text("**❌ Error deleting metadata. Try again.**", reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Back", callback_data="metainfo")]
                ]))
        return

    # Handle back to metadata type selection
    if data == "back_types":
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


async def timeout_handler(client, user_id, meta_type, meta_value):
    """Handle timeout for metadata input."""
    await asyncio.sleep(30)
    if user_id in user_states and user_states[user_id]["state"] == f"set_{meta_type}":
        try:
            # Delete the prompt message
            prompt_message_id = user_states[user_id]["prompt_message_id"]
            await client.delete_messages(chat_id=user_id, message_ids=prompt_message_id)            
            # Clear state
            menu_message_id = user_states[user_id]["menu_message_id"]
            del user_states[user_id]
            # Revert to metadata type menu
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

    # Check if the message is a reply to the correct prompt
    if message.reply_to_message.id != user_states[user_id]["prompt_message_id"]:
        return

    meta_type = user_states[user_id]["state"].split("_")[1]
    value = message.text.strip()
    if not value:
        await message.reply_text("**❌ Input cannot be empty. Please reply with a valid value.**")
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
        menu_message_id = user_states[user_id]["menu_message_id"]
        del user_states[user_id]  # Clear state
        await message.reply_text(f"**✅ {meta_type.capitalize()} saved**")
        # Refresh metadata type menu
        meta_value = {
            "title": await db.get_title(user_id),
            "author": await db.get_author(user_id),
            "artist": await db.get_artist(user_id),
            "audio": await db.get_audio(user_id),
            "subtitle": await db.get_subtitle(user_id),
            "video": await db.get_video(user_id)
        }[meta_type]
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
    except Exception as e:
        logger.error(f"Error setting {meta_type} for user {user_id}: {e}")
        await message.reply_text("**❌ Error setting metadata. Try again.**")
        # Revert to metadata type menu
        menu_message_id = user_states[user_id]["menu_message_id"]
        del user_states[user_id]  # Clear state
        meta_value = {
            "title": await db.get_title(user_id),
            "author": await db.get_author(user_id),
            "artist": await db.get_artist(user_id),
            "audio": await db.get_audio(user_id),
            "subtitle": await db.get_subtitle(user_id),
            "video": await db.get_video(user_id)
        }[meta_type]
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
