"""Pydantic schemas for API payloads."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Sequence

from pydantic import BaseModel, Field, EmailStr, model_validator


class UserCreate(BaseModel):
    """Schema for creating a new user with double-checked email."""

    email: EmailStr
    confirm_email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)

    @model_validator(mode="after")
    def verify_emails_match(self) -> UserCreate:
        """Verify that email and confirm_email fields match.

        Returns
        -------
        UserCreate
            The validated UserCreate model instance.

        Raises
        ------
        ValueError
            If the emails do not match.
        """
        if self.email != self.confirm_email:
            raise ValueError("Los correos electrónicos no coinciden")
        return self


class UserLogin(BaseModel):
    """Schema for user login using email and password."""

    email: EmailStr
    password: str


class UserPublic(BaseModel):
    """Public representation of user account details."""

    id: int
    username: str
    created_at: datetime

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class QuestionPayload(BaseModel):
    """Payload representing a daily question without answers."""

    id: int
    question_date: date
    sequence: int
    question_type: str
    prompt: str
    answer_guide: str
    choices: List[str] = Field(default_factory=list)
    answered: bool = False
    was_correct: bool | None = None

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class AnswerSubmission(BaseModel):
    """Payload for submitting an answer to a question."""

    answer: Sequence[str]


class AnswerResult(BaseModel):
    """Result of an answer submission evaluation."""

    question_id: int
    is_correct: bool
    awarded_points: int
    correct_answer: List[str]


class LeaderboardEntry(BaseModel):
    """Schema representing an entry in the leaderboard."""

    username: str
    answered_questions: int
    total_points: int
    accuracy: float


class GuessSubmission(BaseModel):
    """Payload for map click guess evaluation."""

    street_name: str
    lat: float
    lng: float
    username: str
