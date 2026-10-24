"""PesaGuard HTTP client starter. Keep credentials in server-side secrets."""
import hashlib
import hmac
import os
import time
from urllib.parse import urljoin, urlparse

import requests

BASE_URLS = {
    "sandbox": "https://sandbox-api.pesaguard.co.ke",
    "production": "https://api.pesaguard.co.ke",
}


class PesaGuardClient:
    def __init__(self, api_key=None, environment=None, timeout=10):
        self.environment = environment or os.getenv("PESAGUARD_ENV", "sandbox")
        if self.environment not in BASE_URLS:
            raise ValueError("environment must be sandbox or production")
        self.api_key = api_key or os.getenv("PESAGUARD_API_KEY", "")
        prefix = "pg_sandbox_" if self.environment == "sandbox" else "pg_live_"
        if not self.api_key.startswith(prefix):
            raise ValueError(f"The selected {self.environment} environment requires a {prefix} API key")
        self.base_url = (os.getenv("PESAGUARD_BASE_URL") or BASE_URLS[self.environment]).rstrip("/") + "/"
        parsed = urlparse(self.base_url)
        if parsed.hostname != urlparse(BASE_URLS[self.environment]).hostname:
            raise ValueError("Base URL does not match selected environment")
        if os.getenv("APP_ENV", "").lower() == "production" and parsed.scheme != "https":
            raise ValueError("Production SDK calls require HTTPS")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": self.api_key, "Accept": "application/json"})

    def request(self, path, *, params=None, method="GET", json=None):
        response = self.session.request(method, urljoin(self.base_url, path.lstrip("/")),
                                        params=params, json=json, timeout=self.timeout,
                                        allow_redirects=False)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f"PesaGuard API returned HTTP {response.status_code}") from exc
        return response.json() if response.content else None

    def search_registry(self, query, **params):
        return self.request("/api/v1/registry/search", params={"q": query, **params})


def verify_webhook_signature(secret, raw_body, signature_header, *, tolerance_seconds=300, now=None):
    """Verify PesaGuard-Signature: t=<unix>,v1=<hex> against the exact raw body bytes."""
    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")
    if not isinstance(raw_body, bytes) or not isinstance(signature_header, str):
        return False
    values = {}
    for part in signature_header.split(","):
        key, separator, value = part.strip().partition("=")
        if separator and key in {"t", "v1"} and key not in values:
            values[key] = value
    try:
        timestamp = int(values["t"])
        supplied = values["v1"]
    except (KeyError, ValueError):
        return False
    current = int(time.time() if now is None else now)
    if abs(current - timestamp) > tolerance_seconds:
        return False
    expected = hmac.new(secret.encode("utf-8"), str(timestamp).encode("ascii") + b"." + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied)
