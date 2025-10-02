import asyncio
import sqlite3
import requests
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# ================= CONFIG =================
BOT_TOKEN = "8220188279:AAFmn0aSY8XqHk5DrQvuzAw6iMtheojfysg"
LOG_CHANNEL = -1003124012321
MAIN_GROUP = -1002777315896  # Your group ID

SHORTENER_API_KEY = "6e633aea4aaf1dba0797e8b732de0f65183d9c7a"
DEFAULT_REMOVE_TIME = 24

# ==========================================

print("🔧 Initializing bot...")

# Init bot
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

print("✅ Bot initialized")

# SQLite setup
conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    join_time TEXT,
    expiry_time TEXT,
    invite_link TEXT
)
""")
conn.commit()

print("✅ Database setup complete")

# ========== Helper Functions ==========
async def log_message(text: str):
    """Send log message to log channel"""
    try:
        await bot.send_message(LOG_CHANNEL, text)
        print(f"✅ Log sent to channel: {text[:50]}...")
    except Exception as e:
        print(f"❌ Log error: {e}")

def format_time(dt: datetime):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# ========== Handle ALL MESSAGES for debugging ==========
@dp.message_handler(content_types=types.ContentType.ANY)
async def handle_all_messages(message: types.Message):
    """Debug all messages to see what's happening"""
    current_time = datetime.now().strftime("%H:%M:%S")
    
    print(f"\n📨 📨 📨 NEW MESSAGE IN GROUP 📨 📨 📨")
    print(f"🕒 Time: {current_time}")
    print(f"🔍 Chat ID: {message.chat.id}")
    print(f"🔍 Chat Title: {message.chat.title}")
    print(f"🔍 Content Type: {message.content_type}")
    print(f"🔍 From User: {message.from_user.first_name if message.from_user else 'None'}")
    
    # Check if this is a new chat members message
    if message.new_chat_members:
        print(f"🎯 🎯 🎯 NEW CHAT MEMBERS DETECTED! 🎯 🎯 🎯")
        await handle_new_members(message)
    else:
        print(f"📝 Regular message: {message.text[:100] if message.text else 'No text'}")

async def handle_new_members(message: types.Message):
    """Handle new members joining"""
    for new_member in message.new_chat_members:
        print(f"👤 New Member Details:")
        print(f"   Name: {new_member.first_name}")
        print(f"   Username: @{new_member.username}")
        print(f"   ID: {new_member.id}")
        print(f"   Is Bot: {new_member.is_bot}")
        
        # Skip if the new member is this bot itself
        if new_member.id == (await bot.get_me()).id:
            print("🤖 Skipping - this is the bot itself")
            continue

        join_time = datetime.utcnow()
        expiry_time = join_time + timedelta(hours=DEFAULT_REMOVE_TIME)
        
        print(f"⏰ Join Time: {join_time}")
        print(f"⏰ Expiry Time: {expiry_time}")

        # Create new invite link
        try:
            invite = await bot.create_chat_invite_link(
                chat_id=MAIN_GROUP,
                member_limit=1,
                expire_date=datetime.now() + timedelta(days=1)
            )
            link_used = invite.invite_link
            print(f"🔗 Invite link created: {link_used}")
        except Exception as e:
            print(f"❌ Invite link error: {e}")
            link_used = "Manual_Add"

        # Save in DB
        cur.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?)", (
            new_member.id,
            new_member.username or "",
            new_member.first_name or "",
            format_time(join_time),
            format_time(expiry_time),
            link_used
        ))
        conn.commit()
        print(f"💾 User saved to database: {new_member.id}")

        # Log to channel
        log_text = f"""
👤 <b>New User Joined Group</b>
├ <b>Group:</b> {message.chat.title}
├ <b>Name:</b> {new_member.first_name or 'N/A'}
├ <b>Username:</b> @{new_member.username or 'N/A'}
├ <b>UserID:</b> <code>{new_member.id}</code>
├ <b>Joined:</b> {format_time(join_time)}
├ <b>Expiry:</b> {format_time(expiry_time)} (20 seconds)
└ <b>Link:</b> {link_used}
"""
        print(f"📝 Sending log to channel...")
        await log_message(log_text)
        print(f"🎯 ✅ USER JOIN LOGGED SUCCESSFULLY!")

# ========== Handle Left Chat Members ==========
@dp.message_handler(content_types=types.ContentType.LEFT_CHAT_MEMBER)
async def handle_left_member(message: types.Message):
    """Handle when user leaves the group"""
    print(f"🚪 User left: {message.left_chat_member.first_name}")

