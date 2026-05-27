"""FastAPI application for Callejero Santander Quizz."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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


@app.get("/")
def read_root() -> FileResponse:
    """Serve the single page web application homepage.

    Returns
    -------
    FileResponse
        The index.html frontend page.
    """
    return FileResponse("static/index.html")


app.include_router(users.router)
app.include_router(quiz.router)

# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")
