# app/bot.py
import os, uuid
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, CallbackQueryHandler, filters
)
from app.models import User, Team, Challenge, Submission
from app.database import SessionLocal

# -------- Config --------
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./app/static/uploads")
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# Submission states
AWAIT_CHALLENGE_ID, AWAIT_MEDIA, AWAIT_CAPTION = range(3)
# Create/Join flows
CT_WAIT_NAME, JT_WAIT_CODE = range(3, 5)

# -------- Helpers --------
def _db(): return SessionLocal()

def _unique_code(db):
    for _ in range(10):
        code = uuid.uuid4().hex[:6].upper()
        if not db.query(Team).filter_by(join_code=code).first():
            return code
    return uuid.uuid4().hex[:8].upper()

# unified reply that works for both typed commands and button clicks
async def reply(update: Update, text: str, **kwargs):
    if update.message:
        return await update.message.reply_text(text, **kwargs)
    if update.callback_query:
        return await update.callback_query.message.reply_text(text, **kwargs)

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 Create Team", callback_data="menu:create")],
        [InlineKeyboardButton("🔑 Join Team", callback_data="menu:join")],
        [
            InlineKeyboardButton("🎯 Board", callback_data="menu:board"),
            InlineKeyboardButton("📸 Submit", callback_data="menu:submit"),
        ],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="menu:leaderboard"),
            InlineKeyboardButton("👥 My Team", callback_data="menu:team"),
        ],
    ])

def pretty_help_text():
    return (
        "📖 *How to use BingoQuest*\n\n"
        "/create_team\nCreate a new team (or use the button)\n\n"
        "/join\nJoin a team with code (or use the button)\n\n"
        "/team\nSee team members, score, join code\n\n"
        "/board\nList all challenges and points\n\n"
        "/submit\nLeader uploads photo/video proof\n\n"
        "/leaderboard\nSee top teams\n\n"
        "/status\nSee your team’s approved/pending\n\n"
        "/menu\nShow the quick buttons again"
    )

# -------- Public Commands --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db = _db()
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

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(update, "🔽 Quick actions:", reply_markup=main_menu())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(update, pretty_help_text(), parse_mode="Markdown", reply_markup=main_menu())

# (Optional) legacy power-user commands that still work
async def create_team_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await reply(update, "Use the *Create Team* button or: `/create_team <name>`", parse_mode="Markdown")
        return
    update.message.text = " ".join(context.args)
    return await create_team_from_text(update, context)

async def join_team_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await reply(update, "Use the *Join Team* button or: `/join <code>`", parse_mode="Markdown")
        return
    update.message.text = context.args[0]
    return await join_team_from_text(update, context)

# -------- Inline Menu Actions (non-conversation) --------
async def menu_board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: await update.callback_query.answer()
    return await board(update, context)

async def menu_submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: await update.callback_query.answer()
    return await submit_start(update, context)

async def menu_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: await update.callback_query.answer()
    return await leaderboard(update, context)

async def menu_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: await update.callback_query.answer()
    return await team_info(update, context)

# -------- Create Team (Conversation) --------
async def menu_create_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # entry point for create flow via button
    if update.callback_query: await update.callback_query.answer()
    await reply(update, "🆕 Send your *team name* (3–50 chars):", parse_mode="Markdown")
    return CT_WAIT_NAME

async def create_team_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = (update.message.text or "").strip()
    if not (3 <= len(name) <= 50):
        await reply(update, "❌ Team name must be 3–50 characters. Try again:")
        return CT_WAIT_NAME
    db = _db()
    try:
        me = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
        if not me:
            await reply(update, "Please /start first."); return ConversationHandler.END
        if me.team_id:
            await reply(update, "❌ You’re already in a team."); return ConversationHandler.END
        if db.query(Team).filter_by(name=name).first():
            await reply(update, "❌ That team name already exists. Try another:")
            return CT_WAIT_NAME
        code = _unique_code(db)
        t = Team(name=name, join_code=code)
        db.add(t); db.commit()
        me.team_id, me.role = t.id, "leader"; db.commit()
        await reply(update,
            f"✅ Team *{name}* created!\nShare this join code with members: `{code}`",
            parse_mode="Markdown", reply_markup=main_menu()
        )
    finally:
        db.close()
    return ConversationHandler.END

