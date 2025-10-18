import uuid
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import Update
from app.database import SessionLocal
from app.models import User, Team
from app.bot.utils import reply
from app.bot.keyboards import main_menu

CT_WAIT_NAME = 1001  # unique int

def _unique_code(db):
    for _ in range(10):
        code = uuid.uuid4().hex[:6].upper()
        if not db.query(Team).filter_by(join_code=code).first():
            return code
    return uuid.uuid4().hex[:8].upper()

async def entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: await update.callback_query.answer()
    await reply(update, "🆕 Send your *team name* (3–50 chars):", parse_mode="Markdown")
    return CT_WAIT_NAME

async def from_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = (update.message.text or "").strip()
    if not (3 <= len(name) <= 50):
        await reply(update, "❌ Team name must be 3–50 characters. Try again:")
        return CT_WAIT_NAME
    db = SessionLocal()
    try:
        me = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
        if not me: await reply(update, "Please /start first."); return ConversationHandler.END
        if me.team_id: await reply(update, "❌ You’re already in a team."); return ConversationHandler.END
        if db.query(Team).filter_by(name=name).first():
            await reply(update, "❌ That team name already exists. Try another:")
            return CT_WAIT_NAME
        code = _unique_code(db)
        t = Team(name=name, join_code=code)
        db.add(t); db.commit()
        me.team_id, me.role = t.id, "leader"; db.commit()
        await reply(update, f"✅ Team *{name}* created!\nShare join code: `{code}`",
                    parse_mode="Markdown", reply_markup=main_menu())
    finally:
        db.close()
    return ConversationHandler.END

def conversation():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(entry, pattern=r"^menu:create$")],
        states={ CT_WAIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, from_text)] },
        fallbacks=[],
        name="create_team_flow",
    )
