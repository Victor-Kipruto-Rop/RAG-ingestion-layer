from datetime import timedelta
import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src import api_keys
from src.config import settings
from src.database import Base
from src.models import DeveloperAccount, DeveloperSession, DeveloperWorkspace, now_utc


@pytest.fixture
def developer_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(api_keys, "SessionLocal", factory)
    monkeypatch.setattr(settings, "developer_access_token_secret", "d" * 48)
    monkeypatch.setattr(settings, "developer_access_token_issuer", "https://identity.test/developer")
    monkeypatch.setattr(settings, "developer_access_token_audience", "pesaguard-datasource-api-keys")
    account_id, workspace_id, session_id = "user-1", "workspace-1", "session-1"
    now = now_utc()
    with factory() as db:
        account = DeveloperAccount(id=account_id, email="developer@example.com", display_name="Developer",
                                   password_hash="unused", email_verified_at=now)
        workspace = DeveloperWorkspace(id=workspace_id, name="Workspace", owner_user_id=account_id,
                                       verified=False, production_access_approved=False)
        session = DeveloperSession(id=session_id, user_id=account_id, created_at=now, last_seen_at=now,
                                   expires_at=now + timedelta(hours=1), user_agent="pytest", ip_digest="a" * 64)
        db.add_all([account, workspace, session])
        db.commit()
    return factory, account_id, workspace_id, session_id


def _developer_token(session_id="session-1"):
    now = int(__import__("time").time())
    return jwt.encode({
        "iss": settings.developer_access_token_issuer,
        "aud": settings.developer_access_token_audience,
        "sub": "user-1",
        "tenant_id": "workspace-1",
        "session_id": session_id,
        "type": "access",
        "auth_version": 1,
        "scope": "registry:read api_keys:manage webhooks:manage",
        "jti": "token-id",
        "iat": now,
        "nbf": now - 1,
        "exp": now + 300,
    }, settings.developer_access_token_secret, algorithm="HS256")


def test_developer_access_token_requires_a_live_server_session(developer_db):
    token = _developer_token()
    claims = api_keys.require_user_claims("Bearer " + token)
    assert claims["org_id"] == "workspace-1"
    assert claims["sub"] == "user-1"


def test_revoking_a_developer_session_invalidates_existing_bearer_token(developer_db):
    factory, _, _, session_id = developer_db
    with factory() as db:
        row = db.get(DeveloperSession, session_id)
        row.revoked_at = now_utc()
        db.commit()

    with pytest.raises(HTTPException) as exc:
        api_keys.require_user_claims("Bearer " + _developer_token())
    assert exc.value.status_code == 401


def test_developer_access_token_cannot_reference_another_users_session(developer_db):
    with pytest.raises(HTTPException) as exc:
        api_keys.require_user_claims("Bearer " + _developer_token("missing-session"))
    assert exc.value.status_code == 401
