from telegram.ext import ContextTypes, CommandHandler
from telegram import Update
from app.database import SessionLocal
from app.models import User
from app.bot.keyboards import main_menu, pretty_help_text
from app.bot.utils import reply

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=u.id).first()
        if not user:
            db.add(User(telegram_id=u.id, username=u.username, first_name=u.first_name))
            db.commit()
        await reply(update,
            "👋 Welcome to *BingoQuest*! Use the buttons below to get started.\n\n" + pretty_help_text(),
            parse_mode="Markdown", reply_markup=main_menu()
        )
    finally:
        db.close()

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(update, "🔽 Quick actions:", reply_markup=main_menu())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(update, pretty_help_text(), parse_mode="Markdown", reply_markup=main_menu())

def handlers():
    return [
        CommandHandler("start", start),
        CommandHandler("menu", menu),
        CommandHandler("help", help_cmd),
    ]
