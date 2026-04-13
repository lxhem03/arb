import re, os, time
from os import environ, getenv
id_pattern = re.compile(r'^.\d+$') 


class Config(object):
    # pyro client config
    API_ID       = os.environ.get("API_ID", "")
    API_HASH     = os.environ.get("API_HASH", "")
    BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
    SESSION_NAME = os.environ.get("SESSION_NAME", "codeflixbots")

    # database config
    DB_NAME = os.environ.get("DB_NAME","")     
    DB_URL  = os.environ.get("DB_URL","")
    PORT = os.environ.get("PORT", "8080")
 
    # upstream update config
    UPSTREAM_REPO   = os.environ.get("UPSTREAM_REPO", "")
    UPSTREAM_BRANCH = os.environ.get("UPSTREAM_BRANCH", "main")

    # other configs
    BOT_UPTIME  = time.time()
    START_PIC   = os.environ.get("START_PIC", "https://graph.org/file/29a3acbbab9de5f45a5fe.jpg")
    ADMIN       = [int(admin) if id_pattern.search(admin) else admin for admin in os.environ.get('ADMIN', '7465574522').split()]
    FORCE_SUB_CHANNELS = os.environ.get('FORCE_SUB_CHANNELS', 'The_TGguy').split(',')
    LOG_CHANNEL  = int(os.environ.get("LOG_CHANNEL",  "-1002288135729"))
    DUMP_CHANNEL = int(os.environ.get("DUMP_CHANNEL", "0"))   # 0 = disabled
    
    # wes response configuration     
    WEBHOOK = bool(os.environ.get("WEBHOOK", "True"))


