"""Quiz and leaderboard endpoints."""

from __future__ import annotations

import json
import random
from datetime import date, datetime, time
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.config import get_settings
from ..dependencies import get_session
from ..services.callejero import get_street_graph
from ..services.question_generator import Question, QuestionGenerator

router = APIRouter(prefix="/quiz", tags=["quiz"])


@router.get("/daily", response_model=List[schemas.QuestionPayload])
def get_daily_questions(
    username: str | None = Query(None, description="Nombre de usuario registrado"),
    session: Session = Depends(get_session),
) -> List[schemas.QuestionPayload]:
    """Return or generate the daily set of questions, including user answer status.

    Parameters
    ----------
    username : str | None
        The username of the player checking questions.
    session : Session
        The database session.

    Returns
    -------
    List[schemas.QuestionPayload]
        List of daily questions.
    """

    today = date.today()
    settings = get_settings()

    existing = (
        session.query(models.DailyQuestion)
        .filter(models.DailyQuestion.question_date == today)
        .order_by(models.DailyQuestion.sequence)
        .all()
    )

    # Force regeneration if today's questions don't have "choices" stored or are of legacy types
    has_legacy = any(
        item.question_type == "OPEN_INTERSECTIONS"
        or not item.answer_data
        or "choices" not in item.answer_data
        for item in existing
    )

    if len(existing) < settings.daily_questions or has_legacy:
        generator = QuestionGenerator()
        generated = generator.generate_for_date(today, settings.daily_questions)
        session.query(models.DailyQuestion).filter(
            models.DailyQuestion.question_date == today
        ).delete()
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
                        "choices": question.choices,
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
    user = (
        session.query(models.User).filter_by(username=username).first()
        if username
        else None
    )
    for item in existing:
        answer_data = item.answer_data or {}
        answer_guide = answer_data.get(
            "answer_guide", "Responde con calles separadas por comas."
        )
        choices = answer_data.get("choices", [])
        answered = False
        was_correct = None
        if user:
            ans = (
                session.query(models.UserAnswer)
                .filter_by(user_id=user.id, question_id=item.id)
                .first()
            )
            if ans:
                answered = True
                was_correct = ans.is_correct
        payload.append(
            schemas.QuestionPayload(
                id=item.id,
                question_date=item.question_date,
                sequence=item.sequence,
                question_type=item.question_type,
                prompt=item.prompt,
                answer_guide=answer_guide,
                choices=choices,
                answered=answered,
                was_correct=was_correct,
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

    question = session.get(models.DailyQuestion, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pregunta no encontrada"
        )

    if user:
        existing = (
            session.query(models.UserAnswer)
            .filter_by(user_id=user.id, question_id=question_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La pregunta ya fue respondida",
            )

    reconstructed = _reconstruct_question(question)
    is_correct = reconstructed.evaluate(submission.answer)
    points = 100 if is_correct else 0

    if user:
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


# In-memory dictionary to track daily map guesses: (username, date) -> count
_user_map_guesses: dict[tuple[str, date], int] = {}


@router.get("/leaderboard", response_model=List[schemas.LeaderboardEntry])
def leaderboard(
    username: str = Query(..., description="Nombre de usuario registrado"),
    session: Session = Depends(get_session),
) -> List[schemas.LeaderboardEntry]:
    """Return the global leaderboard ordered by points and accuracy.

    This is only accessible to registered users.

    Parameters
    ----------
    username : str
        The query username making the request.
    session : Session
        The database session.

    Returns
    -------
    List[schemas.LeaderboardEntry]
        Sorted leaderboard entries.
    """
    # Verify user exists in database (registered check)
    requesting_user = session.query(models.User).filter_by(username=username).first()
    if not requesting_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clasificación solo disponible para usuarios con una cuenta registrada.",
        )

    users = session.query(models.User).all()
    leaderboard_entries: List[schemas.LeaderboardEntry] = []

    for u in users:
        # Count total answered daily questions
        answered_count = (
            session.query(models.UserAnswer).filter_by(user_id=u.id).count()
        )

        # Sum points from daily questions (100 points each)
        quiz_points = (
            session.query(func.sum(models.UserAnswer.awarded_points))
            .filter_by(user_id=u.id)
            .scalar()
            or 0
        )

        # Sum points from map guesses (30 points each)
        map_points = (
            session.query(func.sum(models.MapGuess.awarded_points))
            .filter_by(user_id=u.id)
            .scalar()
            or 0
        )

        total_points = int(quiz_points) + int(map_points)

        # Calculate accuracy for daily questions
        correct_count = (
            session.query(models.UserAnswer)
            .filter_by(user_id=u.id, is_correct=True)
            .count()
        )
        accuracy_value = (
            float(correct_count / answered_count) if answered_count > 0 else 0.0
        )

        leaderboard_entries.append(
            schemas.LeaderboardEntry(
                username=u.username,
                answered_questions=answered_count,
                total_points=total_points,
                accuracy=round(accuracy_value, 3),
            )
        )

    # Sort: highest points first, alphabetical username on tie
    leaderboard_entries.sort(key=lambda x: (-x.total_points, x.username))
    return leaderboard_entries


@router.get("/user-stats")
def get_user_stats(
    username: str = Query(..., description="Nombre de usuario"),
    session: Session = Depends(get_session),
) -> dict:
    """Get daily stats and total points for a given user.

    Parameters
    ----------
    username : str
        The username of the user.
    session : Session
        The database session.

    Returns
    -------
    dict
        Dictionary containing daily counts and total points.
    """
    today = date.today()
    user = session.query(models.User).filter_by(username=username).first()

    if user:
        today_start = datetime.combine(today, time.min)
        today_end = datetime.combine(today, time.max)

        # Map guesses count today
        map_guesses_today = (
            session.query(models.MapGuess)
            .filter(
                models.MapGuess.user_id == user.id,
                models.MapGuess.guessed_at >= today_start,
                models.MapGuess.guessed_at <= today_end,
            )
            .count()
        )

        # Quiz questions answered today
        quiz_answered_today = (
            session.query(models.UserAnswer)
            .join(models.DailyQuestion)
            .filter(
                models.UserAnswer.user_id == user.id,
                models.DailyQuestion.question_date == today,
            )
            .count()
        )

        # Total points from DB
        quiz_points = (
            session.query(func.sum(models.UserAnswer.awarded_points))
            .filter_by(user_id=user.id)
            .scalar()
            or 0
        )
        map_points = (
            session.query(func.sum(models.MapGuess.awarded_points))
            .filter_by(user_id=user.id)
            .scalar()
            or 0
        )
        total_points = int(quiz_points) + int(map_points)

        is_registered = True
    else:
        map_guesses_today = _user_map_guesses.get((username, today), 0)
        quiz_answered_today = 0
        total_points = 0
        is_registered = False

    return {
        "username": username,
        "is_registered": is_registered,
        "map_guesses_today": map_guesses_today,
        "map_guesses_limit": 10,
        "quiz_questions_answered_today": quiz_answered_today,
        "quiz_questions_total_today": 3,
        "total_points": total_points,
    }


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


@router.get("/boundary")
def get_boundary() -> dict:
    """Return the municipal boundary polygon of Santander in GeoJSON format.

    Returns
    -------
    dict
        The GeoJSON dictionary containing the boundary geometry.
    """
    boundary_path = Path("data") / "santander_boundary.geojson"
    if not boundary_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Municipal boundary data not found.",
        )
    return json.loads(boundary_path.read_text(encoding="utf-8"))


@router.get("/random-street")
def get_random_street() -> dict:
    """Return a random street name from the municipal street index.

    Returns
    -------
    dict
        A dictionary containing the random street name.
    """
    graph = get_street_graph()
    candidates = graph.candidate_streets()
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No candidate streets loaded.",
        )
    return {"name": random.choice(candidates)}


