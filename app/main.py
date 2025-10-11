"""FastAPI application for Callejero Santander Quizz."""
from __future__ import annotations

from fastapi import FastAPI

from .core.config import get_settings
from .database import init_db
from .routers import quiz, users

settings = get_settings()
app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(users.router)
app.include_router(quiz.router)
