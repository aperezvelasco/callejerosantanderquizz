"""Application configuration utilities."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    """Runtime configuration for the API."""

    app_name: str = "Callejero Santander Quizz"
    callejero_dataset_url: str = "https://datos.santander.es/api/rest/datasets/callejero_tramos.json"
    database_url: str = f"sqlite:///{Path('data') / 'callejero.db'}"
    daily_questions: int = 3


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
