"""Tests for user registration and authentication."""

from __future__ import annotations

from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
import pytest

from app.main import app
from app.database import Base
from app.dependencies import get_session

from sqlalchemy.pool import StaticPool

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="db_session")
def fixture_db_session() -> Generator[Session, None, None]:
    """Provide a clean in-memory database session for each test.

    Yields
    ------
    Session
        The temporary database session.
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(name="client")
def fixture_client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a TestClient with overridden get_session dependency.

    Parameters
    ----------
    db_session : Session
        The active database session fixture.

    Yields
    ------
    TestClient
        FastAPI TestClient.
    """

    def override_get_session() -> Generator[Session, None, None]:
        """Override database dependency to use the test session.

        Yields
        ------
        Session
            The test database session.
        """
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_register_and_login(client: TestClient) -> None:
    """Test successful user registration and subsequent login.

    Parameters
    ----------
    client : TestClient
        The test client instance.
    """
    # 1. Register user
    reg_response = client.post(
        "/users/register",
        json={
            "email": "test@example.com",
            "confirm_email": "test@example.com",
            "password": "securepassword123",
        },
    )
    assert reg_response.status_code == 201
    reg_data = reg_response.json()
    assert reg_data["username"] == "test@example.com"
    assert "id" in reg_data

    # 2. Login user
    login_response = client.post(
        "/users/login",
        json={"email": "test@example.com", "password": "securepassword123"},
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["username"] == "test@example.com"


def test_register_mismatched_emails(client: TestClient) -> None:
    """Test that registration fails when email inputs do not match.

    Parameters
    ----------
    client : TestClient
        The test client instance.
    """
    reg_response = client.post(
        "/users/register",
        json={
            "email": "test@example.com",
            "confirm_email": "different@example.com",
            "password": "securepassword123",
        },
    )
    assert reg_response.status_code == 422
    assert "Los correos electrónicos no coinciden" in reg_response.text


def test_login_invalid_credentials(client: TestClient) -> None:
    """Test login with incorrect password.

    Parameters
    ----------
    client : TestClient
        The test client instance.
    """
    # Register first
    client.post(
        "/users/register",
        json={
            "email": "test@example.com",
            "confirm_email": "test@example.com",
            "password": "securepassword123",
        },
    )

    # Login with wrong password
    login_response = client.post(
        "/users/login", json={"email": "test@example.com", "password": "wrongpassword"}
    )
    assert login_response.status_code == 401
    assert "Credenciales inválidas" in login_response.json()["detail"]


def test_google_login_endpoints_removed(client: TestClient) -> None:
    """Test that the Google login and config endpoints are removed (return 404).

    Parameters
    ----------
    client : TestClient
        The test client instance.
    """
    response_login = client.post("/users/google-login", json={"credential": "token"})
    assert response_login.status_code == 404

    response_config = client.get("/users/config")
    assert response_config.status_code == 404
