from contextlib import nullcontext
from unittest.mock import MagicMock

from src import main


@pytest.fixture
def healthy_database(monkeypatch):
    connection = MagicMock()
    monkeypatch.setattr(main.engine, "connect", lambda: nullcontext(connection))
    return connection


def test_development_readiness_reports_optional_dependencies_without_failing(healthy_database, monkeypatch):
    monkeypatch.setattr(main.settings, "app_env", "development")
    monkeypatch.setattr(main.settings, "require_hmac", False)
    monkeypatch.setattr(main.settings, "redis_url", "")
    monkeypatch.setattr(main.storage_module, "configured", lambda: False)

    ready, dependencies = main._health_snapshot()

    assert ready is True
    assert dependencies == {
        "database": "healthy",
        "object_storage": "not_configured",
        "redis": "not_configured",
    }


def test_production_readiness_fails_when_private_object_storage_is_missing(healthy_database, monkeypatch):
    redis = MagicMock()
    redis.ping.return_value = True
    monkeypatch.setattr(main.settings, "app_env", "production")
    monkeypatch.setattr(main.settings, "require_hmac", False)
    monkeypatch.setattr(main.settings, "redis_url", "redis://configured")
    monkeypatch.setattr(main.storage_module, "configured", lambda: False)
    monkeypatch.setattr(main, "_redis_client", lambda: redis)

    ready, dependencies = main._health_snapshot()

    assert ready is False
    assert dependencies["database"] == "healthy"
    assert dependencies["object_storage"] == "unavailable"
    assert dependencies["redis"] == "healthy"


def test_production_readiness_fails_when_redis_is_unavailable(healthy_database, monkeypatch):
    monkeypatch.setattr(main.settings, "app_env", "production")
    monkeypatch.setattr(main.settings, "require_hmac", False)
    monkeypatch.setattr(main.settings, "redis_url", "redis://configured")
    monkeypatch.setattr(main.storage_module, "configured", lambda: True)
    monkeypatch.setattr(main.storage_module, "health_check", lambda: True)
    monkeypatch.setattr(main, "_redis_client", lambda: (_ for _ in ()).throw(ConnectionError("offline")))

    ready, dependencies = main._health_snapshot()

    assert ready is False
    assert dependencies["object_storage"] == "healthy"
    assert dependencies["redis"] == "unavailable"


def test_readiness_fails_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr(main.settings, "app_env", "development")
    monkeypatch.setattr(main.settings, "require_hmac", False)
    monkeypatch.setattr(main.settings, "redis_url", "")
    monkeypatch.setattr(main.engine, "connect", lambda: (_ for _ in ()).throw(ConnectionError("offline")))
    monkeypatch.setattr(main.storage_module, "configured", lambda: False)

    ready, dependencies = main._health_snapshot()

    assert ready is False
    assert dependencies["database"] == "unavailable"
