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
        return await send_msg(user_id, message)   # was missing await
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
import re as _re
import urllib.request as _urllib_request
import zipfile as _zipfile
import shutil as _shutil
import json as _json

def _parse_github_repo(repo_url: str):
    """
    Accepts any of:
      https://github.com/owner/repo
      https://github.com/owner/repo.git
      github.com/owner/repo
    Returns (owner, repo_name) or raises ValueError.
    """
    match = _re.search(r'github\.com[/:]([^/]+)/([^/\s]+?)(?:\.git)?$', repo_url.strip())
    if not match:
        raise ValueError(f"Cannot parse GitHub URL: {repo_url!r}")
    return match.group(1), match.group(2)


async def _run(cmd: list, env: dict = None):
    """Run a subprocess, return (returncode, stdout, stderr)."""
    import subprocess
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=full_env
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()


@Client.on_message(filters.private & filters.command("update") & filters.user(ADMIN_USER_ID))
async def update_bot(client: Client, message: Message):
    """
    Download the latest code from UPSTREAM_REPO / UPSTREAM_BRANCH via
    GitHub's zip archive API (no git auth / credentials needed — works on
    Heroku Docker where git HTTPS always fails without a credential store).

    Flow:
      1. Hit GitHub API → get latest commit SHA on the branch
      2. Compare with local HEAD SHA (if available) to detect changes
      3. Download branch zip → extract → overwrite local files
      4. pip install -r requirements.txt
      5. os.execl restart
    """
    repo_url = Config.UPSTREAM_REPO
    branch   = Config.UPSTREAM_BRANCH

    if not repo_url:
        return await message.reply_text(
            "❌ **`UPSTREAM_REPO` is not set in config.**\n"
            "Add it to your environment variables and restart."
        )

    try:
        owner, repo_name = _parse_github_repo(repo_url)
    except ValueError as e:
        return await message.reply_text(f"❌ **Invalid repo URL:**\n`{e}`")

    status = await message.reply_text(
        f"🔄 **Checking for updates...**\n"
        f"`{owner}/{repo_name}` → `{branch}`"
    )

    # ── 1. get latest commit SHA from GitHub API (no auth for public repos) ──
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}/commits/{branch}"
    try:
        def _fetch_sha():
            req = _urllib_request.Request(
                api_url,
                headers={"Accept": "application/vnd.github.v3+json",
                         "User-Agent": "TelegramBot-Updater"}
            )
            with _urllib_request.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read())
            return data["sha"], data["commit"]["message"].splitlines()[0]

        loop = asyncio.get_event_loop()
        remote_sha, commit_msg = await loop.run_in_executor(None, _fetch_sha)
    except Exception as e:
        return await status.edit_text(
            f"❌ **Failed to reach GitHub API:**\n`{e}`\n\n"
            f"Make sure `{owner}/{repo_name}` is a public repository."
        )

    # ── 2. compare with local HEAD (best-effort; skipped if not a git repo) ──
    rc, local_sha, _ = await _run(["git", "rev-parse", "HEAD"])
    if rc == 0 and local_sha and local_sha == remote_sha:
        return await status.edit_text(
            f"✅ **Already up to date.**\n"
            f"Local HEAD matches remote `{remote_sha[:7]}`."
        )

    short_sha = remote_sha[:7]
    await status.edit_text(
        f"📦 **New commit found:** `{short_sha}` — _{commit_msg}_\n\n"
        f"⬇️ **Downloading `{branch}` from GitHub...**"
    )

    # ── 3. download branch zip ────────────────────────────────────────────
    zip_url  = f"https://github.com/{owner}/{repo_name}/archive/refs/heads/{branch}.zip"
    zip_path = f"/tmp/update_{branch}.zip"
    extract_dir = f"/tmp/update_extract_{branch}"

    try:
        def _download_zip():
            req = _urllib_request.Request(
                zip_url,
                headers={"User-Agent": "TelegramBot-Updater"}
            )
            with _urllib_request.urlopen(req, timeout=60) as resp, \
                 open(zip_path, "wb") as f:
                _shutil.copyfileobj(resp, f)

        await loop.run_in_executor(None, _download_zip)
    except Exception as e:
        return await status.edit_text(f"❌ **Download failed:**\n`{e}`")

    # ── 4. extract and overwrite local files ─────────────────────────────
    await status.edit_text("📂 **Extracting and applying update...**")
    try:
        if os.path.exists(extract_dir):
            _shutil.rmtree(extract_dir)

        with _zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)

        # GitHub zips always have a top-level folder like "repo-branch/"
        extracted_root = os.path.join(
            extract_dir,
            f"{repo_name}-{branch}"
        )
        if not os.path.isdir(extracted_root):
            # Fallback: find the first subdirectory
            subdirs = [
                d for d in os.listdir(extract_dir)
                if os.path.isdir(os.path.join(extract_dir, d))
            ]
            if not subdirs:
                raise RuntimeError("Zip structure unexpected — no subdirectory found.")
            extracted_root = os.path.join(extract_dir, subdirs[0])

        bot_root = os.path.dirname(os.path.abspath(__file__))   # plugins/
        bot_root = os.path.dirname(bot_root)                     # project root

        # Copy every file from the zip, skipping .git and session files
        skip_exts    = {".session", ".session-journal"}
        skip_dirs    = {".git", "__pycache__"}
        files_copied = 0

        for dirpath, dirnames, filenames in os.walk(extracted_root):
            # Prune unwanted directories in-place
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]

            rel_dir = os.path.relpath(dirpath, extracted_root)
            dest_dir = os.path.join(bot_root, rel_dir) if rel_dir != "." else bot_root
            os.makedirs(dest_dir, exist_ok=True)

            for fname in filenames:
                if any(fname.endswith(ext) for ext in skip_exts):
                    continue
                src  = os.path.join(dirpath, fname)
                dest = os.path.join(dest_dir, fname)
                _shutil.copy2(src, dest)
                files_copied += 1

    except Exception as e:
        return await status.edit_text(f"❌ **Extraction/copy failed:**\n`{e}`")
    finally:
        # Clean up temp files regardless
        for path in (zip_path, extract_dir):
            try:
                if os.path.isdir(path):
                    _shutil.rmtree(path)
                elif os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    # ── 5. install any new/changed dependencies ───────────────────────────
    await status.edit_text(
        f"✅ **{files_copied} file(s) updated** from `{short_sha}`.\n"
        f"📦 **Installing dependencies...**"
    )
    rc, _, pip_err = await _run([
        sys.executable, "-m", "pip", "install", "-r", "requirements.txt",
        "--quiet", "--break-system-packages"
    ])
    if rc != 0:
        logger.warning(f"pip install warning: {pip_err}")

    # ── 6. restart ────────────────────────────────────────────────────────
    await status.edit_text(
        f"🎉 **Update complete!**\n"
        f"• Commit: `{short_sha}` — _{commit_msg}_\n"
        f"• Files updated: `{files_copied}`\n\n"
        f"🔁 **Restarting bot...**"
    )
    await asyncio.sleep(1)
    logger.info(f"Restarting after update to {short_sha}...")
    os.execl(sys.executable, sys.executable, *sys.argv)
