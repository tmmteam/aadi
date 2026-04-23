import asyncio
import sqlite3
import os
import logging
from pyrogram import Client, filters
from pyrogram.errors import SessionPasswordNeeded, UserAlreadyParticipant
from pyrogram.types import ReplyKeyboardMarkup
from pyromod import listen

logging.getLogger("pyrogram").setLevel(logging.ERROR)

# --- CONFIG ---
API_ID = 20247726
API_HASH = "2a2654fa036e1ec6b98216d85d9fa38c"
BOT_TOKEN = "8650625191:AAFmIVTVNRvLC8xrCpTsxru62biVaq4DJFI"

OWNER_ID = 1161241513  # 👈 apna Telegram user id daal

# --- SESSION CLEAN ---
if os.path.exists("MasterBot.session"):
    os.remove("MasterBot.session")

bot = Client("MasterBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- DATABASE ---
db = sqlite3.connect("accounts.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (phone TEXT PRIMARY KEY, session TEXT, name TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS auth_users (user_id INTEGER PRIMARY KEY)")
db.commit()

# --- AUTH FUNCTIONS ---
def is_authorized(user_id):
    if user_id == OWNER_ID:
        return True
    cursor.execute("SELECT * FROM auth_users WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

async def not_auth(message):
    await message.reply(
        "❌ You are not authorised!\n\n"
        "Contact 👉 @AADI_520117 for Authorization"
    )

#--- REMOVE ACCESS ---
@bot.on_message(filters.command("removeaccess") & filters.private)
async def remove_access(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Only Owner can use this command")

    try:
        user_id = int(message.text.split()[1])
    except:
        return await message.reply("Usage: /removeaccess user_id")

    cursor.execute("DELETE FROM auth_users WHERE user_id=?", (user_id,))
    db.commit()

    await message.reply(f"❌ Access Removed from {user_id}")

# --- ACCESS COMMAND ---
@bot.on_message(filters.command("access") & filters.private)
async def access_user(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Only Owner can use this command")

    try:
        user_id = int(message.text.split()[1])
    except:
        return await message.reply("Usage: /access user_id")

    cursor.execute("INSERT OR IGNORE INTO auth_users VALUES (?)", (user_id,))
    db.commit()

    await message.reply(f"✅ Access Granted to {user_id}")

# --- LIST ACCESS ---
@bot.on_message(filters.command("listaccess") & filters.private)
async def list_access(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Only Owner can use this command")

    cursor.execute("SELECT user_id FROM auth_users")
    users = cursor.fetchall()

    if not users:
        return await message.reply("📭 No authorized users")

    text = "📋 **Authorized Users:**\n\n"
    for u in users:
        text += f"• `{u[0]}`\n"

    await message.reply(text)
    
# --- STATS OF BOT ---
@bot.on_message(filters.command("stats") & filters.private)
async def stats(client, message):

    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Only Owner")

    # --- TOTAL ACCOUNTS ---
    cursor.execute("SELECT COUNT(*) FROM users")
    total_accounts = cursor.fetchone()[0]

    # --- ACTIVE / DEAD CHECK ---
    active = 0
    dead = 0

    sessions = get_all_accounts()

    for i, s in enumerate(sessions, start=1):
        try:
            acc = Client(f"check{i}", session_string=s, api_id=API_ID, api_hash=API_HASH)
            await acc.connect()
            active += 1
            await acc.disconnect()
        except:
            dead += 1

    # --- AUTH USERS ---
    cursor.execute("SELECT COUNT(*) FROM auth_users")
    auth_users = cursor.fetchone()[0]

    # --- RESPONSE ---
    text = f"""
📊 **BOT STATS**

👤 Total Accounts: {total_accounts}
✅ Active Accounts: {active}
❌ Dead Accounts: {dead}

🔐 Authorized Users: {auth_users}
"""

    await message.reply(text)

# --- GET ACCOUNTS ---
def get_all_accounts():
    cursor.execute("SELECT session FROM users")
    return [x[0] for x in cursor.fetchall()]

# --- START ---
@bot.on_message(filters.command("start"))
async def start(client, message):

    if is_authorized(message.from_user.id):
        kb = ReplyKeyboardMarkup(
            [["VOTE"], ["/add"]],
            resize_keyboard=True
        )
    else:
        kb = ReplyKeyboardMarkup(
            [["/add"]],
            resize_keyboard=True
        )

    await message.reply("🤖 Bot Active!", reply_markup=kb)

# --- ADD ACCOUNT ---
@bot.on_message(filters.command("add"))
async def add(client, message):
    try:
        phone = (await bot.ask(message.chat.id, "📱 Number (+91...):")).text

        temp = Client("temp", api_id=API_ID, api_hash=API_HASH, in_memory=True)
        await temp.connect()

        code = await temp.send_code(phone)
        otp = (await bot.ask(message.chat.id, "📩 OTP:")).text

        try:
            await temp.sign_in(phone, code.phone_code_hash, otp)
        except SessionPasswordNeeded:
            pw = await bot.ask(message.chat.id, "🔐 2FA Password:")
            await temp.check_password(pw.text)

        session = await temp.export_session_string()
        me = await temp.get_me()

        cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)", (phone, session, me.first_name))
        db.commit()

        await temp.disconnect()
        await message.reply(f"✅ Added: {me.first_name}")

    except Exception as e:
        await message.reply(f"❌ Error: {e}")

# --- VOTE ---
@bot.on_message(filters.regex("^VOTE$"))
async def vote(client, message):

    if not is_authorized(message.from_user.id):
        return await not_auth(message)

    sessions = get_all_accounts()

    ch_link = (await bot.ask(message.chat.id, "🔗 Channel invite link bhejo:")).text
    post_link = (await bot.ask(message.chat.id, "🔗 Post link bhejo:")).text

    try:
        msg_id = int(post_link.split("/")[-1])
    except:
        return await message.reply("❌ Invalid post link")

    joined = 0
    voted = 0

    for i, session in enumerate(sessions, start=1):
        acc = Client(f"user{i}", session_string=session, api_id=API_ID, api_hash=API_HASH)

        try:
            await acc.start()

            try:
                await acc.join_chat(ch_link)
                joined += 1
            except UserAlreadyParticipant:
                joined += 1
            except:
                continue

            chat = await acc.get_chat(ch_link)
            msg = await acc.get_messages(chat.id, msg_id)

            if not msg or not msg.reply_markup:
                continue

            for row in msg.reply_markup.inline_keyboard:
                for btn in row:
                    try:
                        await acc.request_callback_answer(chat.id, msg.id, btn.callback_data)
                        voted += 1
                        break
                    except:
                        continue

        except:
            pass
        finally:
            try:
                await acc.stop()
            except:
                pass

    await message.reply(f"✅ Joined: {joined}\n✅ Voted: {voted}")

print("Bot running...")
bot.run()