# -------- Join Team (Conversation) --------
async def menu_join_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: await update.callback_query.answer()
    await reply(update, "🔑 Send your *team join code*:", parse_mode="Markdown")
    return JT_WAIT_CODE

async def join_team_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = (update.message.text or "").strip().upper()
    db = _db()
    try:
        me = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
        if not me:
            await reply(update, "Please /start first."); return ConversationHandler.END
        if me.team_id:
            await reply(update, "❌ You’re already in a team."); return ConversationHandler.END
        team = db.query(Team).filter_by(join_code=code).first()
        if not team:
            await reply(update, "❌ Invalid code. Please try again:")
            return JT_WAIT_CODE
        me.team_id, me.role = team.id, "member"; db.commit()
        await reply(update, f"🎉 Joined *{team.name}*!", parse_mode="Markdown", reply_markup=main_menu())
    finally:
        db.close()
    return ConversationHandler.END

# -------- Team / Board / Leaderboard / Status --------
async def team_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _db()
    try:
        me = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
        if not me:
            await reply(update, "Please /start first.")
            return
        if not me.team_id:
            await reply(update, "You’re not in a team yet. Use *Create Team* or *Join Team*.", parse_mode="Markdown")
            return
        t = db.query(Team).filter_by(id=me.team_id).first()
        if not t:
            await reply(update, "❌ Team not found. Please contact an admin.")
            return
        members = db.query(User).filter_by(team_id=t.id).all()
        roster = "\n".join(
            f"• {m.first_name or m.username or 'Member'}{' 👑' if m.role == 'leader' else ''}"
            for m in members
        ) or "No members yet."
        await reply(
            update,
            f"👥 *Team:* {t.name}\n"
            f"📊 Score: {t.score}\n"
            f"🔑 Code: `{t.join_code}`\n\n"
            f"*Members:*\n{roster}",
            parse_mode="Markdown"
        )
    finally:
        db.close()

async def board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _db()
    try:
        challenges = db.query(Challenge).order_by(Challenge.id).all()
        if not challenges:
            await reply(update, "No challenges yet."); return
        text = "🎯 *Bingo Board*\n\n" + "\n".join([f"• *{c.id}.* {c.title} ({c.points} pts)" for c in challenges])
        await reply(update, text, parse_mode="Markdown")
    finally:
        db.close()

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _db()
    try:
        teams = db.query(Team).order_by(Team.score.desc(), Team.created_at.asc()).limit(10).all()
        if not teams:
            await reply(update, "No teams yet."); return
        medals = ["🥇","🥈","🥉"]; rows=[]
        for i,t in enumerate(teams,1):
            rows.append(f"{medals[i-1] if i<=3 else f'{i}.'} {t.name} — {t.score} pts")
        await reply(update, "🏆 *Leaderboard*\n\n" + "\n".join(rows), parse_mode="Markdown")
    finally:
        db.close()

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _db()
    try:
        me = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
        if not me or not me.team_id:
            await reply(update, "Join a team first: *Create Team* or *Join Team*.", parse_mode="Markdown"); return
        subs = db.query(Submission).filter_by(team_id=me.team_id).all()
        if not subs:
            await reply(update, "No submissions yet. Try /submit"); return
        by = {"approved":[], "pending":[], "rejected":[]}
        for s in subs: by[s.status].append(s.challenge_id)
        msg = (
            f"📌 *Team Progress*\n"
            f"✅ Approved: {sorted(by['approved'])}\n"
            f"⏳ Pending: {sorted(by['pending'])}\n"
            f"❌ Rejected: {sorted(by['rejected'])}\n"
        )
        await reply(update, msg, parse_mode="Markdown")
    finally:
        db.close()

# -------- Submit Conversation --------
async def submit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _db()
    try:
        me = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
        if not me:
            await reply(update, "Please /start first."); return ConversationHandler.END
        if not me.team_id:
            await reply(update, "Join or create a team first."); return ConversationHandler.END
        if me.role != "leader":
            await reply(update, "❌ Only leaders can submit."); return ConversationHandler.END
        challenges = db.query(Challenge).order_by(Challenge.id).all()
        if not challenges:
            await reply(update, "No challenges available."); return ConversationHandler.END
        msg = "🎯 *Choose Challenge ID:*\n" + "\n".join([f"• {c.id} — {c.title}" for c in challenges])
        await reply(update, msg + "\n\nEnter the challenge ID:", parse_mode="Markdown")
        return AWAIT_CHALLENGE_ID
    finally:
        db.close()

