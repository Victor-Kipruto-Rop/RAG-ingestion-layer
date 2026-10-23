"""Regression tests for environment-scoped customer API keys.

These tests use an isolated in-memory SQLite database and fictional identities.
They never connect to production PostgreSQL, R2, Redis, or external identity services.
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from src import security
from src.api_keys import CreateApiKey, _create_key
from src.config import settings
from src.database import Base
from src.models import ApiKey, ApiKeyAuditEvent


@pytest.fixture
def key_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(security, "SessionLocal", factory)
    with factory() as db:
        yield db
    Base.metadata.drop_all(engine)
    engine.dispose()


def _request(path="/api/v1/registry/lookup"):
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 54321),
        "server": ("testserver", 443),
        "state": {"request_id": "test-" + uuid.uuid4().hex},
    })


def _claims(**overrides):
    claims = {
        "sub": "test-user",
        "org_id": "fictional-org-1",
        "roles": ["owner"],
        "exp": datetime.now(timezone.utc).timestamp() + 3600,
        "organization_verified": True,
    }
    claims.update(overrides)
    return claims


def _persist_key(db, *, environment="sandbox", scopes=None, status="active", expires_at=None):
    secret = ("pg_sandbox_" if environment == "sandbox" else "pg_live_") + uuid.uuid4().hex
    row = ApiKey(
        id=str(uuid.uuid4()),
        organization_id="fictional-org-1",
        created_by_user_id="test-user",
        name="fictional test key",
        environment=environment,
        key_prefix=secret[:22],
        secret_hash=hashlib.sha256(secret.encode()).hexdigest(),
        scopes=scopes or ["registry:read"],
        status=status,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    return secret, row


def test_created_key_is_environment_scoped_and_only_hash_is_persisted(key_db):
    result = _create_key(
        key_db,
        _claims(),
        CreateApiKey(name="Sandbox integration", environment="sandbox", scopes=["registry:read"]),
    )
    row = key_db.scalar(select(ApiKey).where(ApiKey.id == result["id"]))
    assert result["secret"].startswith("pg_sandbox_")
    assert result["environment"] == "sandbox"
    assert row is not None
    assert row.secret_hash == hashlib.sha256(result["secret"].encode()).hexdigest()
    assert result["secret"] != row.secret_hash
    assert "secret" not in {column.name for column in ApiKey.__table__.columns}


def test_production_key_requires_verified_organization_and_owner_role(key_db):
    with pytest.raises(HTTPException) as unverified:
        _create_key(
            key_db,
            _claims(organization_verified=False),
            CreateApiKey(name="Production integration", environment="production", expires_in_days=90),
        )
    assert unverified.value.status_code == 403

    with pytest.raises(HTTPException) as not_admin:
        _create_key(
            key_db,
            _claims(roles=["member"]),
            CreateApiKey(name="Production integration", environment="production", expires_in_days=90),
        )
    assert not_admin.value.status_code == 403


def test_sandbox_key_used_in_production_is_rejected_and_audited(key_db, monkeypatch):
    secret, row = _persist_key(key_db, environment="sandbox")
    monkeypatch.setattr(settings, "api_environment", "production")

    with pytest.raises(HTTPException) as exc:
        security._validate_customer_api_key(secret, _request())

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
    assert "sandbox" in exc.value.detail["message"].lower()
    event = key_db.scalar(
        select(ApiKeyAuditEvent).where(
            ApiKeyAuditEvent.organization_id == row.organization_id,
            ApiKeyAuditEvent.action == "api_key.environment_mismatch",
        )
    )
    assert event is not None
    assert secret not in str(event.details)


def test_wrong_scope_is_rejected_and_revoked_or_expired_keys_are_invalid(key_db, monkeypatch):
    monkeypatch.setattr(settings, "api_environment", "sandbox")
    scoped_secret, _ = _persist_key(key_db, scopes=["sources:read"])
    with pytest.raises(HTTPException) as scope_error:
        security._validate_customer_api_key(scoped_secret, _request())
    assert scope_error.value.status_code == 403
    assert scope_error.value.detail["code"] == "API_KEY_SCOPE_INSUFFICIENT"

    revoked_secret, _ = _persist_key(key_db, status="revoked")
    with pytest.raises(HTTPException) as revoked_error:
        security._validate_customer_api_key(revoked_secret, _request())
    assert revoked_error.value.status_code == 401

    expired_secret, _ = _persist_key(
        key_db,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    with pytest.raises(HTTPException) as expired_error:
        security._validate_customer_api_key(expired_secret, _request())
    assert expired_error.value.status_code == 401
