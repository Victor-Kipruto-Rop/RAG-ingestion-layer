import hashlib
from fastapi import HTTPException, Request

from src import security


class Result:
    def __init__(self, row=None):
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row


class FakeSession:
    def __init__(self, row):
        self.row = row
        self.statements = []
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append((sql, params or {}))
        return Result(self.row if sql.startswith("SELECT * FROM api_keys") else None)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


def make_request(path="/api/v1/registry/search", method="GET"):
    return Request({
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(b"x-correlation-id", b"req-test-123")],
        "client": ("127.0.0.1", 4321),
        "server": ("testserver", 80),
        "scheme": "http",
    })


def managed_row(raw_key, environment="sandbox", scopes=None):
    prefix = "pg_sandbox_" + raw_key[len("pg_sandbox_"):len("pg_sandbox_") + 8]
    return {
        "id": "key-test-id",
        "key_prefix": prefix,
        "secret_hash": hashlib.sha256(raw_key.encode()).hexdigest(),
        "environment": environment,
        "status": "active",
        "expires_at": None,
        "scopes": scopes or ["registry:read"],
    }


def test_managed_sandbox_key_is_rejected_in_production_and_audited(monkeypatch):
    raw_key = "pg_sandbox_12345678-secret-test-value"
    row = managed_row(raw_key, environment="sandbox")
    session = FakeSession(row)
    monkeypatch.setattr(security, "SessionLocal", lambda: session)
    monkeypatch.setattr(security.settings, "pesaguard_datasource_environment", "production")

    try:
        security._managed_key(raw_key, make_request())
        assert False, "Expected environment mismatch to be rejected"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
        assert "sandbox only" in exc.detail["message"]

    assert session.committed
    assert any("INSERT INTO api_key_security_events" in sql for sql, _ in session.statements)


def test_managed_key_requires_route_scope(monkeypatch):
    raw_key = "pg_sandbox_12345678-secret-test-value"
    row = managed_row(raw_key, environment="sandbox", scopes=["registry:read"])
    session = FakeSession(row)
    monkeypatch.setattr(security, "SessionLocal", lambda: session)
    monkeypatch.setattr(security.settings, "pesaguard_datasource_environment", "sandbox")

    try:
        security._managed_key(raw_key, make_request("/api/v1/ingestion/uploads", method="POST"))
        assert False, "Expected write-scope denial"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail["code"] == "API_KEY_SCOPE_INSUFFICIENT"


def test_managed_key_updates_last_used_without_returning_secret(monkeypatch):
    raw_key = "pg_sandbox_12345678-secret-test-value"
    row = managed_row(raw_key, environment="sandbox")
    session = FakeSession(row)
    monkeypatch.setattr(security, "SessionLocal", lambda: session)
    monkeypatch.setattr(security.settings, "pesaguard_datasource_environment", "sandbox")

    identity = security._managed_key(raw_key, make_request())
    assert identity == "managed-api-key:key-test-id"
    assert session.committed
    assert any("UPDATE api_keys SET last_used_at" in sql for sql, _ in session.statements)
    assert raw_key not in repr(session.statements)
