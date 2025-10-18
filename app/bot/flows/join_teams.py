from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import Update
from app.database import SessionLocal
from app.models import User, Team
from app.bot.utils import reply
from app.bot.keyboards import main_menu

JT_WAIT_CODE = 1002

async def entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: await update.callback_query.answer()
    await reply(update, "🔑 Send your *team join code*:", parse_mode="Markdown")
    return JT_WAIT_CODE

async def from_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = (update.message.text or "").strip().upper()
    db = SessionLocal()
    try:
        me = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
        if not me: await reply(update, "Please /start first."); return ConversationHandler.END
        if me.team_id: await reply(update, "❌ You’re already in a team."); return ConversationHandler.END
        team = db.query(Team).filter_by(join_code=code).first()
        if not team:
            await reply(update, "❌ Invalid code. Please try again:"); return JT_WAIT_CODE
        me.team_id, me.role = team.id, "member"; db.commit()
        await reply(update, f"🎉 Joined *{team.name}*!", parse_mode="Markdown", reply_markup=main_menu())
    finally:
        db.close()
    return ConversationHandler.END

def conversation():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(entry, pattern=r"^menu:join$")],
        states={ JT_WAIT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, from_text)] },
        fallbacks=[],
        name="join_team_flow",
    )
