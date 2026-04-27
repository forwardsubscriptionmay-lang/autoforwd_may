import os
import json
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from userbot import client, start_userbot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CONFIG_FILE = "config.json"

chat_list = []
mode = None
map_source = None


# ================= CONFIG =================

def load():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def icon(v):
    return "🟢" if v else "🔴"


# ================= COMMAND SETTINGS =================

async def links_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    data["settings"]["remove_links"] = True
    save(data)
    await update.message.reply_text("✅ Links remove ON")


async def links_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    data["settings"]["remove_links"] = False
    save(data)
    await update.message.reply_text("❌ Links remove OFF")


async def username_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    data["settings"]["remove_username"] = True
    save(data)
    await update.message.reply_text("✅ Username remove ON")


async def username_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    data["settings"]["remove_username"] = False
    save(data)
    await update.message.reply_text("❌ Username remove OFF")


async def forward_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    data["settings"]["forward"] = True
    save(data)
    await update.message.reply_text("✅ Forward ON")


async def forward_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    data["settings"]["forward"] = False
    save(data)
    await update.message.reply_text("❌ Forward OFF")


async def media_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    data["settings"]["media"] = True
    save(data)
    await update.message.reply_text("✅ Media ON")


async def media_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    data["settings"]["media"] = False
    save(data)
    await update.message.reply_text("❌ Media OFF")


async def autodel_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    data["settings"]["auto_delete"] = True
    save(data)
    await update.message.reply_text("✅ Auto Delete ON")


async def autodel_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    data["settings"]["auto_delete"] = False
    save(data)
    await update.message.reply_text("❌ Auto Delete OFF")


async def set_replace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    if context.args:
        data["settings"]["replace_link"] = context.args[0]
        save(data)
        await update.message.reply_text("✅ Replace link set")
    else:
        await update.message.reply_text("Usage: /replace_link https://yourlink.com")


async def add_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    if context.args:
        word = context.args[0]
        if word not in data["settings"]["blacklist"]:
            data["settings"]["blacklist"].append(word)
            save(data)
        await update.message.reply_text(f"✅ Added: {word}")
    else:
        await update.message.reply_text("Usage: /block word")


# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    kb = [
        [InlineKeyboardButton("📥 Add Sources", callback_data="sources")],
        [InlineKeyboardButton("🎯 Add Targets", callback_data="targets")],
        [InlineKeyboardButton("🔗 Mapping", callback_data="mapping")],
        [InlineKeyboardButton("❌ Remove Sources", callback_data="remove_sources")],
        [InlineKeyboardButton("❌ Remove Targets", callback_data="remove_targets")],
        [InlineKeyboardButton("📊 Dashboard", callback_data="dashboard")]
    ]

    await update.message.reply_text(
        "🚀 AUTO FORWARD PANEL",
        reply_markup=InlineKeyboardMarkup(kb)
    )


