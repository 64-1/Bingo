# app/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String(100))
    first_name = Column(String(100))
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    role = Column(String(20), default="member")
    created_at = Column(DateTime, default=datetime.utcnow)

    team = relationship("Team", back_populates="members")


class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    join_code = Column(String(10), unique=True)
    score = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("User", back_populates="team")
    submissions = relationship("Submission", back_populates="team")


class Challenge(Base):
    __tablename__ = "challenges"
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    description = Column(Text)
    points = Column(Integer, default=10)


class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    challenge_id = Column(Integer, ForeignKey("challenges.id"))
    submitted_by = Column(Integer, ForeignKey("users.id"))
    media_path = Column(String(300))
    caption = Column(Text)
    status = Column(String(20), default="pending")
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)

    team = relationship("Team", back_populates="submissions")
