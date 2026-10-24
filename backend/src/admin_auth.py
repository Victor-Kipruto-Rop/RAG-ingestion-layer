"""Server-side dashboard authentication.

The browser never receives the service API key. An operator signs in with a dedicated
admin password; the server verifies it against a PBKDF2 hash and issues a signed,
HttpOnly, SameSite=Strict session cookie. State-changing requests that rely on the
cookie must also send the per-session CSRF token in ``X-CSRF-Token``.

Generate a password hash with: ``python -m src.admin_auth hash-password``
"""
import base64
import collections
import getpass
import hashlib
import hmac
import json
import secrets
import sys
import threading
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .config import settings

COOKIE_NAME = 'pg_admin_session'
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}
PBKDF2_ITERATIONS = 600_000
router = APIRouter(prefix='/api/v1/admin', tags=['admin session'])

_attempt_lock = threading.Lock()
_attempts = collections.defaultdict(collections.deque)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations)
    return f'pbkdf2_sha256${iterations}${_b64(salt)}${_b64(digest)}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt, expected = encoded.split('$')
        if scheme != 'pbkdf2_sha256':
            return False
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), _unb64(salt), int(iterations))
        return hmac.compare_digest(digest, _unb64(expected))
    except Exception:
        return False


def _sign(payload: str) -> str:
    return _b64(hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).digest())


def issue_session_token(now: float | None = None) -> tuple[str, dict]:
    issued = int(now if now is not None else time.time())
    claims = {'sub': 'admin', 'iat': issued, 'exp': issued + max(60, settings.session_ttl_seconds), 'csrf': secrets.token_urlsafe(24)}
    payload = _b64(json.dumps(claims, separators=(',', ':')).encode())
    return f'{payload}.{_sign(payload)}', claims


def decode_session_token(token: str | None) -> dict | None:
    if not token or not settings.session_secret or '.' not in token:
        return None
    payload, _, signature = token.partition('.')
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        claims = json.loads(_unb64(payload))
    except Exception:
        return None
    if not isinstance(claims.get('exp'), (int, float)) or claims['exp'] <= time.time():
        return None
    return claims


def session_from_request(request: Request) -> dict | None:
    return decode_session_token(request.cookies.get(COOKIE_NAME))


def enforce_session_csrf(request: Request, claims: dict) -> None:
    """Cookie-authenticated unsafe requests must prove they came from our dashboard."""
    if request.method.upper() in SAFE_METHODS:
        return
    supplied = request.headers.get('X-CSRF-Token', '')
    if not supplied or not hmac.compare_digest(supplied, str(claims.get('csrf', ''))):
        raise HTTPException(403, 'Missing or invalid CSRF token')


def _check_login_rate(client_host: str) -> None:
    limit = max(1, settings.admin_login_max_attempts_per_minute)
    now = time.monotonic()
    with _attempt_lock:
        bucket = _attempts[client_host]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(429, 'Too many sign-in attempts. Try again in a minute.', headers={'Retry-After': '60'})
        bucket.append(now)


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)


@router.post('/login')
def login(payload: LoginRequest, request: Request, response: Response):
    if not settings.admin_password_hash or not settings.session_secret:
        raise HTTPException(503, 'Dashboard sign-in is not configured')
    _check_login_rate(request.client.host if request.client else 'unknown')
    if not verify_password(payload.password, settings.admin_password_hash):
        raise HTTPException(401, 'Invalid credentials')
    token, claims = issue_session_token()
    response.set_cookie(COOKIE_NAME, token, max_age=max(60, settings.session_ttl_seconds), httponly=True,
                        secure=settings.session_cookie_secure, samesite='strict', path='/')
    response.headers['Cache-Control'] = 'no-store'
    return {'authenticated': True, 'csrf_token': claims['csrf'], 'expires_at': claims['exp']}


@router.get('/session')
def session(request: Request, response: Response):
    claims = session_from_request(request)
    response.headers['Cache-Control'] = 'no-store'
    if not claims:
        raise HTTPException(401, 'Not signed in')
    return {'authenticated': True, 'csrf_token': claims['csrf'], 'expires_at': claims['exp']}


@router.post('/logout', status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path='/')
    return None


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'hash-password':
        first = getpass.getpass('Admin password: ')
        if len(first) < 12:
            sys.exit('Use at least 12 characters.')
        if first != getpass.getpass('Repeat password: '):
            sys.exit('Passwords did not match.')
        print(hash_password(first))
    else:
        sys.exit('usage: python -m src.admin_auth hash-password')
