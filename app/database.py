# app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, Team, Challenge
import uuid

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./bingoquest.db")

engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if "sqlite" in DB_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables and load sample data if empty."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # --- Insert sample teams if none ---
    if db.query(Team).count() == 0:
        t1 = Team(name="Team Horizon", join_code=str(uuid.uuid4())[:6].upper(), score=50)
        t2 = Team(name="SkyWalkers", join_code=str(uuid.uuid4())[:6].upper(), score=30)
        db.add_all([t1, t2])
        db.commit()
        print("🌱 Sample teams added.")

    # --- Insert sample challenges if none ---
    if db.query(Challenge).count() == 0:
        sample_challenges = [
            Challenge(id=1, title="Beach Selfie", description="Take a team selfie by the sea.", points=10),
            Challenge(id=2, title="Sunset Pose", description="Capture a group photo at sunset.", points=15),
            Challenge(id=3, title="Creative Jump", description="Jump shot with all team members!", points=20),
            Challenge(id=4, title="Hidden Gem", description="Find and photograph a unique spot in Sentosa.", points=25),
            Challenge(id=5, title="Random Kindness", description="Do a kind act and document it.", points=30),
        ]
        db.add_all(sample_challenges)
        db.commit()
        print("🌱 Sample challenges added.")

    db.close()
