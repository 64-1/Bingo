# app/main.py
import os
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from telegram import Update
from telegram.ext import Application
from .bot import setup_bot_handlers
from .database import init_db
from .routes_admin import router as admin_router
from telegram import BotCommand
import logging
logger = logging.getLogger("uvicorn")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8390031344:AAEtB9GsqUf8ANJVk7lmbTD56ZxiqrUwTDg")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://bingoquest.onrender.com/webhook/" + BOT_TOKEN)

app = FastAPI(title="BingoQuest Telegram Bot")

# Telegram Application (singleton)
telegram_app = Application.builder().token(BOT_TOKEN).build()
setup_bot_handlers(telegram_app)

# Register admin & leaderboard routes
app.include_router(admin_router)

@app.on_event("startup")
async def on_startup():
    init_db()
    await telegram_app.initialize()  # <-- you already added this
    # 1) Set webhook
    await telegram_app.bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=False)
    # 2) Set side-menu commands
    from telegram import BotCommand
    # ...
    await telegram_app.bot.set_my_commands([
        BotCommand("menu", "Open buttons"),
        BotCommand("create_team", "Create a team (alt)"),
        BotCommand("join", "Join a team (alt)"),
        BotCommand("board", "See challenges"),
        BotCommand("submit", "Submit proof (leader)"),
        BotCommand("leaderboard", "Top teams"),
        BotCommand("team", "My team"),
        BotCommand("status", "Team progress"),
        BotCommand("help", "How to play"),
        BotCommand("cancel", "Cancel current action"),
    ])

    info = await telegram_app.bot.get_webhook_info()
    logger.info(f"✅ Webhook set. URL={info.url} Pending={info.pending_update_count}")


@app.post("/webhook/{token}")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks, token: str):
    if token != BOT_TOKEN:
        return {"error": "Invalid token"}
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    background_tasks.add_task(telegram_app.process_update, update)
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def root():
    return "<h2>🏕️ BingoQuest Bot is running!</h2><p>Visit /web/leaderboard to view scores.</p>"


@app.on_event("shutdown")
async def on_shutdown():
    await telegram_app.shutdown()
    await telegram_app.stop()
    logger.info("🛑 Telegram app stopped.")