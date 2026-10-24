import re
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src import developer_platform
from src.config import settings
from src.database import Base
from src.models import DeveloperSession


@pytest.fixture
def auth_client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    sent_codes = []

    def override_db():
        with factory() as db:
            yield db

    monkeypatch.setattr(developer_platform, "_send_email",
        lambda to_email, subject, body: sent_codes.append(re.search(r"\b([0-9]{6})\b", body).group(1)))
    monkeypatch.setattr(developer_platform, "_check_login_rate", lambda client_host: None)
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "smtp_from_email", "no-reply@example.test")
    monkeypatch.setattr(settings, "smtp_username", "")
    monkeypatch.setattr(settings, "smtp_password", "")
    monkeypatch.setattr(settings, "auth_otp_pepper", "p" * 48)
    monkeypatch.setattr(settings, "auth_otp_ttl_seconds", 600)
    monkeypatch.setattr(settings, "auth_otp_max_attempts", 5)
    monkeypatch.setattr(settings, "developer_access_token_secret", "d" * 48)
    monkeypatch.setattr(settings, "developer_access_token_issuer", "https://identity.test/developer")
    monkeypatch.setattr(settings, "developer_access_token_audience", "pesaguard-datasource-api-keys")
    monkeypatch.setattr(settings, "developer_access_token_ttl_seconds", 900)
    monkeypatch.setattr(settings, "developer_session_ttl_seconds", 86400)
    monkeypatch.setattr(settings, "session_secret", "s" * 48)
    monkeypatch.setattr(settings, "session_cookie_secure", False)

    app = FastAPI()
    app.include_router(developer_platform.router)
    app.dependency_overrides[developer_platform.get_db] = override_db
    with TestClient(app) as client:
        yield client, factory, sent_codes
    engine.dispose()


def _signup(client, sent_codes, email="dev@example.com"):
    response = client.post("/api/v1/developer/auth/signup/request-otp", json={
        "email": email, "display_name": "Test Developer",
        "workspace_name": "Test Workspace", "password": "Strong-password-123",
    })
    assert response.status_code == 200, response.text
    verify = client.post("/api/v1/developer/auth/signup/verify-otp", json={
        "email": email, "code": sent_codes[-1],
    })
    assert verify.status_code == 200, verify.text
    return verify.json()


def test_signup_otp_login_session_and_logout_lifecycle(auth_client):
    client, _, sent_codes = auth_client
    session = _signup(client, sent_codes)
    assert session["authenticated"] is True
    assert session["user"]["email_verified"] is True
    assert session["workspace"]["name"] == "Test Workspace"

    current = client.get("/api/v1/developer/auth/session")
    assert current.status_code == 200
    assert current.json()["authenticated"] is True
    csrf = current.json()["csrf_token"]

    logout = client.post("/api/v1/developer/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout.status_code == 204
    assert client.get("/api/v1/developer/auth/session").status_code == 401


def test_password_reset_consumes_otp_and_revokes_all_sessions(auth_client):
    client, factory, sent_codes = auth_client
    _signup(client, sent_codes)
    reset = client.post("/api/v1/developer/auth/password-reset/request-otp", json={"email": "dev@example.com"})
    assert reset.status_code == 200
    code = sent_codes[-1]
    response = client.post("/api/v1/developer/auth/password-reset/confirm", json={
        "email": "dev@example.com", "code": code, "new_password": "Another-strong-Password-456",
    })
    assert response.status_code == 200, response.text
    assert response.json()["updated"] is True
    with factory() as db:
        rows = db.scalars(select(DeveloperSession)).all()
        assert rows
        assert all(row.revoked_at is not None for row in rows)
    assert client.get("/api/v1/developer/auth/session").status_code == 401
    assert client.post("/api/v1/developer/auth/login", json={
        "email": "dev@example.com", "password": "Strong-password-123",
    }).status_code == 401
    assert client.post("/api/v1/developer/auth/login", json={
        "email": "dev@example.com", "password": "Another-strong-Password-456",
    }).status_code == 200


def test_signup_otp_attempt_limit_blocks_further_guesses(auth_client):
    client, _, sent_codes = auth_client
    response = client.post("/api/v1/developer/auth/signup/request-otp", json={
        "email": "guess@example.com", "display_name": "Test Developer",
        "workspace_name": "Test Workspace", "password": "Strong-password-123",
    })
    assert response.status_code == 200
    for _ in range(settings.auth_otp_max_attempts):
        bad = client.post("/api/v1/developer/auth/signup/verify-otp", json={
            "email": "guess@example.com", "code": "000000" if sent_codes[-1] != "000000" else "999999",
        })
        assert bad.status_code == 400
    locked = client.post("/api/v1/developer/auth/signup/verify-otp", json={
        "email": "guess@example.com", "code": sent_codes[-1],
    })
    assert locked.status_code == 400
