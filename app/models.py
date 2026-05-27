"""Database models."""

from __future__ import annotations

from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    """Registered user of the quiz application."""

    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True)
    username: str = Column(String(80), nullable=False, unique=True, index=True)
    password_hash: str = Column(String(128), nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    answers = relationship(
        "UserAnswer", back_populates="user", cascade="all, delete-orphan"
    )
    map_guesses = relationship(
        "MapGuess", back_populates="user", cascade="all, delete-orphan"
    )


class DailyQuestion(Base):
    """Question generated for a specific day."""

    __tablename__ = "daily_questions"
    __table_args__ = (
        UniqueConstraint("question_date", "sequence", name="uq_daily_question"),
    )

    id: int = Column(Integer, primary_key=True)
    question_date: date = Column(Date, nullable=False, index=True)
    sequence: int = Column(Integer, nullable=False)
    question_type: str = Column(String(40), nullable=False)
    prompt: str = Column(String(500), nullable=False)
    answer_data = Column(JSON, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    answers = relationship(
        "UserAnswer", back_populates="question", cascade="all, delete-orphan"
    )


class UserAnswer(Base):
    """Answer submitted by a user."""

    __tablename__ = "user_answers"
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_user_question"),
    )

    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: int = Column(
        Integer,
        ForeignKey("daily_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    submitted_answer = Column(JSON, nullable=False)
    is_correct: bool = Column(Boolean, default=False, nullable=False)
    awarded_points: int = Column(Integer, default=0, nullable=False)
    answered_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="answers")
    question = relationship("DailyQuestion", back_populates="answers")


class MapGuess(Base):
    """A map guess submitted by a registered user."""

    __tablename__ = "map_guesses"

    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    street_name: str = Column(String(100), nullable=False)
    lat: float = Column(Float, nullable=False)
    lng: float = Column(Float, nullable=False)
    distance_meters: float = Column(Float, nullable=False)
    is_correct: bool = Column(Boolean, default=False, nullable=False)
    awarded_points: int = Column(Integer, default=0, nullable=False)
    guessed_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="map_guesses")
