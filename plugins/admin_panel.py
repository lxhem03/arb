from config import Config, Txt
from helper.database import codeflixbots
from pyrogram.types import Message
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
import os
import sys
import time
import asyncio
import logging
import datetime
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ADMIN_USER_ID = Config.ADMIN

# Flag to prevent multiple restarts
is_restarting = False

@Client.on_message(filters.private & filters.command("restart") & filters.user(ADMIN_USER_ID))
async def restart_bot(client: Client, message: Message):
    global is_restarting

    if is_restarting:
        return await message.reply_text("**Bot is already restarting...**")

    is_restarting = True
    await message.reply_text("**Restarting bot... Please wait.**")

    try:
        # Gracefully stop the bot
        await client.stop()  # ← This was the fix: await here!

        # Small delay to ensure everything is cleaned up
        await asyncio.sleep(2)

        # Restart the process
        logger.info("Bot is restarting...")
        os.execl(sys.executable, sys.executable, *sys.argv)

    except Exception as e:
        logger.error(f"Error during restart: {e}")
        is_restarting = False
        await message.reply_text(f"**Restart failed: {e}**")

@Client.on_message(filters.private & filters.command("tutorial"))
async def tutorial(bot: Client, message: Message):
    user_id = message.from_user.id
    format_template = await codeflixbots.get_format_template(user_id)
    await message.reply_text(
        text=Txt.FILE_NAME_TXT.format(format_template=format_template),
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("• ᴏᴡɴᴇʀ", url="https://t.me/cosmic_freak"),
             InlineKeyboardButton("• ᴛᴜᴛᴏʀɪᴀʟ", url="https://t.me/codeflix_bots")]
        ])
    )


@Client.on_message(filters.command(["stats", "status"]) & filters.user(Config.ADMIN))
async def get_stats(bot, message):
    total_users = await codeflixbots.total_users_count()
    uptime = time.strftime("%Hh%Mm%Ss", time.gmtime(time.time() - bot.uptime))    
    start_t = time.time()
    st = await message.reply('**Accessing The Details.....**')    
    end_t = time.time()
    time_taken_s = (end_t - start_t) * 1000
    await st.edit(text=f"**--Bot Status--** \n\n**⌚️ Bot Uptime :** {uptime} \n**🐌 Current Ping :** `{time_taken_s:.3f} ms` \n**👭 Total Users :** `{total_users}`")

@Client.on_message(filters.command("broadcast") & filters.user(Config.ADMIN) & filters.reply)
async def broadcast_handler(bot: Client, m: Message):
    await bot.send_message(Config.LOG_CHANNEL, f"{m.from_user.mention} or {m.from_user.id} Is Started The Broadcast......")
    all_users = await codeflixbots.get_all_users()
    broadcast_msg = m.reply_to_message
    sts_msg = await m.reply_text("Broadcast Started..!") 
    done = 0
    failed = 0
    success = 0
    start_time = time.time()
    total_users = await codeflixbots.total_users_count()
    async for user in all_users:
        sts = await send_msg(user['_id'], broadcast_msg)
        if sts == 200:
           success += 1
        else:
           failed += 1
        if sts == 400:
           await codeflixbots.delete_user(user['_id'])
        done += 1
        if not done % 20:
           await sts_msg.edit(f"Broadcast In Progress: \n\nTotal Users {total_users} \nCompleted : {done} / {total_users}\nSuccess : {success}\nFailed : {failed}")
    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
    await sts_msg.edit(f"Bʀᴏᴀᴅᴄᴀꜱᴛ Cᴏᴍᴩʟᴇᴛᴇᴅ: \nCᴏᴍᴩʟᴇᴛᴇᴅ Iɴ `{completed_in}`.\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nFailed: {failed}")
           
async def send_msg(user_id, message):
    try:
        await message.copy(chat_id=int(user_id))
        return 200
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return send_msg(user_id, message)
    except InputUserDeactivated:
        logger.info(f"{user_id} : Deactivated")
        return 400
    except UserIsBlocked:
        logger.info(f"{user_id} : Blocked The Bot")
        return 400
    except PeerIdInvalid:
        logger.info(f"{user_id} : User ID Invalid")
        return 400
    except Exception as e:
        logger.error(f"{user_id} : {e}")
        return 500


