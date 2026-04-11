# plugins/settings.py — unified /settings command
import logging
from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from pyrogram.errors import MessageNotModified
from helper.database import codeflixbots

logger = logging.getLogger(__name__)


# ══════════════════════════ HELPERS ══════════════════════════════════════════
def _yn(val: bool) -> str:
    return "✅ On" if val else "❌ Off"

def _set_not(val) -> str:
    return "✅ Set" if val else "❌ Not Set"

def _mode_label(mode: str) -> str:
    return {'filename': '📄 Filename', 'caption': '💬 Caption', 'both': '🔀 Both'}.get(mode, mode)

def _type_label(t: str) -> str:
    return {'media': '🎬 Media', 'document': '📁 Document'}.get(t, t)


async def _build_settings(user_id: int, user_mention: str):
    thumb       = await codeflixbots.get_thumbnail(user_id)
    meta        = await codeflixbots.get_metadata(user_id)
    dump        = await codeflixbots.get_dump_channel(user_id)
    mode        = await codeflixbots.get_rename_mode(user_id)
    upload_type = await codeflixbots.get_upload_type(user_id)

    text = (
        f"⚙️ **User Settings for {user_mention}**\n\n"
        f"📤 **Dump:** {_set_not(dump)}{f'  (`{dump}`)' if dump else ''}\n"
        f"🏷️ **Metadata:** {_yn(meta)}\n"
        f"🖼️ **Thumbnail:** {_set_not(thumb)}\n"
        f"📋 **Mode:** {_mode_label(mode)}\n"
        f"📦 **Upload Type:** {_type_label(upload_type)}"
    )
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 Dump",      callback_data="settings_goto_dump"),
            InlineKeyboardButton("🏷️ Metadata",  callback_data="settings_goto_metadata"),
        ],
        [
            InlineKeyboardButton("🖼️ Thumbnail", callback_data="settings_thumbnail"),
            InlineKeyboardButton("📋 Mode",       callback_data="settings_mode"),
        ],
        [
            InlineKeyboardButton("📦 Upload Type", callback_data="settings_uploadtype"),
        ],
    ])
    return text, buttons


# ══════════════════════════ /settings ════════════════════════════════════════
@Client.on_message(filters.private & filters.command("settings"))
async def settings_command(client: Client, message: Message):
    user_id      = message.from_user.id
    user_mention = message.from_user.mention
    text, markup = await _build_settings(user_id, user_mention)
    await message.reply_text(text, reply_markup=markup)


