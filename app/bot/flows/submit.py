import os, uuid
from datetime import datetime
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, filters
from telegram import Update, ReplyKeyboardRemove
from app.database import SessionLocal
from app.models import User, Challenge, Submission
from app.bot.utils import reply

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./app/static/uploads")
MAX_FILE_SIZE = 20 * 1024 * 1024
AWAIT_CHALLENGE_ID, AWAIT_MEDIA, AWAIT_CAPTION = range(2001, 2004)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        me = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
        if not me: await reply(update, "Please /start first."); return ConversationHandler.END
        if not me.team_id: await reply(update, "Join or create a team first."); return ConversationHandler.END
        if me.role != "leader": await reply(update, "❌ Only leaders can submit."); return ConversationHandler.END
        chals = db.query(Challenge).order_by(Challenge.id).all()
        if not chals: await reply(update, "No challenges available."); return ConversationHandler.END
        msg = "🎯 *Choose Challenge ID:*\n" + "\n".join([f"• {c.id} — {c.title}" for c in chals])
        await reply(update, msg + "\n\nEnter the challenge ID:", parse_mode="Markdown")
        return AWAIT_CHALLENGE_ID
    finally:
        db.close()

async def receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        txt = (update.message.text or "").strip()
        if not txt.isdigit():
            await reply(update, "❌ Enter a number, e.g. 3"); return AWAIT_CHALLENGE_ID
        cid = int(txt)
        chal = db.query(Challenge).filter_by(id=cid).first()
        if not chal: await reply(update, "❌ Challenge not found."); return AWAIT_CHALLENGE_ID
        me = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
        approved = db.query(Submission).filter_by(team_id=me.team_id, challenge_id=cid, status="approved").first()
        if approved: await reply(update, "✅ Already approved for this challenge."); return ConversationHandler.END
        context.user_data["challenge_id"] = cid
        context.user_data["challenge_title"] = chal.title
        await reply(update, f"Now send a *photo or video* as proof for *{chal.title}*.", parse_mode="Markdown")
        return AWAIT_MEDIA
    finally:
        db.close()

async def receive_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = update.get_bot()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    uid = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    if update.message.photo:
        tg_file = await bot.get_file(update.message.photo[-1].file_id)
        if getattr(tg_file, "file_size", 0) > MAX_FILE_SIZE:
            await reply(update, "❌ Max size 20MB. Send a smaller photo."); return AWAIT_MEDIA
        path = f"{UPLOAD_DIR}/{uid}.jpg"
    elif update.message.video:
        tg_file = await bot.get_file(update.message.video.file_id)
        if getattr(tg_file, "file_size", 0) > MAX_FILE_SIZE:
            await reply(update, "❌ Max size 20MB. Send a smaller video."); return AWAIT_MEDIA
        path = f"{UPLOAD_DIR}/{uid}.mp4"
    else:
        await reply(update, "Please send a *photo or video*.", parse_mode="Markdown"); return AWAIT_MEDIA
    await tg_file.download_to_drive(path)
    context.user_data["media_path"] = path
    await reply(update, "✅ Media received. Now send a short caption:")
    return AWAIT_CAPTION

async def receive_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        caption = (update.message.text or "").strip()
        if len(caption) < 3:
            await reply(update, "Caption too short, try again:"); return AWAIT_CAPTION
        me = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
        sub = Submission(
            team_id=me.team_id,
            challenge_id=context.user_data["challenge_id"],
            submitted_by=me.id,
            media_path=context.user_data["media_path"],
            caption=caption,
            status="pending"
        )
        db.add(sub); db.commit()
        await reply(update,
            f"📝 Submitted *{context.user_data.get('challenge_title','challenge')}*.\nStatus: ⏳ Pending review.",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END
    except Exception:
        db.rollback()
        try:
            if "media_path" in context.user_data and os.path.exists(context.user_data["media_path"]):
                os.remove(context.user_data["media_path"])
        except: pass
        context.user_data.clear()
        await reply(update, "❌ Couldn’t save submission. Please /submit again.")
        return ConversationHandler.END
    finally:
        db.close()

def conversation():
    return ConversationHandler(
        entry_points=[CommandHandler("submit", start)],
        states={
            AWAIT_CHALLENGE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id)],
            AWAIT_MEDIA: [MessageHandler(filters.PHOTO | filters.VIDEO, receive_media)],
            AWAIT_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_caption)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
        name="submit_flow",
    )
