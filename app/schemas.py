"""Pydantic schemas for API payloads."""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Sequence

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)


class UserLogin(BaseModel):
    username: str
    password: str


class UserPublic(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True


class QuestionPayload(BaseModel):
    id: int
    question_date: date
    sequence: int
    question_type: str
    prompt: str
    answer_guide: str

    class Config:
        from_attributes = True


class AnswerSubmission(BaseModel):
    answer: Sequence[str]


class AnswerResult(BaseModel):
    question_id: int
    is_correct: bool
    awarded_points: int
    correct_answer: List[str]


class LeaderboardEntry(BaseModel):
    username: str
    answered_questions: int
    total_points: int
    accuracy: float
