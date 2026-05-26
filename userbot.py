import os
import json
import re
import asyncio
import tempfile

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
STRING_SESSION = os.getenv("STRING_SESSION")

CONFIG_FILE = "config.json"

client = TelegramClient(
StringSession(STRING_SESSION),
API_ID,
API_HASH
)

msg_map = {}
processed_groups = set()

=========================================

LOAD CONFIG

=========================================

def load():

with open(CONFIG_FILE) as f:
    return json.load(f)

=========================================

TEXT PROCESS

=========================================

def process_text(text, s):

if not text:
    text = ""

for w in s.get("blacklist", []):

    if w.lower() in text.lower():
        return None

if s.get("remove_username"):

    text = re.sub(
        r"@\w+",
        "",
        text
    )

if s.get("replace_link"):

    text = re.sub(
        r"https?://\S+",
        s["replace_link"],
        text
    )

elif s.get("remove_links"):

    text = re.sub(
        r"https?://\S+",
        "",
        text
    )

return text.strip()

=========================================

SAFE SEND

=========================================

async def safe_send(
target,
text=None,
file=None,
reply=None
):

if not text and not file:
    return None

try:

    # MEDIA
    if file:

        return await client.send_file(
            int(target),
            file=file,
            caption=text,
            reply_to=reply
        )

    # TEXT
    else:

        return await client.send_message(
            int(target),
            text,
            reply_to=reply,
            link_preview=False
        )

except FloodWaitError as e:

    print(f"FloodWait {e.seconds}s")
    await asyncio.sleep(e.seconds)

except Exception as er:

    print("SEND ERROR:", er)

return None

=========================================

FAST MEDIA SYSTEM

=========================================

async def smart_forward(
event,
target,
text,
reply_to=None
):

# FAST STREAM METHOD
try:

    return await safe_send(
        target,
        text,
        event.media,
        reply_to
    )

except Exception as er:

    print("FAST STREAM FAILED:", er)

# FALLBACK FOR RESTRICTED CHANNELS
try:

    # RAM TEMP FILE
    with tempfile.NamedTemporaryFile(delete=True) as tmp:

        path = await event.download_media(
            file=tmp.name
        )

        return await safe_send(
            target,
            text,
            path,
            reply_to
        )

except Exception as er:

    print("DOWNLOAD FALLBACK ERROR:", er)

return None

=========================================

ALBUM HANDLER

=========================================

@client.on(events.Album)
async def album_handler(event):

gid = event.grouped_id

# DUPLICATE PROTECTION
if gid in processed_groups:
    return

processed_groups.add(gid)

# WAIT FOR FULL ALBUM
await asyncio.sleep(2)

data = load()

cid = str(event.chat_id)

if cid not in data["sources"]:
    return

targets = data["mapping"].get(cid)

if not targets:
    return

files = []
caption = ""

for m in event.messages:

    if m.media:
        files.append(m.media)

    if m.text:

        txt = process_text(
            m.text,
            data["settings"]
        )

        if txt:
            caption = txt

if not files:
    return

for t in targets:

    try:

        reply_to = None

        # REPLY SUPPORT
        if event.reply_to_msg_id:

            old = msg_map.get(
                event.reply_to_msg_id,
                {}
            )

            reply_to = old.get(t)

        # FAST STREAM ALBUM
        try:

            sent = await client.send_file(
                int(t),
                files,
                caption=caption,
                reply_to=reply_to
            )

        except Exception:

            # RESTRICTED CHANNEL FALLBACK
            temp_files = []

            for m in event.messages:

                if m.media:

                    tmp = tempfile.NamedTemporaryFile(
                        delete=False
                    )

                    path = await m.download_media(
                        file=tmp.name
                    )

                    temp_files.append(path)

            sent = await client.send_file(
                int(t),
                temp_files,
                caption=caption,
                reply_to=reply_to
            )

            # CLEANUP
            for p in temp_files:

                try:
                    os.remove(p)
                except:
                    pass

        # SAVE MESSAGE MAP
        if isinstance(sent, list):

            first_msg = sent[0].id

            for m in event.messages:

                msg_map.setdefault(
                    m.id,
                    {}
                )[t] = first_msg

        else:

            for m in event.messages:

                msg_map.setdefault(
                    m.id,
                    {}
                )[t] = sent.id

    except Exception as er:

        print("ALBUM ERROR:", er)

=========================================

NORMAL MESSAGE HANDLER

=========================================

@client.on(events.NewMessage)
async def forward_handler(e):

# SKIP ALBUM ITEMS
if e.grouped_id:
    return

data = load()

cid = str(e.chat_id)

if cid not in data["sources"]:
    return

targets = data["mapping"].get(cid)

if not targets:
    return

text = process_text(
    e.text,
    data["settings"]
)

if text is None:
    return

for t in targets:

    try:

        reply_to = None

        # REPLY SUPPORT
        if e.reply_to_msg_id:

            old = msg_map.get(
                e.reply_to_msg_id,
                {}
            )

            reply_to = old.get(t)

        # MEDIA
        if e.media and data["settings"].get("media"):

            sent = await smart_forward(
                e,
                t,
                text,
                reply_to
            )

        # TEXT
        else:

            sent = await safe_send(
                t,
                text,
                None,
                reply_to
            )

        # SAVE MAP
        if sent:

            msg_map.setdefault(
                e.id,
                {}
            )[t] = sent.id

    except Exception as er:

        print("FORWARD ERROR:", er)

=========================================

DELETE SYNC

=========================================

@client.on(events.MessageDeleted)
async def delete_handler(e):

for mid in e.deleted_ids:

    if mid not in msg_map:
        continue

    for t, tid in msg_map[mid].items():

        try:

            await client.delete_messages(
                int(t),
                tid
            )

        except:
            pass

    del msg_map[mid]

=========================================

START USERBOT

=========================================

async def start_userbot():

await client.start()

me = await client.get_me()

print(
    f"USERBOT RUNNING AS {me.first_name}"
)

await client.run_until_disconnected()
