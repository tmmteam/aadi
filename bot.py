import asyncio
import sqlite3
import os
import logging
import random
from pyrogram.types import InlineKeyboardMarkup
from pyrogram import Client, filters
from pyrogram.errors import SessionPasswordNeeded
from pyrogram.errors import UserAlreadyParticipant
from pyrogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from pyromod import listen

logging.getLogger("pyrogram").setLevel(logging.ERROR)

# --- CONFIG ---
API_ID = 20247726
API_HASH = "2a2654fa036e1ec6b98216d85d9fa38c"
BOT_TOKEN = "8650625191:AAFmIVTVNRvLC8xrCpTsxru62biVaq4DJFI"

# --- SESSION CLEAN ---
if os.path.exists("MasterBot.session"):
    os.remove("MasterBot.session")

bot = Client("MasterBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- DATABASE ---
db = sqlite3.connect("accounts.db", check_same_thread=False)
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (phone TEXT PRIMARY KEY, session TEXT, name TEXT)")
db.commit()

def get_all_accounts():
    cursor.execute("SELECT session FROM users")
    return [x[0] for x in cursor.fetchall()]

def delete_account(session):
    cursor.execute("DELETE FROM users WHERE session=?", (session,))
    db.commit()

# --- START ---
@bot.on_message(filters.command("start"))
async def start(client, message):
    kb = ReplyKeyboardMarkup(
        [["VOTE"], ["/add"]],
        resize_keyboard=True
    )
    await message.reply("🤖 Refer Bot Active!", reply_markup=kb)

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

# --- LINK PARSER (FIXED) ---
def parse_link(link):
    try:
        if "t.me/c/" in link:
            parts = link.split("/")
            return int("-100" + parts[-2]), int(parts[-1]), "private"

        elif "t.me/" in link:
            parts = link.split("/")
            return parts[-2], int(parts[-1]), "public"

    except:
        return None, None, None

@bot.on_message(filters.regex("^VOTE$"))
async def vote(client, message):
    sessions = get_all_accounts()
    
    # STEP 1: CHANNEL INVITE LINK
    ch_link_msg = await bot.ask(message.chat.id, "🔗 Channel invite link bhejo:")
    ch_link = ch_link_msg.text.strip()
    
    # STEP 2: POST LINK
    post_link_msg = await bot.ask(message.chat.id, "🔗 Post link bhejo:")
    post_link = post_link_msg.text.strip()
    
    # Extract message ID from post link
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
            print(f"\n🔹 Account {i} started")
            
            # 1. JOIN CHANNEL
            try:
                await acc.join_chat(ch_link)
                joined += 1
                print(f"✅ Account {i} joined channel")
            except UserAlreadyParticipant:
                joined += 1
                print(f"⚠️ Account {i} already in channel")
            except Exception as e:
                print(f"❌ Join error: {e}")
                continue
            
            # 2. GET CHAT ENTITY FROM INVITE LINK (CRITICAL FIX)
            try:
                # 🔥 FIX: Invite link se chat fetch karo
                chat = await acc.get_chat(ch_link)
                chat_id = chat.id
                print(f"✅ Chat resolved: {chat_id}")
            except Exception as e:
                print(f"❌ Chat resolve error: {e}")
                continue
            
            # 3. GET MESSAGE
            try:
                msg = await acc.get_messages(chat_id, msg_id)
                if not msg:
                    print(f"❌ Message not found")
                    continue
                print(f"✅ Message fetched")
            except Exception as e:
                print(f"❌ Fetch error: {e}")
                continue
            
            # 4. CLICK BUTTON
            if not msg.reply_markup:
                print(f"❌ No buttons in message")
                continue
            
            clicked = False
            for row in msg.reply_markup.inline_keyboard:
                for btn in row:
                    try:
                        await acc.request_callback_answer(
                            chat_id,
                            msg.id,
                            btn.callback_data
                        )
                        print(f"✅ Clicked: {btn.text}")
                        voted += 1
                        clicked = True
                        break
                    except Exception as e:
                        print(f"❌ Click error: {e}")
                        continue
                if clicked:
                    break
            
            if not clicked:
                print(f"❌ No button could be clicked")
                
        except Exception as e:
            print(f"❌ Account {i} error: {e}")
        finally:
            try:
                await acc.stop()
            except:
                pass
    
    await message.reply(f"✅ Joined: {joined}\n✅ Voted: {voted}")
    print("Bot starting...")
bot.run()
