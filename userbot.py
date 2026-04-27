import os
import json
import re
import asyncio

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
STRING_SESSION = os.getenv("STRING_SESSION")

CONFIG_FILE = "config.json"

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

msg_map = {}


def load():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def process_text(text, s):

    if not text:
        text = ""

    for w in s.get("blacklist", []):
        if w.lower() in text.lower():
            return None

    if s.get("remove_username"):
        text = re.sub(r"@\w+", "", text)

    if s.get("replace_link"):
        text = re.sub(r"https?://\S+", s["replace_link"], text)

    elif s.get("remove_links"):
        text = re.sub(r"https?://\S+", "", text)

    return text.strip()


async def safe_send(target, text=None, file=None, reply=None):

    if not text and not file:
        return None

    try:
        if file:
            return await client.send_file(int(target), file, caption=text, reply_to=reply)
        else:
            return await client.send_message(int(target), text, reply_to=reply, link_preview=False)

    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)

    except Exception as er:
        print("SEND ERROR:", er)

    return None


# 🔥 ALBUM FIX (DELAY + COMPLETE LOAD)
@client.on(events.Album)
async def album_handler(event):

    await asyncio.sleep(10)  # 🔥 MAIN FIX (wait for full album)

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
            f = await m.download_media()
            if f:
                files.append(f)

        if m.text:
            caption = process_text(m.text, data["settings"]) or caption

    if not files:
        return

    for t in targets:
        try:
            sent = await client.send_file(
                int(t),
                files,
                caption=caption
            )

            for m in event.messages:
                msg_map.setdefault(m.id, {})[t] = sent[0].id if isinstance(sent, list) else sent.id

        except Exception as er:
            print("ALBUM ERROR:", er)


# 🔥 NORMAL MESSAGE (MEDIA FIX)
@client.on(events.NewMessage)
async def forward_handler(e):

    if e.grouped_id:
        return

    data = load()
    cid = str(e.chat_id)

    if cid not in data["sources"]:
        return

    targets = data["mapping"].get(cid)
    if not targets:
        return

    text = process_text(e.text, data["settings"])
    if text is None:
        return

    for t in targets:
        try:

            if e.media and data["settings"].get("media"):
                file = await e.download_media()
                sent = await safe_send(t, text, file)
            else:
                sent = await safe_send(t, text, None)

            if sent:
                msg_map.setdefault(e.id, {})[t] = sent.id

        except Exception as er:
            print("FORWARD ERROR:", er)


# 🔥 DELETE SYNC
@client.on(events.MessageDeleted)
async def delete_handler(e):

    for mid in e.deleted_ids:

        if mid not in msg_map:
            continue

        for t, tid in msg_map[mid].items():
            try:
                await client.delete_messages(int(t), tid)
            except:
                pass

        del msg_map[mid]


async def start_userbot():
    await client.start()
    print("USERBOT RUNNING")
    await client.run_until_disconnected()
