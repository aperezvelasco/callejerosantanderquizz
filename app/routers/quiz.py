"""Quiz and leaderboard endpoints."""
from __future__ import annotations

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Float, case, func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.config import get_settings
from ..dependencies import get_session
from ..services.question_generator import Question, QuestionGenerator

router = APIRouter(prefix="/quiz", tags=["quiz"])


@router.get("/daily", response_model=List[schemas.QuestionPayload])
def get_daily_questions(session: Session = Depends(get_session)) -> List[schemas.QuestionPayload]:
    """Return or generate the daily set of questions."""

    today = date.today()
    settings = get_settings()

    existing = (
        session.query(models.DailyQuestion)
        .filter(models.DailyQuestion.question_date == today)
        .order_by(models.DailyQuestion.sequence)
        .all()
    )

    if len(existing) < settings.daily_questions:
        generator = QuestionGenerator()
        generated = generator.generate_for_date(today, settings.daily_questions)
        session.query(models.DailyQuestion).filter(models.DailyQuestion.question_date == today).delete()
        for index, question in enumerate(generated, start=1):
            session.add(
                models.DailyQuestion(
                    question_date=today,
                    sequence=index,
                    question_type=question.question_type,
                    prompt=question.prompt,
                    answer_data={
                        "answer": question.answer,
                        "answer_guide": question.answer_guide,
                        "metadata": question.metadata,
                    },
                )
            )
        session.commit()
        existing = (
            session.query(models.DailyQuestion)
            .filter(models.DailyQuestion.question_date == today)
            .order_by(models.DailyQuestion.sequence)
            .all()
        )

    payload: List[schemas.QuestionPayload] = []
    for item in existing:
        answer_guide = item.answer_data.get("answer_guide", "Responde con calles separadas por comas.")
        payload.append(
            schemas.QuestionPayload(
                id=item.id,
                question_date=item.question_date,
                sequence=item.sequence,
                question_type=item.question_type,
                prompt=item.prompt,
                answer_guide=answer_guide,
            )
        )
    return payload


@router.post("/{question_id}/answer", response_model=schemas.AnswerResult)
def answer_question(
    question_id: int,
    submission: schemas.AnswerSubmission,
    session: Session = Depends(get_session),
    username: str = Query(..., description="Nombre de usuario registrado"),
) -> schemas.AnswerResult:
    """Persist and evaluate a user's answer."""

    user = session.query(models.User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    question = session.get(models.DailyQuestion, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pregunta no encontrada")

    existing = (
        session.query(models.UserAnswer)
            .filter_by(user_id=user.id, question_id=question_id)
            .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La pregunta ya fue respondida")

    reconstructed = _reconstruct_question(question)
    is_correct = reconstructed.evaluate(submission.answer)
    points = 1 if is_correct else 0

    answer_model = models.UserAnswer(
        user_id=user.id,
        question_id=question.id,
        submitted_answer=list(submission.answer),
        is_correct=is_correct,
        awarded_points=points,
    )
    session.add(answer_model)
    session.commit()

    return schemas.AnswerResult(
        question_id=question.id,
        is_correct=is_correct,
        awarded_points=points,
        correct_answer=reconstructed.answer,
    )


@router.get("/leaderboard", response_model=List[schemas.LeaderboardEntry])
def leaderboard(session: Session = Depends(get_session)) -> List[schemas.LeaderboardEntry]:
    """Return the global leaderboard ordered by points and accuracy."""

    results = (
        session.query(
            models.User.username,
            func.count(models.UserAnswer.id),
            func.coalesce(func.sum(models.UserAnswer.awarded_points), 0),
            func.coalesce(
                func.avg(
                    case((models.UserAnswer.is_correct.is_(True), 1), else_=0).cast(Float)
                ),
                0.0,
            ),
        )
        .outerjoin(models.UserAnswer, models.User.id == models.UserAnswer.user_id)
        .group_by(models.User.id)
        .order_by(func.coalesce(func.sum(models.UserAnswer.awarded_points), 0).desc(), models.User.username.asc())
        .all()
    )

    leaderboard_entries: List[schemas.LeaderboardEntry] = []
    for username, answered, points, accuracy in results:
        answered_count = int(answered or 0)
        total_points = int(points or 0)
        accuracy_value = float(accuracy or 0.0)
        leaderboard_entries.append(
            schemas.LeaderboardEntry(
                username=username,
                answered_questions=answered_count,
                total_points=total_points,
                accuracy=round(accuracy_value, 3),
            )
        )

    return leaderboard_entries


def _reconstruct_question(model: models.DailyQuestion) -> Question:
    data = model.answer_data or {}
    answer = data.get("answer", [])
    guide = data.get("answer_guide", "")
    metadata = data.get("metadata", {})
    return Question(
        question_type=model.question_type,
        prompt=model.prompt,
        answer=list(answer),
        answer_guide=guide,
        metadata=metadata,
    )
