from telegram.ext import ContextTypes, CommandHandler
from telegram import Update
from app.database import SessionLocal
from app.models import User, Team, Challenge, Submission
from app.bot.utils import reply

async def team_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        me = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
        if not me:
            await reply(update, "Please /start first."); return
        if not me.team_id:
            await reply(update, "You’re not in a team yet. Use *Create Team* or *Join Team*.", parse_mode="Markdown"); return
        t = db.query(Team).filter_by(id=me.team_id).first()
        if not t: await reply(update, "❌ Team not found. Contact admin."); return
        members = db.query(User).filter_by(team_id=t.id).all()
        roster = "\n".join(f"• {m.first_name or m.username or 'Member'}{' 👑' if m.role=='leader' else ''}" for m in members) or "No members yet."
        await reply(update,
            f"👥 *Team:* {t.name}\n📊 Score: {t.score}\n🔑 Code: `{t.join_code}`\n\n*Members:*\n{roster}",
            parse_mode="Markdown"
        )
    finally:
        db.close()

async def board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        chals = db.query(Challenge).order_by(Challenge.id).all()
        if not chals: await reply(update, "No challenges yet."); return
        text = "🎯 *Bingo Board*\n\n" + "\n".join([f"• *{c.id}.* {c.title} ({c.points} pts)" for c in chals])
        await reply(update, text, parse_mode="Markdown")
    finally:
        db.close()

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        teams = db.query(Team).order_by(Team.score.desc(), Team.created_at.asc()).limit(10).all()
        if not teams: await reply(update, "No teams yet."); return
        medals = ["🥇","🥈","🥉"]
        rows = [f"{medals[i-1] if i<=3 else f'{i}.'} {t.name} — {t.score} pts" for i,t in enumerate(teams,1)]
        await reply(update, "🏆 *Leaderboard*\n\n" + "\n".join(rows), parse_mode="Markdown")
    finally:
        db.close()

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        me = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
        if not me or not me.team_id:
            await reply(update, "Join a team first: *Create Team* or *Join Team*.", parse_mode="Markdown"); return
        subs = db.query(Submission).filter_by(team_id=me.team_id).all()
        if not subs: await reply(update, "No submissions yet. Try /submit"); return
        by = {"approved":[], "pending":[], "rejected":[]}
        for s in subs: by[s.status].append(s.challenge_id)
        await reply(update,
            f"📌 *Team Progress*\n"
            f"✅ Approved: {sorted(by['approved'])}\n"
            f"⏳ Pending: {sorted(by['pending'])}\n"
            f"❌ Rejected: {sorted(by['rejected'])}\n",
            parse_mode="Markdown"
        )
    finally:
        db.close()

def handlers():
    return [
        CommandHandler("team", team_info),
        CommandHandler("board", board),
        CommandHandler("leaderboard", leaderboard),
        CommandHandler("status", status),
    ]
