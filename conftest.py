"""Test bootstrap: isolate settings and the database before any application import."""
import os
import tempfile

_workdir = tempfile.mkdtemp(prefix="registry-tests-")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_workdir}/test.db")
os.environ["LOCAL_STORAGE_PATH"] = os.path.join(_workdir, "uploads")
os.environ["APP_ENV"] = "development"
os.environ["REGISTRY_API_KEYS"] = "test-secret-key"
os.environ["METRICS_TOKEN"] = "test-metrics-token"
os.environ["API_ENVIRONMENT"] = "sandbox"
for name in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME", "REDIS_URL", "HMAC_SHARED_SECRET", "REQUIRE_HMAC"):
    os.environ.pop(name, None)