# ================= PANEL =================

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global mode

    q = update.callback_query
    await q.answer()

    if q.data == "sources":
        mode = "source"

    elif q.data == "targets":
        mode = "target"

    elif q.data == "mapping":
        mode = "map_source"

    if q.data in ["sources", "targets", "mapping"]:
        kb = [[InlineKeyboardButton("📌 Show Chats", callback_data="fetch")]]
        await q.message.edit_text(
            "Select chat",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif q.data == "remove_sources":
        await remove_sources(update)

    elif q.data == "remove_targets":
        await remove_targets(update)

    elif q.data == "dashboard":
        await dashboard(update, context)

# ================= REMOVE SOURCES =================

async def remove_sources(update):

    q = update.callback_query
    await q.answer()

    data = load()

    buttons = []

    for cid, name in data["sources"].items():
        buttons.append([InlineKeyboardButton(name, callback_data=f"rs_{cid}")])

    if not buttons:
        buttons = [[InlineKeyboardButton("❌ No Sources", callback_data="noop")]]

    await q.message.edit_text(
        "Select source to remove",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ================= REMOVE TARGETS =================

async def remove_targets(update):

    q = update.callback_query
    await q.answer()

    data = load()

    buttons = []

    for cid, name in data["targets"].items():
        buttons.append([InlineKeyboardButton(name, callback_data=f"rt_{cid}")])

    if not buttons:
        buttons = [[InlineKeyboardButton("❌ No Targets", callback_data="noop")]]

    await q.message.edit_text(
        "Select target to remove",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
# ================= FETCH =================

async def fetch(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global chat_list, mode

    q = update.callback_query
    await q.answer()

    data = load()
    chat_list = []

    if not client.is_connected():
        await client.connect()

    if mode == "map_source":
        chat_list = list(data["sources"].items())

    elif mode == "map_target":
        chat_list = list(data["targets"].items())

    else:
        dialogs = await client.get_dialogs()
        chat_list = [(str(d.id), d.name) for d in dialogs[:15]]

    text = "📋 SELECT CHAT\n\n"

    for i, (_, name) in enumerate(chat_list, 1):
        text += f"{i}. {name}\n"

    buttons = []
    row = []

    for i in range(1, len(chat_list) + 1):
        row.append(InlineKeyboardButton(str(i), callback_data=f"add_{i}"))
        if len(row) == 5:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    await q.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# ================= ADD =================

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global mode, map_source

    q = update.callback_query
    await q.answer()

    i = int(q.data.split("_")[1]) - 1
    cid, name = chat_list[i]

    data = load()

    if mode == "source":
        data["sources"][cid] = name
        save(data)
        await q.message.edit_text(f"✅ SOURCE ADDED\n{name}")

    elif mode == "target":
        data["targets"][cid] = name
        save(data)
        await q.message.edit_text(f"✅ TARGET ADDED\n{name}")

    elif mode == "map_source":
        map_source = cid
        mode = "map_target"

        kb = [[InlineKeyboardButton("📌 Show Targets", callback_data="fetch")]]

        await q.message.edit_text(
            f"✅ SOURCE SELECTED:\n{name}\n\nअब TARGET select करो",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif mode == "map_target":

        data["mapping"].setdefault(map_source, [])

        if cid not in data["mapping"][map_source]:
            data["mapping"][map_source].append(cid)

        save(data)

        await q.message.edit_text(f"✅ MAPPED\n{name}")

        map_source = None
        mode = None


# ================= REMOVE / DASHBOARD same =================

# (unchanged - same as your code)
async def remove_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    data = load()

    if q.data.startswith("rs_"):

        cid = q.data.replace("rs_", "")
        name = data["sources"].get(cid)

        if cid in data["sources"]:
            del data["sources"][cid]
            data["mapping"].pop(cid, None)
            save(data)

            await q.message.edit_text(f"❌ SOURCE REMOVED\n{name}")

    elif q.data.startswith("rt_"):

        cid = q.data.replace("rt_", "")
        name = data["targets"].get(cid)

        if cid in data["targets"]:
            del data["targets"][cid]

            for k in list(data["mapping"].keys()):
                if cid in data["mapping"][k]:
                    data["mapping"][k].remove(cid)

            save(data)

            await q.message.edit_text(f"❌ TARGET REMOVED\n{name}")
            

# ================= DASHBOARD FUNCTION =================

async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query
    await q.answer()

    data = load()
    s = data["settings"]

    text = "📊 BOT DASHBOARD\n\n"

    # 📥 SOURCES
    text += "📥 SOURCES\n"
    for name in data["sources"].values():
        text += f"• {name}\n"

    # 🎯 TARGETS
    text += "\n🎯 TARGETS\n"
    for name in data["targets"].values():
        text += f"• {name}\n"

    # 🔗 MAPPING
    text += "\n🔗 MAPPING\n"
    for s_id, t_list in data["mapping"].items():
        s_name = data["sources"].get(s_id, s_id)
        for t_id in t_list:
            t_name = data["targets"].get(t_id, t_id)
            text += f"{s_name} → {t_name}\n"

    # ⚙ SETTINGS
    text += f"""

⚙ SETTINGS

Forward : {icon(s["forward"])}
Media : {icon(s["media"])}
Remove Links : {icon(s["remove_links"])}
Remove Username : {icon(s["remove_username"])}
Auto Delete : {icon(s["auto_delete"])}

Blacklist Words : {len(s["blacklist"])}
Replace Link : {s.get("replace_link") or "None"}
"""

    await q.message.edit_text(text)
# ================= START USERBOT =================

async def startup(app):
    asyncio.create_task(start_userbot())


# ================= MAIN =================

def main():

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(startup).build()

    app.add_handler(CommandHandler("start", start))

    # 🔥 COMMANDS ADDED
    app.add_handler(CommandHandler("links_on", links_on))
    app.add_handler(CommandHandler("links_off", links_off))
    app.add_handler(CommandHandler("username_on", username_on))
    app.add_handler(CommandHandler("username_off", username_off))
    app.add_handler(CommandHandler("forward_on", forward_on))
    app.add_handler(CommandHandler("forward_off", forward_off))
    app.add_handler(CommandHandler("media_on", media_on))
    app.add_handler(CommandHandler("media_off", media_off))
    app.add_handler(CommandHandler("autodel_on", autodel_on))
    app.add_handler(CommandHandler("autodel_off", autodel_off))
    app.add_handler(CommandHandler("replace_link", set_replace))
    app.add_handler(CommandHandler("block", add_blacklist))

    app.add_handler(CallbackQueryHandler(fetch, pattern="^fetch$"))
    app.add_handler(CallbackQueryHandler(add, pattern=r"^add_\d+$"))
    app.add_handler(CallbackQueryHandler(remove_handler, pattern="^(rs_|rt_)"))
    app.add_handler(CallbackQueryHandler(lambda u, c: None, pattern="^noop$"))
    app.add_handler(CallbackQueryHandler(
        panel,
        pattern="^(sources|targets|mapping|remove_sources|remove_targets|dashboard)$"
    ))

    print("BOT STARTED")

    app.run_polling()


if __name__ == "__main__":
    main()
