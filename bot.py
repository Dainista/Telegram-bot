import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, filters
)
import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

# ---------- Configuration (set these in Railway Variables) ----------
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "<<<PUT_YOUR_TOKEN_HERE>>>")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "bot.db")
# The full public HTTPS webhook URL for your Railway project, e.g.
# https://sabtradebot-production.up.railway.app/webhook
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")

PORT = int(os.getenv("PORT", "8000"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------ Database init ------------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_subscribed INTEGER DEFAULT 0
            )
        """)
        await db.commit()

# ------------------ Handlers ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (id, username, first_name, is_subscribed) VALUES (?, ?, ?, COALESCE((SELECT is_subscribed FROM users WHERE id=?), 0))",
            (user.id, user.username, user.first_name, user.id)
        )
        await db.commit()

    kb = [
        [InlineKeyboardButton("📈 سیگنال‌ها", callback_data="signals")],
        [InlineKeyboardButton("🔔 اشتراک", callback_data="subscribe")],
        [InlineKeyboardButton("📞 تماس با ادمین", callback_data="contact_admin")]
    ]
    await update.message.reply_text("سلام 👋 به SabTradeBot خوش اومدی!", reply_markup=InlineKeyboardMarkup(kb))

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start — شروع\n/help — راهنما\n/adminbroadcast <متن> — ارسال توسط ادمین")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "signals":
        await query.edit_message_text("برای دریافت سیگنال باید اشتراک فعال داشته باشید ✅")
    elif data == "subscribe":
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET is_subscribed = 1 WHERE id = ?", (query.from_user.id,))
            await db.commit()
        await query.edit_message_text("اشتراک شما فعال شد 🎉")
    elif data == "contact_admin":
        await query.edit_message_text("پیام شما به ادمین ارسال شد — در نسخه کامل این پیام فوروارد می‌شود.")

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔️ دسترسی ندارید.")
    text = " ".join(context.args)
    if not text:
        return await update.message.reply_text("مثال:\n/adminbroadcast سلام کاربران!")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM users WHERE is_subscribed=1") as c:
            rows = await c.fetchall()
            for (uid,) in rows:
                try:
                    await context.bot.send_message(chat_id=uid, text=text)
                except Exception:
                    logger.exception(f"Failed sending to {uid}")
    await update.message.reply_text("✅ پیام برای همه ارسال شد.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Forwards received text messages to admin (simple support)
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"پیام از {update.effective_user.id}: {update.message.text}")
    except Exception:
        logger.exception("Failed forwarding message to admin.")
    await update.message.reply_text("پیامت دریافت شد — متشکرم!")

async def scheduled_signal(context: ContextTypes.DEFAULT_TYPE):
    text = "سیگنال نمونه: BTC/USDT — BUY"
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM users WHERE is_subscribed=1") as cursor:
            rows = await cursor.fetchall()
            for (uid,) in rows:
                try:
                    await context.bot.send_message(chat_id=uid, text=text)
                except Exception:
                    logger.exception(f"Failed to send scheduled to {uid}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Exception while handling an update:", exc_info=context.error)

# ------------------ Main (Webhook) ------------------
async def main():
    await init_db()
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("adminbroadcast", admin_broadcast))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.add_error_handler(error_handler)

    # Scheduler for periodic signals (optional)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: application.create_task(scheduled_signal(application)), "interval", minutes=60)
    scheduler.start()

    # Set webhook
    if not WEBHOOK_URL:
        # default domain for Railway; adjust if your Railway project domain differs
        project_domain = os.getenv("RAILWAY_STATIC_URL", "sabtradebot-production.up.railway.app")
        WEBHOOK_URL_FULL = f"https://{project_domain}{WEBHOOK_PATH}"
    else:
        WEBHOOK_URL_FULL = WEBHOOK_URL

    logger.info(f"Setting webhook to: {WEBHOOK_URL_FULL}")
    # set webhook
    await application.bot.set_webhook(WEBHOOK_URL_FULL)

    # run webhook (Application.run_webhook should handle aiohttp server internally)
    await application.run_webhook(listen="0.0.0.0", port=PORT, url_path=WEBHOOK_PATH)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