async def receive_challenge_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _db()
    try:
        txt = (update.message.text or "").strip()
        if not txt.isdigit():
            await reply(update, "❌ Enter a number, e.g. 3"); return AWAIT_CHALLENGE_ID
        cid = int(txt)
        chal = db.query(Challenge).filter_by(id=cid).first()
        if not chal:
            await reply(update, "❌ Challenge not found."); return AWAIT_CHALLENGE_ID
        me = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
        already = db.query(Submission).filter_by(team_id=me.team_id, challenge_id=cid, status="approved").first()
        if already:
            await reply(update, "✅ Already approved for this challenge."); return ConversationHandler.END
        context.user_data["challenge_id"] = cid
        context.user_data["challenge_title"] = chal.title
        await reply(update, f"Now send a *photo or video* as proof for *{chal.title}*.", parse_mode="Markdown")
        return AWAIT_MEDIA
    finally:
        db.close()

async def receive_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = update.get_bot()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    unique = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    if update.message.photo:
        tg_file = await bot.get_file(update.message.photo[-1].file_id)
        if getattr(tg_file, "file_size", 0) and tg_file.file_size > MAX_FILE_SIZE:
            await reply(update, "❌ Max size 20MB. Send a smaller photo.")
            return AWAIT_MEDIA
        path = f"{UPLOAD_DIR}/{unique}.jpg"
    elif update.message.video:
        tg_file = await bot.get_file(update.message.video.file_id)
        if getattr(tg_file, "file_size", 0) and tg_file.file_size > MAX_FILE_SIZE:
            await reply(update, "❌ Max size 20MB. Send a smaller video.")
            return AWAIT_MEDIA
        path = f"{UPLOAD_DIR}/{unique}.mp4"
    else:
        await reply(update, "Please send a *photo or video*.", parse_mode="Markdown")
        return AWAIT_MEDIA
    await tg_file.download_to_drive(path)
    context.user_data["media_path"] = path
    await reply(update, "✅ Media received. Now send a short caption:")
    return AWAIT_CAPTION

async def receive_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = _db()
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
            f"📝 Submitted *{context.user_data.get('challenge_title','challenge')}*.\n"
            "Status: ⏳ Pending review.",
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

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if "media_path" in context.user_data and os.path.exists(context.user_data["media_path"]):
            os.remove(context.user_data["media_path"])
    except: pass
    context.user_data.clear()
    await reply(update, "❌ Submission cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# -------- Wiring (called from main.py) --------
def setup_bot_handlers(app: Application):
    # 1) Conversations that START on button clicks — add these FIRST
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_create_entry, pattern=r"^menu:create$")],
        states={ CT_WAIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_team_from_text)] },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="create_team_flow",
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_join_entry, pattern=r"^menu:join$")],
        states={ JT_WAIT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, join_team_from_text)] },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="join_team_flow",
    ))

    # 2) Button actions that are NOT conversations
    app.add_handler(CallbackQueryHandler(menu_board, pattern=r"^menu:board$"))
    app.add_handler(CallbackQueryHandler(menu_submit, pattern=r"^menu:submit$"))
    app.add_handler(CallbackQueryHandler(menu_leaderboard, pattern=r"^menu:leaderboard$"))
    app.add_handler(CallbackQueryHandler(menu_team, pattern=r"^menu:team$"))

    # 3) Submit conversation (also reachable via /submit)
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("submit", submit_start)],
        states={
            AWAIT_CHALLENGE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_challenge_id)],
            AWAIT_MEDIA: [MessageHandler(filters.PHOTO | filters.VIDEO, receive_media)],
            AWAIT_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_caption)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="submit_flow",
    ))

    # 4) Normal commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("create_team", create_team_cmd))
    app.add_handler(CommandHandler("join", join_team_cmd))
    app.add_handler(CommandHandler("team", team_info))
    app.add_handler(CommandHandler("board", board))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("status", status))

    # 5) Nice error logging (optional)
    async def on_error(update_obj: object, context: ContextTypes.DEFAULT_TYPE):
        print(f"[telegram-error] err={context.error} update={getattr(update_obj,'to_dict',lambda: str(update_obj))()}")
    app.add_error_handler(on_error)
