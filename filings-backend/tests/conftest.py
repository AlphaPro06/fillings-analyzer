"""
Shared test fixtures.

Design:
  * Use an in-memory SQLite DB so tests need no external Postgres and are fast.
  * Override the get_db dependency so the app talks to the test DB.
  * Provide a ready-to-use authenticated client to keep tests focused.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    # StaticPool + shared in-memory URL so all connections see the same DB.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    """A TestClient with the DB dependency overridden to the test session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_client(client):
    """A client that has registered + logged in; adds the bearer token."""
    email = "mo@example.com"
    password = "supersecret123"
    client.post("/auth/register", json={"email": email, "password": password})
    resp = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
