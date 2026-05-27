"""Application configuration utilities."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseModel):
    """Runtime configuration for the API."""

    app_name: str = "Callejero Santander Quizz"
    callejero_dataset_url: str = (
        "https://datos.santander.es/api/rest/datasets/callejero_tramos.json"
    )
    database_url: str = Field(default="")
    daily_questions: int = 3
    google_client_id: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance.

    Returns
    -------
    Settings
        The cached configuration settings.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        db_url = f"sqlite:///{Path('data') / 'callejero.db'}"

    # Render/Heroku PostgreSQL driver fix
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    google_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    daily_q = int(os.environ.get("DAILY_QUESTIONS", "3"))

    return Settings(
        database_url=db_url, google_client_id=google_id, daily_questions=daily_q
    )