class Txt(object):
    # part of text configuration

    START_TXT = """<b>ʜᴇʏ! {}

» ɪ ᴀᴍ ᴀɴ ᴀᴅᴠᴀɴᴄᴇᴅ ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ʙᴏᴛ!

✦ ʀᴇɴᴀᴍᴇ ᴡɪᴛʜ sᴍᴀʀᴛ ᴘʟᴀᴄᴇʜᴏʟᴅᴇʀs
✦ ᴄᴜsᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ & ᴄᴀᴘᴛɪᴏɴ
✦ ᴍᴇᴛᴀᴅᴀᴛᴀ ᴇᴅɪᴛɪɴɢ ғᴏʀ ᴍᴋᴠ ғɪʟᴇs
✦ ᴅᴜᴍᴘ ᴄʜᴀɴɴᴇʟ sᴜᴘᴘᴏʀᴛ
✦ ǫᴜᴇᴜᴇ sʏsᴛᴇᴍ ᴡɪᴛʜ ᴄᴀɴᴄᴇʟ ʙᴜᴛᴛᴏɴ

ᴜsᴇ /help ᴛᴏ sᴇᴇ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs</b>"""

    FILE_NAME_TXT = """<b>» <u>ꜱᴇᴛᴜᴘ ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ꜰᴏʀᴍᴀᴛ</u></b>

<b>ᴘʟᴀᴄᴇʜᴏʟᴅᴇʀꜱ ʏᴏᴜ ᴄᴀɴ ᴜꜱᴇ:</b>

<code>{{episode}}</code>  — ᴇᴘɪꜱᴏᴅᴇ ɴᴜᴍʙᴇʀ
<code>{{season}}</code>   — ꜱᴇᴀꜱᴏɴ ɴᴜᴍʙᴇʀ
<code>{{quality}}</code>  — ᴠɪᴅᴇᴏ ǫᴜᴀʟɪᴛʏ ꜰʀᴏᴍ ꜱᴛʀᴇᴀᴍ (ᴇɢ. 1080ᴘ)
<code>{{resolution}}</code> — ǫᴜᴀʟɪᴛʏ ꜰʀᴏᴍ ꜰɪʟᴇɴᴀᴍᴇ
<code>{{audio}}</code>    — Sᴜʙ / Dᴜᴀʟ / Mᴜʟᴛɪ
<code>{{languages}}</code> — ᴀᴜᴅɪᴏ ʟᴀɴɢᴜᴀɢᴇs (ᴇɢ. Eɴɢʟɪꜱʜ, Jᴀᴘᴀɴᴇꜱᴇ)
<code>{{subtitles}}</code> — ꜱᴜʙᴛɪᴛʟᴇ ʟᴀɴɢᴜᴀɢᴇs
<code>{{codec}}</code>    — ᴠɪᴅᴇᴏ ᴄᴏᴅᴇᴄ (ᴇɢ. H.265, AV1)
<code>{{filesize}}</code> — ꜰɪʟᴇ ꜱɪᴢᴇ (ᴇɢ. 2.4 Gʙ)

<b>‣ ᴇxᴀᴍᴘʟᴇ:</b>
<code>/autorename Anime Name S{{season}}E{{episode}} [{{quality}} {{audio}} {{codec}}]</code>

<b>‣ ᴏᴜᴛᴘᴜᴛ:</b> <code>Anime Name S01E04 [1080p Dual H.265].mkv</code>

<i>ᴛɪᴘ: ᴜꜱᴇ /settings ᴛᴏ ᴄᴏɴᴛʀᴏʟ ᴡʜᴇᴛʜᴇʀ ᴘʟᴀᴄᴇʜᴏʟᴅᴇʀs ᴀʀᴇ ʀᴇᴀᴅ ꜰʀᴏᴍ ꜰɪʟᴇɴᴀᴍᴇ, ᴄᴀᴘᴛɪᴏɴ, ᴏʀ ʙᴏᴛʜ.</i>"""

    ABOUT_TXT = f"""<b>❍ ᴍʏ ɴᴀᴍᴇ : <a href="https://t.me/codeflix_bots">ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ</a>
❍ ᴅᴇᴠᴇʟᴏᴩᴇʀ : <a href="https://t.me/cosmic_freak">ʏᴀᴛᴏ</a>
❍ ɢɪᴛʜᴜʙ : <a href="https://github.com/cosmic_freak">ʏᴀᴛᴏ</a>
❍ ʟᴀɴɢᴜᴀɢᴇ : <a href="https://www.python.org/">ᴘʏᴛʜᴏɴ</a>
❍ ᴅᴀᴛᴀʙᴀꜱᴇ : <a href="https://www.mongodb.com/">ᴍᴏɴɢᴏ ᴅʙ</a>
❍ ʜᴏꜱᴛᴇᴅ ᴏɴ : <a href="https://t.me/codeflix_bots">ʜᴇʀᴏᴋᴜ</a>
❍ ᴍᴀɪɴ ᴄʜᴀɴɴᴇʟ : <a href="https://t.me/animes_cruise">ᴀɴɪᴍᴇ ᴄʀᴜɪsᴇ</a>

➻ ᴄʟɪᴄᴋ ᴏɴ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ꜰᴏʀ ʜᴇʟᴘ ᴀɴᴅ ɪɴꜰᴏ ᴀʙᴏᴜᴛ ᴍᴇ.</b>"""

    THUMBNAIL_TXT = """<b><u>» ᴛʜᴜᴍʙɴᴀɪʟ ꜱᴇᴛᴛɪɴɢꜱ</u></b>

<b>ʜᴏᴡ ᴛᴏ ꜱᴇᴛ ᴀ ᴛʜᴜᴍʙɴᴀɪʟ:</b>
➲ ꜱᴇɴᴅ ᴀ ᴘʜᴏᴛᴏ ᴛᴏ ᴛʜᴇ ʙᴏᴛ, ᴛʜᴇɴ ʀᴇᴘʟʏ ᴛᴏ ɪᴛ ᴡɪᴛʜ /setthumb

<b>ᴏᴛʜᴇʀ ᴄᴏᴍᴍᴀɴᴅꜱ:</b>
➲ /view_thumb — ᴠɪᴇᴡ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴛʜᴜᴍʙɴᴀɪʟ
➲ /del_thumb  — ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ᴛʜᴜᴍʙɴᴀɪʟ

<i>ɴᴏᴛᴇ: ɪꜰ ɴᴏ ᴛʜᴜᴍʙɴᴀɪʟ ɪꜱ ꜱᴀᴠᴇᴅ, ᴛʜᴇ ʙᴏᴛ ᴡɪʟʟ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴇxᴛʀᴀᴄᴛ ᴀ ꜰʀᴀᴍᴇ ꜰʀᴏᴍ ᴛʜᴇ ᴠɪᴅᴇᴏ ᴀꜱ ᴛʜᴜᴍʙɴᴀɪʟ.</i>"""

    CAPTION_TXT = """<b><u>» ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ</u></b>

<b>ᴘʟᴀᴄᴇʜᴏʟᴅᴇʀꜱ ꜰᴏʀ ᴄᴀᴘᴛɪᴏɴ:</b>
<code>{{filename}}</code>   — ꜰɪɴᴀʟ ʀᴇɴᴀᴍᴇᴅ ꜰɪʟᴇɴᴀᴍᴇ
<code>{{filesize}}</code>   — ꜰɪʟᴇ ꜱɪᴢᴇ
<code>{{audio}}</code>      — Sᴜʙ / Dᴜᴀʟ / Mᴜʟᴛɪ
<code>{{languages}}</code>  — ᴀᴜᴅɪᴏ ʟᴀɴɢᴜᴀɢᴇꜱ
<code>{{subtitles}}</code>  — ꜱᴜʙᴛɪᴛʟᴇ ʟᴀɴɢᴜᴀɢᴇꜱ
<code>{{quality}}</code>    — ᴠɪᴅᴇᴏ ǫᴜᴀʟɪᴛʏ
<code>{{codec}}</code>      — ᴠɪᴅᴇᴏ ᴄᴏᴅᴇᴄ
<code>{{episode}}</code>    — ᴇᴘɪꜱᴏᴅᴇ ɴᴜᴍʙᴇʀ
<code>{{season}}</code>     — ꜱᴇᴀꜱᴏɴ ɴᴜᴍʙᴇʀ

<b>ᴄᴏᴍᴍᴀɴᴅꜱ:</b>
➲ /set_caption  — ꜱᴇᴛ ᴄᴀᴘᴛɪᴏɴ
➲ /see_caption  — ᴠɪᴇᴡ ᴄᴀᴘᴛɪᴏɴ
➲ /del_caption  — ᴅᴇʟᴇᴛᴇ ᴄᴀᴘᴛɪᴏɴ

<b>‣ ᴇxᴀᴍᴘʟᴇ:</b>
<code>/set_caption 🎬 {{filename}}
📦 Size: {{filesize}} | 🎵 {{audio}} | 🔤 {{subtitles}}</code>"""

    PROGRESS_BAR = """\n
<b>» Size</b> : {1} | {2}
<b>» Done</b> : {0}%
<b>» Speed</b> : {3}/s
<b>» ETA</b> : {4} """

    DONATE_TXT = """<blockquote> ᴛʜᴀɴᴋs ғᴏʀ sʜᴏᴡɪɴɢ ɪɴᴛᴇʀᴇsᴛ ɪɴ ᴅᴏɴᴀᴛɪᴏɴ</blockquote>

<b><i>💞  ɪꜰ ʏᴏᴜ ʟɪᴋᴇ ᴏᴜʀ ʙᴏᴛ ꜰᴇᴇʟ ꜰʀᴇᴇ ᴛᴏ ᴅᴏɴᴀᴛᴇ ᴀɴʏ ᴀᴍᴏᴜɴᴛ ₹𝟷𝟶, ₹𝟸𝟶, ₹𝟻𝟶, ₹𝟷𝟶𝟶, ᴇᴛᴄ.</i></b>

ᴅᴏɴᴀᴛɪᴏɴs ᴀʀᴇ ʀᴇᴀʟʟʏ ᴀᴘᴘʀᴇᴄɪᴀᴛᴇᴅ ɪᴛ ʜᴇʟᴘs ɪɴ ʙᴏᴛ ᴅᴇᴠᴇʟᴏᴘᴍᴇɴᴛ

 <u>ʏᴏᴜ ᴄᴀɴ ᴀʟsᴏ ᴅᴏɴᴀᴛᴇ ᴛʜʀᴏᴜɢʜ ᴜᴘɪ</u>

 ᴜᴘɪ ɪᴅ : <code>LodaLassan@fam</code>

ɪғ ʏᴏᴜ ᴡɪsʜ ʏᴏᴜ ᴄᴀɴ sᴇɴᴅ ᴜs ss
ᴏɴ - @ProYato"""

    PREMIUM_TXT = """<b>ᴜᴘɢʀᴀᴅᴇ ᴛᴏ ᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ sᴇʀᴠɪᴄᴇ ᴀɴᴅ ᴇɴJᴏʏ ᴇxᴄʟᴜsɪᴠᴇ ғᴇᴀᴛᴜʀᴇs:
○ ᴜɴʟɪᴍɪᴛᴇᴅ Rᴇɴᴀᴍɪɴɢ: ʀᴇɴᴀᴍᴇ ᴀs ᴍᴀɴʏ ғɪʟᴇs ᴀs ʏᴏᴜ ᴡᴀɴᴛ ᴡɪᴛʜᴏᴜᴛ ᴀɴʏ ʀᴇsᴛʀɪᴄᴛɪᴏɴs.
○ ᴇᴀʀʟʏ Aᴄᴄᴇss: ʙᴇ ᴛʜᴇ ғɪʀsᴛ ᴛᴏ ᴛᴇsᴛ ᴀɴᴅ ᴜsᴇ ᴏᴜʀ ʟᴀᴛᴇsᴛ ғᴇᴀᴛᴜʀᴇs ʙᴇғᴏʀᴇ ᴀɴʏᴏɴᴇ ᴇʟsᴇ.

• ᴜꜱᴇ /plan ᴛᴏ ꜱᴇᴇ ᴀʟʟ ᴏᴜʀ ᴘʟᴀɴꜱ ᴀᴛ ᴏɴᴄᴇ.

➲ ғɪʀsᴛ sᴛᴇᴘ : ᴘᴀʏ ᴛʜᴇ ᴀᴍᴏᴜɴᴛ ᴀᴄᴄᴏʀᴅɪɴɢ ᴛᴏ ʏᴏᴜʀ ғᴀᴠᴏʀɪᴛᴇ ᴘʟᴀɴ ᴛᴏ ᴛʜɪs rohit162@fam ᴜᴘɪ ɪᴅ.

➲ secoɴᴅ sᴛᴇᴘ : ᴛᴀᴋᴇ ᴀ sᴄʀᴇᴇɴsʜᴏᴛ ᴏғ ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ ᴀɴᴅ sʜᴀʀᴇ ɪᴛ ᴅɪʀᴇᴄᴛʟʏ ʜᴇʀᴇ: @sewxiy

➲ ᴀʟᴛᴇʀɴᴀᴛɪᴠᴇ sᴛᴇᴘ : ᴏʀ ᴜᴘʟᴏᴀᴅ ᴛʜᴇ sᴄʀᴇᴇɴsʜᴏᴛ ʜᴇʀᴇ ᴀɴᴅ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴛʜᴇ /bought ᴄᴏᴍᴍᴀɴᴅ.

Yᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴ ᴡɪʟʟ ʙᴇ ᴀᴄᴛɪᴠᴀᴛᴇᴅ ᴀғᴛᴇʀ ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ</b>"""

    PREPLANS_TXT = """<b>👋 bro,

🎖️ <u>ᴀᴠᴀɪʟᴀʙʟᴇ ᴘʟᴀɴs</u> :

Pʀɪᴄɪɴɢ:
➜ ᴍᴏɴᴛʜʟʏ ᴘʀᴇᴍɪᴜᴍ: ₹50/ᴍᴏɴᴛʜ
➜ ᴅᴀɪʟʏ ᴘʀᴇᴍɪᴜᴍ: ₹𝟻/ᴅᴀʏ
➜  ғᴏʀ ʙᴏᴛ ʜᴏsᴛɪɴɢ: ᴄᴏɴᴛᴀᴄᴛ @ProYato

➲ ᴜᴘɪ ɪᴅ - <code>LodaLassan@fam</code>

‼️ᴜᴘʟᴏᴀᴅ ᴛʜᴇ ᴘᴀʏᴍᴇɴᴛ sᴄʀᴇᴇɴsʜᴏᴛ ʜᴇʀᴇ ᴀɴᴅ ʀᴇᴘʟʏ ᴡɪᴛʜ ᴛʜᴇ /bought ᴄᴏᴍᴍᴀɴᴅ.</b>"""

    HELP_TXT = """<b>» ᴄᴏᴍᴍᴀɴᴅs & ꜰᴇᴀᴛᴜʀᴇꜱ</b>

<b>⚙️ ꜱᴇᴛᴜᴘ</b>
➲ /settings — ᴀʟʟ ʏᴏᴜʀ ꜱᴇᴛᴛɪɴɢꜱ ɪɴ ᴏɴᴇ ᴘʟᴀᴄᴇ
➲ /autorename — ꜱᴇᴛ ʏᴏᴜʀ ʀᴇɴᴀᴍᴇ ꜰᴏʀᴍᴀᴛ
➲ /metadata — ᴇᴅɪᴛ ᴍᴋᴠ ᴍᴇᴛᴀᴅᴀᴛᴀ
➲ /dump — ꜱᴇᴛ ʏᴏᴜʀ ᴅᴜᴍᴘ ᴄʜᴀɴɴᴇʟ

<b>🖼️ ᴛʜᴜᴍʙɴᴀɪʟ</b>
➲ /setthumb — ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ ᴛᴏ ꜱᴇᴛ ᴛʜᴜᴍʙɴᴀɪʟ
➲ /view_thumb — ᴠɪᴇᴡ ᴛʜᴜᴍʙɴᴀɪʟ
➲ /del_thumb — ᴅᴇʟᴇᴛᴇ ᴛʜᴜᴍʙɴᴀɪʟ

<b>💬 ᴄᴀᴘᴛɪᴏɴ</b>
➲ /set_caption — ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ
➲ /see_caption — ᴠɪᴇᴡ ᴄᴀᴘᴛɪᴏɴ
➲ /del_caption — ᴅᴇʟᴇᴛᴇ ᴄᴀᴘᴛɪᴏɴ

<b>📋 ǫᴜᴇᴜᴇ</b>
➲ /queue — ᴠɪᴇᴡ ᴄᴜʀʀᴇɴᴛ ᴇɴᴛɪʀᴇ ʙᴏᴛ ǫᴜᴇᴜᴇ ꜱᴛᴀᴛᴜꜱ
➲ /cancel — ᴄᴀɴᴄᴇʟ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴛᴀꜱᴋ
➲ /cancel all — ᴄᴀɴᴄᴇʟ ᴀʟʟ ʏᴏᴜʀ ᴛᴀꜱᴋꜱ"""

    SEND_METADATA = """<b>🏷️ Metadata Settings</b>

➜ /metadata — ᴏᴘᴇɴ ᴍᴇᴛᴀᴅᴀᴛᴀ ꜱᴇᴛᴛɪɴɢꜱ

<b>ᴅᴇꜱᴄʀɪᴘᴛɪᴏɴ:</b> ᴍᴇᴛᴀᴅᴀᴛᴀ ᴡɪʟʟ ᴇᴍʙᴇᴅ ᴄᴜꜱᴛᴏᴍ ᴛɪᴛʟᴇ, ᴀᴜᴛʜᴏʀ, ᴀʀᴛɪꜱᴛ, ᴀᴜᴅɪᴏ, ꜱᴜʙᴛɪᴛʟᴇ ᴀɴᴅ ᴠɪᴅᴇᴏ ᴛʀᴀᴄᴋ ɴᴀᴍᴇꜱ ɪɴᴛᴏ ʏᴏᴜʀ ᴍᴋᴠ ꜰɪʟᴇꜱ."""

    SOURCE_TXT = """
<b>ʜᴇʏ,
 ᴛʜɪs ɪs ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ʙᴏᴛ,
ᴀɴ ᴏᴩᴇɴ sᴏᴜʀᴄᴇ ᴛᴇʟᴇɢʀᴀᴍ ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ʙᴏᴛ.</b>

ᴡʀɪᴛᴛᴇɴ ɪɴ ᴩʏᴛʜᴏɴ ᴡɪᴛʜ ᴛʜᴇ ʜᴇʟᴩ ᴏғ :
[ᴩʏʀᴏɢʀᴀᴍ](https://github.com/pyrogram/pyrogram)
ᴀɴᴅ ᴜsɪɴɢ [ᴍᴏɴɢᴏ](https://cloud.mongodb.com) ᴀs ᴅᴀᴛᴀʙᴀsᴇ.


<b>ʜᴇʀᴇ ɪs ᴍʏ sᴏᴜʀᴄᴇ ᴄᴏᴅᴇ :</b> [ɢɪᴛʜᴜʙ](https://github.com/codeflix_bots/autorenamebot)


ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ʙᴏᴛ ɪs ʟɪᴄᴇɴsᴇᴅ ᴜɴᴅᴇʀ ᴛʜᴇ [ᴍɪᴛ ʟɪᴄᴇɴsᴇ](https://github.com/codeflix_bots/autorenamebot/blob/main/LICENSE).
© 2025 | [sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ](https://t.me/codeflixsupport), ᴀʟʟ ʀɪɢʜᴛs ʀᴇsᴇʀᴠᴇᴅ."""

    META_TXT = """
**🏷️ Metadata Manager**

**ꜰɪᴇʟᴅꜱ ʏᴏᴜ ᴄᴀɴ ꜱᴇᴛ:**

- **ᴛɪᴛʟᴇ** — ᴍᴇᴅɪᴀ ᴛɪᴛʟᴇ
- **ᴀᴜᴛʜᴏʀ** — ᴄʀᴇᴀᴛᴏʀ / ᴏᴡɴᴇʀ
- **ᴀʀᴛɪꜱᴛ** — ᴀꜱꜱᴏᴄɪᴀᴛᴇᴅ ᴀʀᴛɪꜱᴛ
- **ᴀᴜᴅɪᴏ** — ᴀᴜᴅɪᴏ ᴛʀᴀᴄᴋ ɴᴀᴍᴇ
- **ꜱᴜʙᴛɪᴛʟᴇ** — ꜱᴜʙᴛɪᴛʟᴇ ᴛʀᴀᴄᴋ ɴᴀᴍᴇ
- **ᴠɪᴅᴇᴏ** — ᴠɪᴅᴇᴏ ᴛʀᴀᴄᴋ ɴᴀᴍᴇ

ᴜꜱᴇ /metadata ᴛᴏ ᴏᴘᴇɴ ᴛʜᴇ ᴍᴇᴛᴀᴅᴀᴛᴀ ᴍᴀɴᴀɢᴇʀ.
"""
