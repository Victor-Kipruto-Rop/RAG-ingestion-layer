"""Small production-oriented PesaGuard Registry API client."""
from __future__ import annotations

from typing import Any, Literal
import hashlib
import hmac
import time
from urllib.parse import urlparse

import requests

Environment = Literal["sandbox", "production"]
DEFAULT_BASE_URLS = {
    "sandbox": "https://sandbox-api.pesaguard.co.ke",
    "production": "https://api.pesaguard.co.ke",
}
KEY_PREFIXES = {"sandbox": "pg_sandbox_", "production": "pg_live_"}


class PesaGuardError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, response_body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class PesaGuardClient:
    """Client for the read-only registry lookup/search API.

    Keep API keys on trusted servers. Sandbox and production keys are not interchangeable.
    """

    def __init__(
        self,
        api_key: str,
        *,
        environment: Environment = "sandbox",
        base_url: str | None = None,
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ):
        if environment not in DEFAULT_BASE_URLS:
            raise ValueError("environment must be 'sandbox' or 'production'")
        if not isinstance(api_key, str) or not api_key.startswith(KEY_PREFIXES[environment]):
            raise ValueError(f"{environment} keys must start with {KEY_PREFIXES[environment]!r}")
        if timeout <= 0 or timeout > 120:
            raise ValueError("timeout must be greater than 0 and at most 120 seconds")
        self.environment = environment
        self.api_key = api_key
        self.base_url = (base_url or DEFAULT_BASE_URLS[environment]).rstrip("/")
        parsed = urlparse(self.base_url)
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("base_url must be an origin without credentials, path, query or fragment")
        local_host = parsed.hostname.lower() in {"localhost", "127.0.0.1"}
        if parsed.scheme != "https" and not local_host:
            raise ValueError("base_url must use HTTPS outside local development")
        if local_host and environment != "sandbox":
            raise ValueError("Local/custom API origins are allowed only with sandbox keys")
        expected_host = urlparse(DEFAULT_BASE_URLS[environment]).hostname
        if not local_host and parsed.hostname.lower() != expected_host:
            raise ValueError("API key environment does not match the approved base URL")
        self.timeout = timeout
        self._session = session or requests.Session()

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        try:
            response = self._session.get(
                f"{self.base_url}/api/v1/registry/{path}",
                params=params,
                headers={"X-API-Key": self.api_key, "Accept": "application/json"},
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise PesaGuardError("Could not connect to PesaGuard API") from exc
        try:
            body = response.json()
        except ValueError:
            body = {"message": response.text[:1000]}
        if not response.ok:
            detail = body.get("detail", body.get("message", "PesaGuard API request failed")) if isinstance(body, dict) else "PesaGuard API request failed"
            raise PesaGuardError(str(detail), status_code=response.status_code, response_body=body)
        if not isinstance(body, dict):
            raise PesaGuardError("PesaGuard returned an unexpected response format", status_code=response.status_code)
        return body

    def search(self, query: str, *, limit: int = 20) -> dict[str, Any]:
        if not isinstance(query, str) or len(query.strip()) < 2:
            raise ValueError("query must contain at least two characters")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        return self._get("search", q=query.strip(), limit=limit)

    def lookup(self, *, registration_number: str | None = None, tax_pin: str | None = None) -> dict[str, Any]:
        if bool(registration_number) == bool(tax_pin):
            raise ValueError("Provide exactly one of registration_number or tax_pin")
        params = {"reg_no": registration_number} if registration_number else {"tax_pin": tax_pin}
        return self._get("lookup", **params)

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "PesaGuardClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

def verify_webhook_signature(
    payload: bytes,
    signature_header: str,
    secret: str,
    *,
    tolerance_seconds: int = 300,
    now: int | None = None,
) -> bool:
    """Verify a PesaGuard t=<unix>,v1=<hex> signature using the exact raw body bytes."""
    if not isinstance(payload, bytes) or not isinstance(secret, str) or not secret:
        return False
    fields = {}
    for part in (signature_header or "").split(","):
        key, separator, value = part.strip().partition("=")
        if separator and key not in fields:
            fields[key] = value
    try:
        timestamp = int(fields["t"])
        supplied = fields["v1"]
    except (KeyError, ValueError, TypeError):
        return False
    current = int(time.time()) if now is None else int(now)
    if tolerance_seconds < 0 or abs(current - timestamp) > tolerance_seconds:
        return False
    expected = hmac.new(secret.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)