# ══════════════════════════ /update ══════════════════════════════════════════
@Client.on_message(filters.private & filters.command("update") & filters.user(ADMIN_USER_ID))
async def update_bot(client: Client, message: Message):
    """
    Pull latest commits from UPSTREAM_REPO / UPSTREAM_BRANCH and restart the bot.
    """
    repo   = Config.UPSTREAM_REPO
    branch = Config.UPSTREAM_BRANCH

    if not repo:
        return await message.reply_text(
            "❌ **`UPSTREAM_REPO` is not set in config.**\n"
            "Add it to your environment variables and restart."
        )

    status = await message.reply_text(
        f"🔄 **Checking for updates...**\n`{repo}` → `{branch}`"
    )

    # ── 1. set / update the upstream remote ───────────────────────────────
    set_remote = await asyncio.create_subprocess_exec(
        "git", "remote", "set-url", "upstream", repo,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, err = await set_remote.communicate()
    if set_remote.returncode != 0:
        # Remote may not exist yet — add it
        add_remote = await asyncio.create_subprocess_exec(
            "git", "remote", "add", "upstream", repo,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, err = await add_remote.communicate()
        if add_remote.returncode != 0:
            return await status.edit_text(
                f"❌ **Failed to set upstream remote:**\n`{err.decode().strip()}`"
            )

    # ── 2. fetch from upstream ────────────────────────────────────────────
    fetch_proc = await asyncio.create_subprocess_exec(
        "git", "fetch", "upstream",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, fetch_err = await fetch_proc.communicate()
    if fetch_proc.returncode != 0:
        return await status.edit_text(
            f"❌ **git fetch failed:**\n`{fetch_err.decode().strip()}`"
        )

    # ── 3. check how many commits we are behind ───────────────────────────
    log_proc = await asyncio.create_subprocess_exec(
        "git", "log", f"HEAD..upstream/{branch}", "--oneline",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    log_out, _ = await log_proc.communicate()
    commits_behind = log_out.decode().strip()

    if not commits_behind:
        return await status.edit_text("✅ **Bot is already up to date. No new commits.**")

    commit_lines   = commits_behind.splitlines()
    commit_count   = len(commit_lines)
    commit_preview = "\n".join(f"• `{c}`" for c in commit_lines[:10])
    if commit_count > 10:
        commit_preview += f"\n_...and {commit_count - 10} more_"

    await status.edit_text(
        f"📦 **{commit_count} new commit(s) found:**\n\n{commit_preview}\n\n"
        f"⬇️ **Pulling changes from `{branch}`...**"
    )

    # ── 4. merge upstream into current HEAD ───────────────────────────────
    pull_proc = await asyncio.create_subprocess_exec(
        "git", "pull", "upstream", branch,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    pull_out, pull_err = await pull_proc.communicate()
    pull_text = pull_out.decode().strip() or pull_err.decode().strip()

    if pull_proc.returncode != 0:
        return await status.edit_text(
            f"❌ **git pull failed:**\n`{pull_text}`"
        )

    # ── 5. install any new/changed dependencies ───────────────────────────
    await status.edit_text("📦 **Installing/updating dependencies...**")
    pip_proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "pip", "install", "-r", "requirements.txt",
        "--quiet", "--break-system-packages",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, pip_err = await pip_proc.communicate()
    if pip_proc.returncode != 0:
        logger.warning(f"pip install warning: {pip_err.decode().strip()}")

    # ── 6. restart ────────────────────────────────────────────────────────
    await status.edit_text(
        f"✅ **Update successful!** Pulled {commit_count} commit(s) from `{branch}`.\n"
        f"🔁 **Restarting bot...**"
    )
    await asyncio.sleep(1)
    logger.info("Restarting after update...")
    os.execl(sys.executable, sys.executable, *sys.argv)