@router.post("/guess-street")
def guess_street(
    submission: schemas.GuessSubmission, session: Session = Depends(get_session)
) -> dict:
    """Evaluate a user's map click guess against the target street.

    Checks daily guess limits (max 10) and persists results for registered users.

    Parameters
    ----------
    submission : schemas.GuessSubmission
        The guess coordinates and user metadata.
    session : Session
        The database session.

    Returns
    -------
    dict
        Evaluation results, distance, closest point, and remaining guesses.
    """
    graph = get_street_graph()
    today = date.today()
    username = submission.username

    # Check if the user is registered in the database
    user = session.query(models.User).filter_by(username=username).first()

    # Enforce limit of 10 daily guesses per user
    if user:
        today_start = datetime.combine(today, time.min)
        today_end = datetime.combine(today, time.max)
        current_guesses = (
            session.query(models.MapGuess)
            .filter(
                models.MapGuess.user_id == user.id,
                models.MapGuess.guessed_at >= today_start,
                models.MapGuess.guessed_at <= today_end,
            )
            .count()
        )
    else:
        current_guesses = _user_map_guesses.get((username, today), 0)

    if current_guesses >= 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Has superado el límite de 10 calles diarias en el mapa.",
        )

    try:
        result = graph.guess_street(
            submission.street_name, submission.lat, submission.lng
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    new_count = current_guesses + 1

    if not user:
        # Increment in-memory counter for guests
        _user_map_guesses[(username, today)] = new_count
    else:
        # Determine points (30 points if correct, 0 if incorrect)
        is_correct = result["is_correct"]
        points = 30 if is_correct else 0

        # Save to database
        map_guess = models.MapGuess(
            user_id=user.id,
            street_name=result["street_name"],
            lat=submission.lat,
            lng=submission.lng,
            distance_meters=result["distance_meters"],
            is_correct=is_correct,
            awarded_points=points,
        )
        session.add(map_guess)
        session.commit()

    # Append remaining attempts info to result payload
    result["guesses_remaining"] = 10 - new_count
    return result
