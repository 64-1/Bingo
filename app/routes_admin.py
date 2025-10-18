# app/routes_admin.py
import os
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Team, Submission, Challenge, User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ADMIN_PASS = os.getenv("ADMIN_PASS", "letmein")  # simple shared key in query string


def db_session() -> Session:
    return SessionLocal()


# ---------- Public Leaderboard ----------
@router.get("/web/leaderboard", response_class=HTMLResponse)
def leaderboard_page(request: Request):
    """Renders a small HTML page that auto-refreshes leaderboard via JS."""
    return templates.TemplateResponse("leaderboard.html", {"request": request})


@router.get("/api/leaderboard")
def leaderboard_api():
    db = db_session()
    teams = db.query(Team).order_by(Team.score.desc(), Team.created_at.asc()).limit(50).all()
    payload = [
        {"rank": i + 1, "team": t.name, "score": t.score}
        for i, t in enumerate(teams)
    ]
    db.close()
    return JSONResponse({"data": payload})


# ---------- Simple Admin (query key) ----------
def check_admin_key(key: str | None):
    if key != ADMIN_PASS:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/web/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, key: str | None = None):
    check_admin_key(key)
    db = db_session()

    pending = (
        db.query(Submission)
        .filter(Submission.status == "pending")
        .order_by(Submission.submitted_at.asc())
        .all()
    )
    rows = []
    for s in pending:
        team = db.query(Team).filter_by(id=s.team_id).first()
        chal = db.query(Challenge).filter_by(id=s.challenge_id).first()
        user = db.query(User).filter_by(id=s.submitted_by).first()
        rows.append(
            {
                "id": s.id,
                "team": team.name if team else f"#{s.team_id}",
                "challenge": f"{chal.id} - {chal.title}" if chal else f"#{s.challenge_id}",
                "points": chal.points if chal else 0,
                "caption": s.caption or "",
                "media_url": f"/web/media/{s.id}?key={key}",
                "submitted_by": user.first_name or user.username if user else "user",
                "submitted_at": s.submitted_at.strftime("%Y-%m-%d %H:%M"),
            }
        )
    db.close()

    html = [
        "<h2>🛠️ BingoQuest Admin</h2>",
        f"<p>Pending submissions: <b>{len(rows)}</b></p>",
        "<table border='1' cellpadding='6' cellspacing='0'>",
        "<tr><th>ID</th><th>Team</th><th>Challenge</th><th>Points</th><th>Media</th><th>Caption</th><th>By</th><th>Submitted</th><th>Actions</th></tr>",
    ]
    for r in rows:
        approve_url = f"/web/admin/approve/{r['id']}?key={key}"
        reject_url = f"/web/admin/reject/{r['id']}?key={key}"
        html.append(
            "<tr>"
            f"<td>{r['id']}</td>"
            f"<td>{r['team']}</td>"
            f"<td>{r['challenge']}</td>"
            f"<td>{r['points']}</td>"
            f"<td><a href='{r['media_url']}' target='_blank'>view</a></td>"
            f"<td>{r['caption']}</td>"
            f"<td>{r['submitted_by']}</td>"
            f"<td>{r['submitted_at']}</td>"
            f"<td><a href='{approve_url}'>✅ Approve</a> | <a href='{reject_url}'>❌ Reject</a></td>"
            "</tr>"
        )
    html.append("</table>")
    return HTMLResponse("".join(html))


@router.get("/web/media/{submission_id}")
def serve_media(submission_id: int, key: str | None = None):
    """Serve media file for a submission (admin only)."""
    check_admin_key(key)
    db = db_session()
    s = db.query(Submission).filter_by(id=submission_id).first()
    db.close()
    if not s or not s.media_path or not os.path.exists(s.media_path):
        raise HTTPException(status_code=404, detail="Media not found")

    # rudimentary content type by extension
    ext = os.path.splitext(s.media_path)[-1].lower()
    media_type = "image/jpeg" if ext in [".jpg", ".jpeg", ".png"] else "video/mp4"
    return FileResponse(s.media_path, media_type=media_type)


@router.get("/web/admin/approve/{submission_id}")
def approve_submission(submission_id: int, key: str | None = None):
    check_admin_key(key)
    db = db_session()
    s = db.query(Submission).filter_by(id=submission_id).first()
    if not s or s.status != "pending":
        db.close()
        raise HTTPException(status_code=404, detail="Submission not found")

    chal = db.query(Challenge).filter_by(id=s.challenge_id).first()
    team = db.query(Team).filter_by(id=s.team_id).first()
    points = chal.points if chal else 0

    s.status = "approved"
    s.reviewed_by = "admin"
    s.reviewed_at = datetime.utcnow()
    if team:
        team.score = (team.score or 0) + points

    db.commit()
    db.close()
    return RedirectResponse(url=f"/web/admin?key={key}", status_code=302)


@router.get("/web/admin/reject/{submission_id}")
def reject_submission(submission_id: int, key: str | None = None):
    check_admin_key(key)
    db = db_session()
    s = db.query(Submission).filter_by(id=submission_id).first()
    if not s or s.status != "pending":
        db.close()
        raise HTTPException(status_code=404, detail="Submission not found")

    s.status = "rejected"
    s.reviewed_by = "admin"
    s.reviewed_at = datetime.utcnow()
    db.commit()
    db.close()
    return RedirectResponse(url=f"/web/admin?key={key}", status_code=302)
