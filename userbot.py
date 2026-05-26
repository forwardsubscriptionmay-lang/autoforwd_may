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

client = TelegramClient(
    StringSession(STRING_SESSION),
    API_ID,
    API_HASH
)

msg_map = {}
processed_groups = set()


# =========================================
# LOAD CONFIG
# =========================================
def load():

    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


# =========================================
# TEXT PROCESS
# =========================================
def process_text(text, settings):

    if not text:
        text = ""

    # blacklist
    for word in settings.get("blacklist", []):

        if word.lower() in text.lower():
            return None

    # remove username
    if settings.get("remove_username"):

        text = re.sub(
            r"@\w+",
            "",
            text
        )

    # replace links
    if settings.get("replace_link"):

        text = re.sub(
            r"https?://\S+",
            settings["replace_link"],
            text
        )

    # remove links
    elif settings.get("remove_links"):

        text = re.sub(
            r"https?://\S+",
            "",
            text
        )

    return text.strip()


# =========================================
# SAFE SEND
# =========================================
async def safe_send(
    target,
    text=None,
    file=None,
    reply=None
):

    try:

        # MEDIA
        if file:

            return await client.send_file(
                int(target),
                file=file,
                caption=text,
                reply_to=reply,
                force_document=False
            )

        # TEXT
        else:

            if not text:
                return None

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


# =========================================
# FAST RAM MEDIA SYSTEM
# =========================================
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

    # RESTRICTED CHANNEL RAM FALLBACK
    path = None

    try:

        path = f"/dev/shm/{event.id}"

        path = await event.download_media(
            file=path
        )

        sent = await safe_send(
            target,
            text,
            path,
            reply_to
        )

        # CLEAN RAM
        try:
            os.remove(path)
        except:
            pass

        return sent

    except Exception as er:

        print("RAM DOWNLOAD ERROR:", er)

        # CLEAN RAM
        if path:

            try:
                os.remove(path)
            except:
                pass

    return None


# =========================================
# ALBUM HANDLER
# =========================================
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

    for msg in event.messages:

        if msg.media:
            files.append(msg.media)

        if msg.text:

            txt = process_text(
                msg.text,
                data["settings"]
            )

            if txt:
                caption = txt

    if not files:
        return

    async def send_album(target):

        try:

            reply_to = None

            # REPLY SUPPORT
            if event.reply_to_msg_id:

                old = msg_map.get(
                    event.reply_to_msg_id,
                    {}
                )

                reply_to = old.get(target)

            # FAST STREAM ALBUM
            try:

                sent = await client.send_file(
                    int(target),
                    files,
                    caption=caption,
                    reply_to=reply_to
                )

            except Exception:

                # RAM FALLBACK
                temp_files = []

                for msg in event.messages:

                    if msg.media:

                        path = f"/dev/shm/{msg.id}"

                        path = await msg.download_media(
                            file=path
                        )

                        temp_files.append(path)

                sent = await client.send_file(
                    int(target),
                    temp_files,
                    caption=caption,
                    reply_to=reply_to
                )

                # CLEAN RAM
                for p in temp_files:

                    try:
                        os.remove(p)
                    except:
                        pass

            # SAVE MESSAGE MAP
            if isinstance(sent, list):

                first_id = sent[0].id

                for msg in event.messages:

                    msg_map.setdefault(
                        msg.id,
                        {}
                    )[target] = first_id

            else:

                for msg in event.messages:

                    msg_map.setdefault(
                        msg.id,
                        {}
                    )[target] = sent.id

        except Exception as er:

            print("ALBUM ERROR:", er)

    # PARALLEL TARGET SEND
    await asyncio.gather(
        *[send_album(target) for target in targets]
    )


# =========================================
# NORMAL MESSAGE HANDLER
# =========================================
@client.on(events.NewMessage)
async def forward_handler(event):

    # SKIP ALBUM ITEMS
    if event.grouped_id:
        return

    data = load()

    cid = str(event.chat_id)

    if cid not in data["sources"]:
        return

    targets = data["mapping"].get(cid)

    if not targets:
        return

    text = process_text(
        event.text,
        data["settings"]
    )

    if text is None:
        return

    async def send_to_target(target):

        try:

            reply_to = None

            # REPLY SUPPORT
            if event.reply_to_msg_id:

                old = msg_map.get(
                    event.reply_to_msg_id,
                    {}
                )

                reply_to = old.get(target)

            # MEDIA
            if event.media and data["settings"].get("media"):

                sent = await smart_forward(
                    event,
                    target,
                    text,
                    reply_to
                )

            # TEXT
            else:

                sent = await safe_send(
                    target,
                    text,
                    None,
                    reply_to
                )

            # SAVE MESSAGE MAP
            if sent:

                msg_map.setdefault(
                    event.id,
                    {}
                )[target] = sent.id

        except Exception as er:

            print("FORWARD ERROR:", er)

    # PARALLEL TARGET SEND
    await asyncio.gather(
        *[send_to_target(target) for target in targets]
    )


# =========================================
# DELETE SYNC
# =========================================
@client.on(events.MessageDeleted)
async def delete_handler(event):

    for mid in event.deleted_ids:

        if mid not in msg_map:
            continue

        for target, target_msg_id in msg_map[mid].items():

            try:

                await client.delete_messages(
                    int(target),
                    target_msg_id
                )

            except:
                pass

        del msg_map[mid]


# =========================================
# START USERBOT
# =========================================
async def start_userbot():

    await client.start()

    me = await client.get_me()

    print(
        f"USERBOT RUNNING AS {me.first_name}"
    )

    await client.run_until_disconnected()
