import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import database
import main
from config import settings


@pytest.fixture()
def client(monkeypatch):
    """API client backed by an in-memory SQLite database (no PostgreSQL needed for tests)."""
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", async_sessionmaker(engine, expire_on_commit=False))
    monkeypatch.setattr(settings, "DEV_MODE", True)
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    with TestClient(main.app) as c:  # lifespan creates the tables
        yield c


def register(client, email="alice@example.com", password="supersecret1", name="Alice") -> dict:
    """Sign up, verify the OTP, log in. Returns auth headers."""
    assert client.post("/auth/signup", json={"name": name, "email": email, "password": password}).status_code == 201
    otp = client.post("/auth/send-otp", json={"email": email}).json()["dev_otp"]
    assert client.post("/auth/verify-otp", json={"email": email, "otp": otp}).status_code == 200
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture()
def auth(client):
    return register(client)
