"""User management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_session
from ..services.auth import hash_password, verify_password

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=schemas.UserPublic, status_code=status.HTTP_201_CREATED)
def register_user(payload: schemas.UserCreate, session: Session = Depends(get_session)) -> models.User:
    """Register a new user."""

    existing = session.query(models.User).filter_by(username=payload.username).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El nombre de usuario ya existe")

    user = models.User(username=payload.username, password_hash=hash_password(payload.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/login", response_model=schemas.UserPublic)
def login_user(payload: schemas.UserLogin, session: Session = Depends(get_session)) -> models.User:
    """Validate credentials and return the user profile."""

    user = session.query(models.User).filter_by(username=payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    return user
