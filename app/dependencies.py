"""FastAPI dependencies."""
from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from .database import SessionLocal


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