# ══════════════════════════ SETTINGS CALLBACKS ════════════════════════════════
@Client.on_callback_query(filters.regex(r"^settings_"))
async def settings_callback(client: Client, query: CallbackQuery):
    user_id      = query.from_user.id
    user_mention = query.from_user.mention
    data         = query.data

    # ── back to main settings ─────────────────────────────────────────────
    if data == "settings_back":
        text, markup = await _build_settings(user_id, user_mention)
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except MessageNotModified:
            pass
        await query.answer()
        return

    # ── Dump → redirect to /dump flow ─────────────────────────────────────
    if data == "settings_goto_dump":
        from plugins.dump import _build_dump_menu
        text, markup = await _build_dump_menu(user_id)
        # Add a Back button to return to settings
        rows = markup.inline_keyboard + [[
            InlineKeyboardButton("⬅️ Back to Settings", callback_data="settings_back")
        ]]
        try:
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(rows))
        except MessageNotModified:
            pass
        await query.answer()
        return

    # ── Metadata → redirect to /metadata flow ─────────────────────────────
    if data == "settings_goto_metadata":
        from plugins.metadata import build_main_menu
        text, markup = await build_main_menu(user_id)
        rows = markup.inline_keyboard + [[
            InlineKeyboardButton("⬅️ Back to Settings", callback_data="settings_back")
        ]]
        try:
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(rows))
        except MessageNotModified:
            pass
        await query.answer()
        return

    # ── Thumbnail ─────────────────────────────────────────────────────────
    if data == "settings_thumbnail":
        thumb = await codeflixbots.get_thumbnail(user_id)
        if thumb:
            text = (
                "🖼️ **Thumbnail**\n\n"
                "You have a custom thumbnail set."
            )
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👁️ View",   callback_data="settings_thumb_view"),
                    InlineKeyboardButton("🗑 Delete", callback_data="settings_thumb_delete"),
                ],
                [InlineKeyboardButton("⬅️ Back", callback_data="settings_back")],
            ])
        else:
            text = (
                "🖼️ **Thumbnail**\n\n"
                "You have no custom thumbnail set.\n\n"
                "To set one, send a photo to the bot and reply to it with `/setthumb`."
            )
            markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data="settings_back")
            ]])
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except MessageNotModified:
            pass
        await query.answer()
        return

    if data == "settings_thumb_view":
        thumb = await codeflixbots.get_thumbnail(user_id)
        if thumb:
            await query.answer()
            await client.send_photo(user_id, thumb, caption="🖼️ **Your current thumbnail**")
        else:
            await query.answer("No thumbnail set.", show_alert=True)
        return

    if data == "settings_thumb_delete":
        await codeflixbots.set_thumbnail(user_id, file_id=None)
        await query.answer("✅ Thumbnail deleted.", show_alert=False)
        # Refresh thumbnail submenu
        text = (
            "🖼️ **Thumbnail**\n\n"
            "No custom thumbnail set.\n\n"
            "To set one, send a photo to the bot and reply to it with `/setthumb`."
        )
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Back", callback_data="settings_back")
        ]])
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except MessageNotModified:
            pass
        return

    # ── Mode ─────────────────────────────────────────────────────────────
    if data == "settings_mode":
        current = await codeflixbots.get_rename_mode(user_id)
        text = (
            "📋 **Rename Mode**\n\n"
            "Choose where the bot looks for episode/season/quality info:\n\n"
            "• **Filename** — reads from the file name only\n"
            "• **Caption** — reads from the message caption only\n"
            "• **Both** — checks filename first, then caption for anything missing\n\n"
            f"**Current mode:** {_mode_label(current)}"
        )
        def _check(m): return " ✅" if m == current else ""
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"📄 Filename{_check('filename')}", callback_data="settings_mode_filename"),
                InlineKeyboardButton(f"💬 Caption{_check('caption')}",   callback_data="settings_mode_caption"),
            ],
            [
                InlineKeyboardButton(f"🔀 Both{_check('both')}",         callback_data="settings_mode_both"),
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="settings_back")],
        ])
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except MessageNotModified:
            pass
        await query.answer()
        return

    if data.startswith("settings_mode_"):
        new_mode = data.split("settings_mode_")[1]   # filename | caption | both
        await codeflixbots.set_rename_mode(user_id, new_mode)
        await query.answer(f"✅ Mode set to {_mode_label(new_mode)}", show_alert=False)
        # Refresh mode submenu
        current = new_mode
        text = (
            "📋 **Rename Mode**\n\n"
            "Choose where the bot looks for episode/season/quality info:\n\n"
            "• **Filename** — reads from the file name only\n"
            "• **Caption** — reads from the message caption only\n"
            "• **Both** — checks filename first, then caption for anything missing\n\n"
            f"**Current mode:** {_mode_label(current)}"
        )
        def _check(m): return " ✅" if m == current else ""
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"📄 Filename{_check('filename')}", callback_data="settings_mode_filename"),
                InlineKeyboardButton(f"💬 Caption{_check('caption')}",   callback_data="settings_mode_caption"),
            ],
            [
                InlineKeyboardButton(f"🔀 Both{_check('both')}",         callback_data="settings_mode_both"),
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="settings_back")],
        ])
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except MessageNotModified:
            pass
        return

    # ── Upload Type ────────────────────────────────────────────────────────
    if data == "settings_uploadtype":
        current = await codeflixbots.get_upload_type(user_id)
        text = (
            "📦 **Upload Type**\n\n"
            "Choose how renamed files are sent to you:\n\n"
            "• **Media** — sent as a streamable video (Telegram player)\n"
            "• **Document** — sent as a raw file (no compression)\n\n"
            "_Note: audio files and non-video documents are always sent as documents "
            "regardless of this setting._\n\n"
            f"**Current type:** {_type_label(current)}"
        )
        def _check(t): return " ✅" if t == current else ""
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🎬 Media{_check('media')}",       callback_data="settings_type_media"),
                InlineKeyboardButton(f"📁 Document{_check('document')}", callback_data="settings_type_document"),
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="settings_back")],
        ])
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except MessageNotModified:
            pass
        await query.answer()
        return

    if data.startswith("settings_type_"):
        new_type = data.split("settings_type_")[1]   # media | document
        await codeflixbots.set_upload_type(user_id, new_type)
        await query.answer(f"✅ Upload type set to {_type_label(new_type)}", show_alert=False)
        current = new_type
        text = (
            "📦 **Upload Type**\n\n"
            "Choose how renamed files are sent to you:\n\n"
            "• **Media** — sent as a streamable video (Telegram player)\n"
            "• **Document** — sent as a raw file (no compression)\n\n"
            "_Note: audio files and non-video documents are always sent as documents "
            "regardless of this setting._\n\n"
            f"**Current type:** {_type_label(current)}"
        )
        def _check(t): return " ✅" if t == current else ""
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🎬 Media{_check('media')}",       callback_data="settings_type_media"),
                InlineKeyboardButton(f"📁 Document{_check('document')}", callback_data="settings_type_document"),
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="settings_back")],
        ])
        try:
            await query.message.edit_text(text, reply_markup=markup)
        except MessageNotModified:
            pass
        return

    await query.answer()