# ========== Background Task ==========
async def check_expiry():
    print("🔄 Starting expiry checker...")
    await asyncio.sleep(5)  # Wait for bot to fully start
    
    while True:
        try:
            now = datetime.utcnow()
            cur.execute("SELECT * FROM users")
            rows = cur.fetchall()

            if rows:
                print(f"🔍 Checking {len(rows)} users for expiry...")

            for row in rows:
                user_id, username, full_name, join_t, expiry_t, link = row
                expiry_time = datetime.strptime(expiry_t, "%Y-%m-%d %H:%M:%S")

                time_diff = (expiry_time - now).total_seconds()
                print(f"⏰ User {user_id} ({full_name}) expires in {time_diff:.0f} seconds")

                if now >= expiry_time:
                    print(f"⏰ 🚨 TIME TO REMOVE: {full_name} (ID: {user_id})")
                    try:
                        # Ban user from group
                        await bot.ban_chat_member(
                            chat_id=MAIN_GROUP,
                            user_id=user_id
                        )
                        
                        removal_msg = f"🚫 Banned {full_name} (<code>{user_id}</code>) after 20 seconds"
                        await log_message(removal_msg)
                        print(removal_msg)

                        # Immediately unban
                        await bot.unban_chat_member(
                            chat_id=MAIN_GROUP,
                            user_id=user_id,
                            only_if_banned=True
                        )

                        # Create new invite link
                        new_invite = await bot.create_chat_invite_link(
                            chat_id=MAIN_GROUP,
                            member_limit=1,
                            expire_date=datetime.now() + timedelta(days=1)
                        )
                        short_link = new_invite.invite_link

                        # Send DM
                        try:
                            await bot.send_message(
                                user_id,
                                f"Your 20-second access has ended. Here is your new invite link: {short_link}"
                            )
                            print(f"📨 DM sent to user {user_id}")
                        except Exception as e:
                            error_msg = f"❌ Could not DM user {user_id}: {e}"
                            await log_message(error_msg)
                            print(error_msg)

                        success_msg = f"✅ Reset completed for {full_name} after 20 seconds\nNew link: {short_link}"
                        await log_message(success_msg)
                        print(success_msg)

                        # Delete from DB
                        cur.execute("DELETE FROM users WHERE user_id=?", (user_id,))
                        conn.commit()
                        print(f"🗑️ User {user_id} removed from database")

                    except Exception as e:
                        error_msg = f"❌ Error processing {user_id}: {e}"
                        await log_message(error_msg)
                        print(error_msg)

            await asyncio.sleep(3)  # Check every 3 seconds for faster testing
        except Exception as e:
            print(f"❌ Check expiry error: {e}")
            await asyncio.sleep(3)

# ========== Bot Commands ==========
@dp.message_handler(commands=["start", "help"])
async def start_cmd(message: types.Message):
    response = """
🤖 <b>Group Manager Bot</b>

✅ <b>Features:</b>
• Auto remove users after 20 seconds
• Send new invite links via DM
• Log all activities

⚙️ <b>Commands:</b>
/start - Show this help
/stats - Show user count
/remove_time 20s - Set remove time
/test - Test bot response
"""
    await message.reply(response)
    await log_message(f"🟢 Bot started by {message.from_user.first_name}")

@dp.message_handler(commands=["test"])
async def test_cmd(message: types.Message):
    """Test if bot is responsive"""
    await message.reply("✅ Bot is working! Try adding a user to the group now.")
    await log_message("🧪 Test command executed")
    print("✅ Test command received in group")

@dp.message_handler(commands=["stats"])
async def stats_cmd(message: types.Message):
    """Check how many users are being tracked"""
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    await message.reply(f"📊 Currently tracking {count} users")
    await log_message(f"📊 Stats checked: {count} users")

@dp.message_handler(commands=["remove_time"])
async def set_remove_time(message: types.Message):
    global DEFAULT_REMOVE_TIME
    try:
        args = message.get_args()
        if args and args.endswith("s"):
            seconds = int(args[:-1])
            DEFAULT_REMOVE_TIME = seconds / 3600
            response = f"✅ Removal time updated to {seconds} seconds"
        elif args and args.endswith("h"):
            hours = int(args[:-1])
            DEFAULT_REMOVE_TIME = hours
            response = f"✅ Removal time updated to {hours} hours"
        else:
            response = "❌ Usage: /remove_time 20s or /remove_time 24h"
        
        await message.reply(response)
        await log_message(response)
    except ValueError:
        await message.reply("❌ Invalid number format")

# ========== Main ==========
async def on_startup(dp):
    """Startup function"""
    # Get bot info
    me = await bot.get_me()
    print(f"🤖 Bot started as: {me.first_name} (@{me.username})")
    print(f"🔑 Bot ID: {me.id}")
    
    print("🔄 Starting expiry checker...")
    asyncio.create_task(check_expiry())
    
    print("📢 Bot is ready and monitoring ALL group messages!")
    print(f"⏰ Default remove time: 20 seconds")
    print(f"👥 Monitoring group ID: {MAIN_GROUP}")
    
    startup_msg = f"""
🤖 <b>Bot Started Successfully!</b>
├ <b>Name:</b> {me.first_name}
├ <b>Username:</b> @{me.username}
├ <b>Remove Time:</b> 20 seconds
└ <b>Monitoring Group:</b> {MAIN_GROUP}
"""
    await log_message(startup_msg)

async def on_shutdown(dp):
    """Shutdown function"""
    print("🛑 Shutting down...")
    await bot.close()

if __name__ == "__main__":
    print("🎯 STARTING BOT WITH ULTRA DEBUG MODE...")
    print(f"🎯 Monitoring group ID: {MAIN_GROUP}")
    print("🔍 ALL messages will be printed for debugging")
    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True
    )
