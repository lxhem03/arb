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


@Client.on_callback_query(filters.regex(r"on_metadata|off_metadata|metainfo|meta_(title|author|artist|audio|subtitle|video)|set_(title|author|artist|audio|subtitle|video)|delete_(title|author|artist|audio|subtitle|video)|back_(main|types)"))
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
        user_states[user_id] = {"state": f"set_{meta_type}", "message_id": query.message.id}
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

For example: [TG: @Animes_Guy]

Your current value: `{meta_value if meta_value else 'Not set'}`
Timeout: 30 seconds...
        """
        buttons = [
            [InlineKeyboardButton("Cancel", callback_data=f"meta_{meta_type}")]
        ]
        await query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))

        # Wait for user input with timeout
        try:
            message = await client.wait_for_message(
                chat_id=user_id,
                filters=filters.text & filters.private,
                timeout=30
            )
            value = message.text
            set_functions = {
                "title": db.set_title,
                "author": db.set_author,
                "artist": db.set_artist,
                "audio": db.set_audio,
                "subtitle": db.set_subtitle,
                "video": db.set_video
            }
            await set_functions[meta_type](user_id, value)
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
                message_id=user_states[user_id]["message_id"],
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except asyncio.TimeoutError:
            del user_states[user_id]  # Clear state
            await query.message.reply_text("**⏰ Timeout! Metadata setting cancelled.**")
            await client.edit_message_text(
                chat_id=user_id,
                message_id=user_states[user_id]["message_id"],
                text=f"**Set your metadata for {meta_type.capitalize()}!**\n\nYour current value: `{meta_value if meta_value else 'Not set'}`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Set/Change", callback_data=f"set_{meta_type}")],
                    [InlineKeyboardButton("Back", callback_data="metainfo")]
                ])
            )
        except Exception as e:
            logger.error(f"Error setting metadata for user {user_id}: {e}")
            del user_states[user_id]  # Clear state
            await query.message.reply_text("**❌ Error setting metadata. Try again.**")
            await client.edit_message_text(
                chat_id=user_id,
                message_id=user_states[user_id]["message_id"],
                text=f"**Set your metadata for {meta_type.capitalize()}!**\n\nYour current value: `{meta_value if meta_value else 'Not set'}`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Set/Change", callback_data=f"set_{meta_type}")],
                    [InlineKeyboardButton("Back", callback_data="metainfo")]
                ])
            )
        return

    # Handle delete metadata
    if data.startswith("delete_"):
        meta_type = data.split("_")[1]
        # Map metadata types to delete functions
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
