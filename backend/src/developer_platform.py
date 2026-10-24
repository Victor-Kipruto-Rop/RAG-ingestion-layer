"""Public developer-platform identity and control-plane APIs.

Developer accounts are intentionally separate from internal operator accounts. Signup
never grants access to /api/v1/admin routes.
"""
import base64
import hashlib
import hmac
import json
import secrets
import smtplib
import socket
import ssl
import time
import uuid
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from urllib.parse import urlparse, urlencode
import ipaddress
import logging

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal, get_db
from .models import (
    DeveloperAccount, DeveloperWorkspace, DeveloperProject, DeveloperAuthChallenge,
    DeveloperSession, DeveloperWebhook, DeveloperWebhookDelivery,
    DeveloperProductionAccessRequest, ApiKey, ApiKeyAuditEvent, now_utc,
)
from .admin_auth import hash_password, verify_password, _check_login_rate
from .email_service import send_transactional_email

router = APIRouter(prefix="/api/v1/developer", tags=["developer platform"])
SESSION_COOKIE = "pg_developer_session"
OTP_DIGITS = 6
OTP_PURPOSE_SIGNUP = "signup"
OTP_PURPOSE_RESET = "password_reset"
EVENT_TYPES = {
    "api_key.created", "api_key.revoked", "api_key.rotated",
    "webhook.test", "registry.lookup.completed", "data.source.updated",
    "production_access.requested", "production_access.reviewed",
}


def _require_platform_config():
    if not settings.developer_access_token_secret or len(settings.developer_access_token_secret.encode()) < 32:
        raise HTTPException(503, "Developer account authentication is not configured")
    if not settings.session_secret or len(settings.session_secret.encode()) < 32:
        raise HTTPException(503, "Developer session signing is not configured")
    if not settings.auth_email_delivery_configured or len(settings.auth_otp_pepper.encode()) < 32:
        raise HTTPException(503, "Email verification and recovery are unavailable until email delivery and a 32-character AUTH_OTP_PEPPER are configured")


def _email(email: str) -> str:
    value = email.strip().lower()
    if len(value) > 320 or "@" not in value or value.startswith("@") or value.endswith("@"):
        raise HTTPException(422, "Enter a valid email address")
    return value


def _check_account_rate(email: str) -> None:
    """Rate-limit a normalized account identifier without exposing it to the rate limiter."""
    digest = hashlib.sha256(_email(email).encode()).hexdigest()
    _check_login_rate("developer-account:" + digest)


def _otp_digest(email: str, purpose: str, code: str) -> str:
    return hmac.new(settings.auth_otp_pepper.encode(), f"{purpose}:{email}:{code}".encode(), hashlib.sha256).hexdigest()


def _send_email(to_email: str, subject: str, body: str, *, template_id: str = "account.transactional", idempotency_key: str | None = None):
    """Shared transport wrapper used by auth flows; never logs message contents."""
    return send_transactional_email(to_email, subject, body, template_id=template_id,
                                    idempotency_key=idempotency_key)


def _send_notice_best_effort(to_email: str, subject: str, body: str, *, template_id: str, idempotency_key: str):
    """Notify after commit without rolling back the completed security/business action."""
    try:
        _send_email(to_email, subject, body, template_id=template_id, idempotency_key=idempotency_key)
    except Exception as exc:
        logging.getLogger(__name__).warning("transactional_notice_failed template=%s error_type=%s",
                                            template_id, type(exc).__name__)


def _issue_access_token(account: DeveloperAccount, workspace: DeveloperWorkspace, session_id: str) -> str:
    now = int(time.time())
    claims = {
        "iss": settings.developer_access_token_issuer,
        "aud": settings.developer_access_token_audience,
        "sub": account.id,
        "session_id": session_id,
        "tenant_id": workspace.id,
        "organization_id": workspace.id,
        "roles": ["owner"],
        "type": "access",
        "auth_version": 1,
        "scope": "registry:read api_keys:manage webhooks:manage",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "nbf": now - 1,
        "exp": now + settings.developer_access_token_ttl_seconds,
        "organization_verified": workspace.verified is True,
        "production_access_approved": workspace.production_access_approved is True,
        "email": account.email,
    }
    return jwt.encode(claims, settings.developer_access_token_secret, algorithm="HS256")


def _sign_session(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(hmac.new(settings.session_secret.encode(), raw.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    return raw + "." + signature


def _decode_session(token: str | None) -> dict | None:
    if not token or "." not in token or not settings.session_secret:
        return None
    raw, supplied = token.rsplit(".", 1)
    expected = base64.urlsafe_b64encode(hmac.new(settings.session_secret.encode(), raw.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    if not hmac.compare_digest(supplied, expected):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if not isinstance(payload, dict) or int(payload.get("exp", 0)) <= int(time.time()):
            return None
        if not all(isinstance(payload.get(key), str) and payload[key] for key in ("sub", "jti", "csrf")):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _session_claims(request: Request, db: Session, *, required: bool = True) -> dict | None:
    claims = _decode_session(request.cookies.get(SESSION_COOKIE))
    if not claims:
        if required:
            raise HTTPException(401, "Developer session is missing or expired")
        return None
    session = db.get(DeveloperSession, claims["jti"])
    account = db.get(DeveloperAccount, claims["sub"])
    if not session or session.revoked_at is not None or session.expires_at <= now_utc() or not account or account.disabled_at:
        if required:
            raise HTTPException(401, "Developer session has been revoked or expired")
        return None
    claims["account"] = account
    return claims


def _csrf(request: Request, claims: dict):
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied or not hmac.compare_digest(supplied, str(claims.get("csrf", ""))):
        raise HTTPException(403, "Missing or invalid CSRF token")


def _workspace(db: Session, user_id: str) -> DeveloperWorkspace:
    workspace = db.scalar(select(DeveloperWorkspace).where(DeveloperWorkspace.owner_user_id == user_id).order_by(DeveloperWorkspace.created_at))
    if not workspace:
        raise HTTPException(403, "Developer workspace has not been provisioned")
    return workspace


def _session_response(request: Request, response: Response, db: Session, account: DeveloperAccount, workspace: DeveloperWorkspace, *, auth_method: str = "password"):
    if not settings.session_secret or len(settings.session_secret.encode()) < 32:
        raise HTTPException(503, "Developer session signing is not configured")
    now = int(time.time())
    session_id = str(uuid.uuid4())
    csrf_token = secrets.token_urlsafe(32)
    expires = now + settings.developer_session_ttl_seconds
    ip = request.client.host if request.client else "unknown"
    row = DeveloperSession(
        id=session_id, user_id=account.id, created_at=now_utc(), last_seen_at=now_utc(),
        expires_at=datetime.fromtimestamp(expires, tz=timezone.utc),
        user_agent=(request.headers.get("user-agent") or "")[:500],
        ip_digest=hashlib.sha256(ip.encode()).hexdigest(),
    )
    db.add(row)
    db.commit()
    cookie = _sign_session({"sub": account.id, "jti": session_id, "csrf": csrf_token, "iat": now, "exp": expires})
    response.set_cookie(SESSION_COOKIE, cookie, max_age=settings.developer_session_ttl_seconds,
                        httponly=True, secure=settings.session_cookie_secure, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return {
        "authenticated": True, "csrf_token": csrf_token, "expires_at": expires,
        "access_token": _issue_access_token(account, workspace, session_id),
        "access_token_expires_in": settings.developer_access_token_ttl_seconds,
        "auth_method": auth_method,
        "user": {"id": account.id, "email": account.email, "display_name": account.display_name, "email_verified": bool(account.email_verified_at)},
        "workspace": {"id": workspace.id, "name": workspace.name, "verified": workspace.verified,
                      "production_access_approved": workspace.production_access_approved},
    }


class SignupRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=120)
    workspace_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=256)

class VerifyOtpRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^[0-9]{6}$")

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)

class ResetRequest(BaseModel):
    email: EmailStr

class ResetConfirmRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^[0-9]{6}$")
    new_password: str = Field(min_length=12, max_length=256)

class ProductionAccessRequestBody(BaseModel):
    use_case: str = Field(min_length=30, max_length=5000)
    expected_volume: str = Field(min_length=2, max_length=100)

class WebhookCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    endpoint_url: str = Field(min_length=10, max_length=2000)
    events: list[str] = Field(min_length=1, max_length=30)
    project_id: str | None = None

    @field_validator("events")
    @classmethod
    def validate_events(cls, value):
        if len(set(value)) != len(value) or any(event not in EVENT_TYPES for event in value):
            raise ValueError("Choose supported, unique event types")
        return value


def _active_challenge(db: Session, email: str, purpose: str):
    return db.scalar(select(DeveloperAuthChallenge).where(
        func.lower(DeveloperAuthChallenge.email) == email,
        DeveloperAuthChallenge.purpose == purpose,
        DeveloperAuthChallenge.consumed_at.is_(None),
    ).order_by(DeveloperAuthChallenge.created_at.desc()).with_for_update())


@router.get("/auth/config")
def auth_config():
    signing_configured = bool(len(settings.developer_access_token_secret.encode()) >= 32 and len(settings.session_secret.encode()) >= 32)
    configured = bool(signing_configured and settings.auth_email_delivery_configured and len(settings.auth_otp_pepper.encode()) >= 32)
    callback_configured = settings.app_env.lower() != "production" or bool(settings.developer_oauth_callback_base_url.strip() and settings.developer_frontend_url.strip())
    google = bool(signing_configured and callback_configured and settings.google_oauth_client_id and settings.google_oauth_client_secret)
    github = bool(signing_configured and callback_configured and settings.github_oauth_client_id and settings.github_oauth_client_secret)
    return {"signup_enabled": configured, "password_reset_enabled": configured, "password_min_length": 12,
            "otp_ttl_seconds": settings.auth_otp_ttl_seconds,
            "social_auth_enabled": bool(google or github),
            "google_enabled": google,
            "github_enabled": github}


@router.get("/platform/config")
def developer_platform_config():
    return {
        "sandbox_base_url": settings.developer_public_base_url.rstrip("/"),
        "production_base_url": settings.developer_production_base_url.rstrip("/"),
        "api_docs": {"openapi": "/openapi.json", "swagger": "/docs", "redoc": "/redoc"},
        "key_prefixes": {"sandbox": "pg_sandbox_", "production": "pg_live_"},
        "environments": {"sandbox": settings.api_environment.lower() == "sandbox", "production": settings.api_environment.lower() == "production"},
        "sdk_languages": ["cURL", "JavaScript", "Python", "PHP", "Go", "Java", "Ruby", "C#"],
    }


def _oauth_provider(provider: str):
    if provider == "google":
        return settings.google_oauth_client_id, settings.google_oauth_client_secret
    if provider == "github":
        return settings.github_oauth_client_id, settings.github_oauth_client_secret
    raise HTTPException(404, "Unsupported OAuth provider")


def _oauth_callback_url(request: Request, provider: str) -> str:
    base = (settings.developer_oauth_callback_base_url or "").strip().rstrip("/")
    if settings.app_env.lower() == "production" and not base:
        raise HTTPException(503, "DEVELOPER_OAUTH_CALLBACK_BASE_URL must be explicitly configured for production OAuth")
    if not base:
        base = str(request.base_url).rstrip("/")
    parsed = urlparse(base)
    allowed_schemes = {"https"} if settings.app_env.lower() == "production" else {"http", "https"}
    if parsed.scheme not in allowed_schemes or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(503, "OAuth callback base URL must be absolute and use HTTPS in production")
    return f"{base}/api/v1/developer/auth/oauth/{provider}/callback"


@router.get("/auth/oauth/providers")
def developer_oauth_providers():
    return {"google": bool(settings.google_oauth_client_id and settings.google_oauth_client_secret),
            "github": bool(settings.github_oauth_client_id and settings.github_oauth_client_secret)}


@router.get("/auth/oauth/{provider}/start")
def developer_oauth_start(provider: str, request: Request):
    if len(settings.developer_access_token_secret.encode()) < 32 or len(settings.session_secret.encode()) < 32:
        raise HTTPException(503, "Developer OAuth signing and session secrets must each contain at least 32 characters")
    if settings.app_env.lower() == "production" and not settings.developer_frontend_url.strip():
        raise HTTPException(503, "DEVELOPER_FRONTEND_URL must be configured for production OAuth")
    client_id, client_secret = _oauth_provider(provider)
    if not client_id or not client_secret:
        raise HTTPException(503, f"{provider.title()} sign-in is not configured")
    state = secrets.token_urlsafe(32)
    callback = _oauth_callback_url(request, provider)
    if provider == "google":
        params = {"client_id": client_id, "redirect_uri": callback, "response_type": "code",
                  "scope": "openid email profile", "state": state, "prompt": "select_account"}
        destination = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    else:
        params = {"client_id": client_id, "redirect_uri": callback, "response_type": "code",
                  "scope": "read:user user:email", "state": state}
        destination = "https://github.com/login/oauth/authorize?" + urlencode(params)
    response = RedirectResponse(destination, status_code=303)
    response.set_cookie(f"pg_developer_oauth_state_{provider}", state, max_age=600, httponly=True,
                        secure=settings.session_cookie_secure, samesite="lax", path="/api/v1/developer/auth/oauth/")
    response.headers["Cache-Control"] = "no-store"
    return response


async def _fetch_oauth_email(provider: str, code: str, callback: str) -> tuple[str, str]:
    client_id, client_secret = _oauth_provider(provider)
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        if provider == "google":
            token_response = await client.post("https://oauth2.googleapis.com/token", data={
                "code": code, "client_id": client_id, "client_secret": client_secret,
                "redirect_uri": callback, "grant_type": "authorization_code"})
            if token_response.status_code != 200:
                raise HTTPException(401, "Google authorization could not be completed")
            token = token_response.json().get("access_token")
            if not token:
                raise HTTPException(401, "Google did not return an access token")
            profile_response = await client.get("https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {token}"})
            if profile_response.status_code != 200:
                raise HTTPException(401, "Google identity could not be verified")
            profile = profile_response.json()
            if profile.get("email_verified") is not True or not isinstance(profile.get("email"), str):
                raise HTTPException(403, "A verified Google email is required")
            return profile["email"].strip().lower(), str(profile.get("name") or profile["email"].split("@")[0])[:120]
        token_response = await client.post("https://github.com/login/oauth/access_token", data={
            "code": code, "client_id": client_id, "client_secret": client_secret,
            "redirect_uri": callback}, headers={"Accept": "application/json"})
        if token_response.status_code != 200:
            raise HTTPException(401, "GitHub authorization could not be completed")
        token = token_response.json().get("access_token")
        if not token:
            raise HTTPException(401, "GitHub did not return an access token")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28"}
        profile_response = await client.get("https://api.github.com/user", headers=headers)
        emails_response = await client.get("https://api.github.com/user/emails", headers=headers)
        if profile_response.status_code != 200 or emails_response.status_code != 200:
            raise HTTPException(401, "GitHub identity could not be verified")
        profile = profile_response.json()
        emails = emails_response.json()
        verified = next((item for item in emails if item.get("primary") and item.get("verified")), None)
        if not verified or not isinstance(verified.get("email"), str):
            raise HTTPException(403, "A primary verified GitHub email is required")
        return verified["email"].strip().lower(), str(profile.get("name") or profile.get("login") or verified["email"].split("@")[0])[:120]


async def _developer_oauth_callback(provider: str, request: Request, db: Session):
    expected = request.cookies.get(f"pg_developer_oauth_state_{provider}", "")
    supplied = request.query_params.get("state", "")
    code = request.query_params.get("code", "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        raise HTTPException(400, "OAuth state validation failed; restart sign-in")
    if not code:
        raise HTTPException(400, "Identity provider did not return an authorization code")
    callback = _oauth_callback_url(request, provider)
    try:
        email, display_name = await _fetch_oauth_email(provider, code, callback)
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Identity provider is temporarily unavailable") from exc
    account = db.scalar(select(DeveloperAccount).where(func.lower(DeveloperAccount.email) == email))
    if account and account.disabled_at is not None:
        raise HTTPException(403, "This developer account is disabled")
    if account is None:
        account = DeveloperAccount(email=email, display_name=display_name,
            password_hash=hash_password(secrets.token_urlsafe(48)), email_verified_at=now_utc())
        db.add(account)
        db.flush()
        workspace = DeveloperWorkspace(name=f"{display_name}'s workspace", owner_user_id=account.id,
            verified=False, production_access_approved=False)
        db.add(workspace)
        db.flush()
        db.add(DeveloperProject(workspace_id=workspace.id, name="Default project", slug="project-" + uuid.uuid4().hex[:10]))
        db.commit()
    else:
        if account.email_verified_at is None:
            account.email_verified_at = now_utc()
            db.commit()
        workspace = _workspace(db, account.id)
    frontend = (settings.developer_frontend_url or settings.public_base_url or "/").rstrip("/")
    result = RedirectResponse(frontend if frontend else "/", status_code=303)
    _session_response(request, result, db, account, workspace, auth_method=provider)
    result.delete_cookie(f"pg_developer_oauth_state_{provider}", path="/api/v1/developer/auth/oauth/",
                         secure=settings.session_cookie_secure, httponly=True, samesite="lax")
    return result


@router.get("/auth/oauth/google/callback")
async def developer_google_oauth_callback(request: Request, db: Session = Depends(get_db)):
    return await _developer_oauth_callback("google", request, db)


@router.get("/auth/oauth/github/callback")
async def developer_github_oauth_callback(request: Request, db: Session = Depends(get_db)):
    return await _developer_oauth_callback("github", request, db)


@router.post("/auth/signup/request-otp")
def signup_request_otp(payload: SignupRequest, request: Request, db: Session = Depends(get_db)):
    _require_platform_config()
    _check_login_rate(request.client.host if request.client else "unknown")
    email = _email(str(payload.email))
    _check_account_rate(email)
    existing = db.scalar(select(DeveloperAccount).where(func.lower(DeveloperAccount.email) == email))
    if existing:
        return {"accepted": True, "message": "If this address can register, a verification code will arrive shortly."}
    code = f"{secrets.randbelow(10 ** OTP_DIGITS):0{OTP_DIGITS}d}"
    now = now_utc()
    for old in db.scalars(select(DeveloperAuthChallenge).where(
        func.lower(DeveloperAuthChallenge.email) == email,
        DeveloperAuthChallenge.purpose == OTP_PURPOSE_SIGNUP,
        DeveloperAuthChallenge.consumed_at.is_(None),
    )):
        old.consumed_at = now
    challenge = DeveloperAuthChallenge(
        email=email, purpose=OTP_PURPOSE_SIGNUP, otp_hash=_otp_digest(email, OTP_PURPOSE_SIGNUP, code),
        password_hash=hash_password(payload.password), display_name=payload.display_name.strip(), workspace_name=payload.workspace_name.strip(),
        expires_at=now + timedelta(seconds=settings.auth_otp_ttl_seconds), created_at=now,
    )
    db.add(challenge)
    db.commit()
    try:
        _send_email(email, "Verify your PesaGuard Developer Platform account",
                    f"Your verification code is {code}. It expires in {max(1, settings.auth_otp_ttl_seconds // 60)} minutes. If you did not request this, ignore this email.", template_id="account.verify_otp", idempotency_key=f"signup-otp:{challenge.id}")
    except Exception:
        challenge.consumed_at = now_utc()
        db.commit()
        logging.getLogger(__name__).warning("developer_signup_otp_delivery_failed")
    return {"accepted": True, "message": "If this address can register, a verification code will arrive shortly."}


@router.post("/auth/signup/verify-otp")
def signup_verify_otp(payload: VerifyOtpRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    _require_platform_config()
    _check_login_rate(request.client.host if request.client else "unknown")
    email = _email(str(payload.email))
    _check_account_rate(email)
    challenge = _active_challenge(db, email, OTP_PURPOSE_SIGNUP)
    if not challenge or challenge.expires_at <= now_utc() or challenge.attempts >= settings.auth_otp_max_attempts:
        raise HTTPException(400, "Verification code is invalid or expired. Request a new code.")
    challenge.attempts += 1
    if not hmac.compare_digest(challenge.otp_hash, _otp_digest(email, OTP_PURPOSE_SIGNUP, payload.code)):
        db.commit()
        raise HTTPException(400, "Verification code is invalid or expired. Request a new code.")
    if db.scalar(select(DeveloperAccount.id).where(func.lower(DeveloperAccount.email) == email)):
        challenge.consumed_at = now_utc()
        db.commit()
        raise HTTPException(409, "This email is already registered. Sign in instead.")
    account = DeveloperAccount(email=email, display_name=(challenge.display_name or "Developer").strip(),
                               password_hash=challenge.password_hash or "", email_verified_at=now_utc())
    db.add(account)
    db.flush()
    workspace_name = (challenge.workspace_name or "Developer workspace").strip()
    workspace = DeveloperWorkspace(name=workspace_name, owner_user_id=account.id, verified=False, production_access_approved=False)
    db.add(workspace)
    db.flush()
    slug = "project-" + uuid.uuid4().hex[:10]
    db.add(DeveloperProject(workspace_id=workspace.id, name="Default project", slug=slug))
    challenge.consumed_at = now_utc()
    db.commit()
    result = _session_response(request, response, db, account, workspace, auth_method="password")
    _send_notice_best_effort(email, "Welcome to PesaGuard Developer Platform",
        f"Welcome, {account.display_name}. Your developer account and workspace are ready.\n\nStart with the API documentation, create a sandbox key, and test requests against the sandbox base URL. Production access remains separate and requires approval.\n\nIf you did not create this account, contact PesaGuard support.",
        template_id="account.welcome", idempotency_key=f"welcome:{account.id}")
    return result


@router.post("/auth/login")
def developer_login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    _require_platform_config()
    _check_login_rate(request.client.host if request.client else "unknown")
    email = _email(str(payload.email))
    _check_account_rate(email)
    account = db.scalar(select(DeveloperAccount).where(func.lower(DeveloperAccount.email) == email))
    if not account or account.disabled_at is not None or not account.email_verified_at or not verify_password(payload.password, account.password_hash):
        raise HTTPException(401, "Invalid email or password")
    workspace = _workspace(db, account.id)
    return _session_response(request, response, db, account, workspace, auth_method="password")


@router.get("/auth/session")
def developer_session(request: Request, response: Response, db: Session = Depends(get_db)):
    claims = _session_claims(request, db)
    account = claims["account"]
    workspace = _workspace(db, account.id)
    session = db.get(DeveloperSession, claims["jti"])
    session.last_seen_at = now_utc()
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {
        "authenticated": True, "csrf_token": claims["csrf"], "expires_at": int(session.expires_at.timestamp()),
        "access_token": _issue_access_token(account, workspace, claims["jti"]),
        "access_token_expires_in": settings.developer_access_token_ttl_seconds,
        "user": {"id": account.id, "email": account.email, "display_name": account.display_name, "email_verified": bool(account.email_verified_at)},
        "workspace": {"id": workspace.id, "name": workspace.name, "verified": workspace.verified,
                      "production_access_approved": workspace.production_access_approved},
    }


@router.post("/auth/logout", status_code=204)
def developer_logout(request: Request, response: Response, db: Session = Depends(get_db)):
    claims = _session_claims(request, db, required=False)
    if claims:
        _csrf(request, claims)
        session = db.get(DeveloperSession, claims["jti"])
        if session and session.revoked_at is None:
            session.revoked_at = now_utc()
            db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", secure=settings.session_cookie_secure, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return None


@router.post("/auth/password-reset/request-otp")
def password_reset_request(payload: ResetRequest, request: Request, db: Session = Depends(get_db)):
    _require_platform_config()
    _check_login_rate(request.client.host if request.client else "unknown")
    email = _email(str(payload.email))
    _check_account_rate(email)
    account = db.scalar(select(DeveloperAccount).where(func.lower(DeveloperAccount.email) == email, DeveloperAccount.disabled_at.is_(None)))
    if account:
        code = f"{secrets.randbelow(10 ** OTP_DIGITS):0{OTP_DIGITS}d}"
        now = now_utc()
        for old in db.scalars(select(DeveloperAuthChallenge).where(
            func.lower(DeveloperAuthChallenge.email) == email,
            DeveloperAuthChallenge.purpose == OTP_PURPOSE_RESET,
            DeveloperAuthChallenge.consumed_at.is_(None),
        )):
            old.consumed_at = now
        db.add(DeveloperAuthChallenge(email=email, purpose=OTP_PURPOSE_RESET,
            otp_hash=_otp_digest(email, OTP_PURPOSE_RESET, code),
            expires_at=now + timedelta(seconds=settings.auth_otp_ttl_seconds), created_at=now))
        db.commit()
        try:
            _send_email(email, "Reset your PesaGuard Developer Platform password",
                        f"Your password reset code is {code}. It expires in {max(1, settings.auth_otp_ttl_seconds // 60)} minutes. If you did not request this, ignore this email.", template_id="account.password_reset_otp", idempotency_key=f"password-reset-otp:{email}:{now.isoformat()}")
        except Exception:
            challenge = _active_challenge(db, email, OTP_PURPOSE_RESET)
            if challenge:
                challenge.consumed_at = now_utc()
                db.commit()
            logging.getLogger(__name__).warning("developer_password_reset_otp_delivery_failed")
    return {"accepted": True, "message": "If an active account exists for this address, a reset code will arrive shortly."}


@router.post("/auth/password-reset/confirm")
def password_reset_confirm(payload: ResetConfirmRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    _require_platform_config()
    _check_login_rate(request.client.host if request.client else "unknown")
    email = _email(str(payload.email))
    _check_account_rate(email)
    challenge = _active_challenge(db, email, OTP_PURPOSE_RESET)
    if not challenge or challenge.expires_at <= now_utc() or challenge.attempts >= settings.auth_otp_max_attempts:
        raise HTTPException(400, "Reset code is invalid or expired. Request a new code.")
    challenge.attempts += 1
    if not hmac.compare_digest(challenge.otp_hash, _otp_digest(email, OTP_PURPOSE_RESET, payload.code)):
        db.commit()
        raise HTTPException(400, "Reset code is invalid or expired. Request a new code.")
    account = db.scalar(select(DeveloperAccount).where(func.lower(DeveloperAccount.email) == email, DeveloperAccount.disabled_at.is_(None)))
    if not account:
        challenge.consumed_at = now_utc()
        db.commit()
        raise HTTPException(400, "Reset code is invalid or expired. Request a new code.")
    account.password_hash = hash_password(payload.new_password)
    account.updated_at = now_utc()
    challenge.consumed_at = now_utc()
    db.execute(update(DeveloperSession).where(DeveloperSession.user_id == account.id, DeveloperSession.revoked_at.is_(None)).values(revoked_at=now_utc()))
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", secure=settings.session_cookie_secure, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    _send_notice_best_effort(email, "Your PesaGuard password was changed",
        "Your PesaGuard Developer Platform password was changed and all active sessions were revoked. Sign in again on your trusted devices. If you did not make this change, contact support immediately.",
        template_id="account.password_changed", idempotency_key=f"password-changed:{account.id}:{challenge.id}")
    return {"updated": True, "message": "Password updated. Sign in again."}


@router.get("/notifications")
def developer_notifications(request: Request, db: Session = Depends(get_db), limit: int = 50):
    claims = _session_claims(request, db)
    workspace = _workspace(db, claims["sub"])
    limit = max(1, min(limit, 100))
    items = []
    key_events = db.scalars(select(ApiKeyAuditEvent).where(
        ApiKeyAuditEvent.organization_id == workspace.id
    ).order_by(ApiKeyAuditEvent.created_at.desc()).limit(limit)).all()
    for row in key_events:
        action = row.action.replace(".", " ").replace("_", " ").strip().capitalize()
        items.append({"id": "key:" + row.id, "type": row.action, "title": action,
            "message": (row.details or {}).get("reason") or (row.details or {}).get("environment") or "API credential activity recorded.",
            "created_at": row.created_at.isoformat(), "source": "api_keys"})
    requests = db.scalars(select(DeveloperProductionAccessRequest).where(
        DeveloperProductionAccessRequest.workspace_id == workspace.id
    ).order_by(DeveloperProductionAccessRequest.created_at.desc()).limit(limit)).all()
    for row in requests:
        items.append({"id": "production:" + row.id, "type": "production_access." + row.status,
            "title": "Production access " + row.status,
            "message": row.reviewer_note or "Production access request status: " + row.status + ".",
            "created_at": (row.reviewed_at or row.created_at).isoformat(), "source": "production_access"})
    deliveries = db.scalars(select(DeveloperWebhookDelivery).join(
        DeveloperWebhook, DeveloperWebhookDelivery.webhook_id == DeveloperWebhook.id
    ).where(DeveloperWebhook.workspace_id == workspace.id
    ).order_by(DeveloperWebhookDelivery.created_at.desc()).limit(limit)).all()
    for row in deliveries:
        items.append({"id": "webhook:" + row.id, "type": "webhook." + row.status,
            "title": "Webhook delivery " + row.status,
            "message": f"{row.event_type} · HTTP {row.response_status if row.response_status is not None else 'no response'}",
            "created_at": row.created_at.isoformat(), "source": "webhooks"})
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return {"items": items[:limit], "count": min(len(items), limit)}


@router.get("/profile")
def developer_profile(request: Request, db: Session = Depends(get_db)):
    claims = _session_claims(request, db)
    account = claims["account"]
    workspace = _workspace(db, account.id)
    return {"id": account.id, "email": account.email, "display_name": account.display_name,
            "email_verified": bool(account.email_verified_at), "workspace": {"id": workspace.id, "name": workspace.name},
            "created_at": account.created_at.isoformat()}


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    workspace_name: str = Field(min_length=2, max_length=160)


@router.put("/profile")
def update_developer_profile(payload: ProfileUpdate, request: Request, db: Session = Depends(get_db)):
    claims = _session_claims(request, db)
    _csrf(request, claims)
    account = claims["account"]
    account.display_name = payload.display_name.strip()
    workspace = _workspace(db, account.id)
    workspace.name = payload.workspace_name.strip()
    db.commit()
    return {"updated": True, "display_name": account.display_name, "workspace_name": workspace.name}


@router.get("/sessions")
def list_developer_sessions(request: Request, db: Session = Depends(get_db)):
    claims = _session_claims(request, db)
    rows = db.scalars(select(DeveloperSession).where(DeveloperSession.user_id == claims["sub"]).order_by(DeveloperSession.created_at.desc()).limit(50)).all()
    return {"items": [{"id": row.id, "current": row.id == claims["jti"], "created_at": row.created_at.isoformat(),
                       "last_seen_at": row.last_seen_at.isoformat(), "expires_at": row.expires_at.isoformat(),
                       "revoked": row.revoked_at is not None, "user_agent": row.user_agent} for row in rows]}


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_developer_session(session_id: str, request: Request, db: Session = Depends(get_db)):
    claims = _session_claims(request, db)
    _csrf(request, claims)
    row = db.scalar(select(DeveloperSession).where(DeveloperSession.id == session_id, DeveloperSession.user_id == claims["sub"]))
    if not row:
        raise HTTPException(404, "Session not found")
    row.revoked_at = now_utc()
    db.commit()
    if session_id == claims["jti"]:
        raise HTTPException(401, "Current session revoked; sign in again")
    return None


def _queue_workspace_event(background_tasks: BackgroundTasks, workspace_id: str, event_type: str, payload: dict):
    hooks = []
    with SessionLocal() as db:
        rows = db.scalars(select(DeveloperWebhook).where(
            DeveloperWebhook.workspace_id == workspace_id,
            DeveloperWebhook.enabled.is_(True),
        )).all()
        hooks = [row.id for row in rows if event_type in (row.events or [])]
    for hook_id in hooks:
        background_tasks.add_task(_deliver_webhook, hook_id, workspace_id, event_type, payload)


@router.post("/production-access/request", status_code=201)
def request_production_access(payload: ProductionAccessRequestBody, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    claims = _session_claims(request, db)
    _csrf(request, claims)
    account = claims["account"]
    workspace = _workspace(db, account.id)
    if workspace.production_access_approved is True:
        raise HTTPException(409, "Production access is already approved for this workspace")
    pending = db.scalar(select(DeveloperProductionAccessRequest).where(
        DeveloperProductionAccessRequest.workspace_id == workspace.id,
        DeveloperProductionAccessRequest.status == "pending"))
    if pending:
        raise HTTPException(409, "A production-access request is already pending")
    row = DeveloperProductionAccessRequest(workspace_id=workspace.id, requested_by_user_id=account.id,
        use_case=payload.use_case.strip(), expected_volume=payload.expected_volume.strip())
    db.add(row)
    db.commit()
    _queue_workspace_event(background_tasks, workspace.id, "production_access.requested",
        {"request_id": row.id, "status": row.status, "expected_volume": row.expected_volume})
    background_tasks.add_task(_send_notice_best_effort, account.email,
        "PesaGuard production access request received",
        f"We received your production access request for workspace {workspace.name}.\n\nStatus: pending review. Production credentials remain unavailable until the request is approved and the workspace meets verification requirements. Request reference: {row.id}.",
        template_id="production_access.request_received", idempotency_key=f"production-access-request:{row.id}")
    return {"id": row.id, "status": row.status, "message": "Request submitted for review. Production key issuance remains disabled until the workspace is verified and approved."}


def _fernet() -> Fernet:
    key = settings.developer_webhook_encryption_key
    if not key or len(key.encode()) < 32:
        raise HTTPException(503, "Webhook secret encryption is not configured")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))


def _validate_webhook_url(value: str):
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(422, "Webhook URL must be an HTTPS URL without embedded credentials")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".localhost")):
        raise HTTPException(422, "Webhook URL must resolve to a public host")
    try:
        literal = ipaddress.ip_address(host)
        if not literal.is_global:
            raise HTTPException(422, "Webhook URL must use a public IP address")
    except ValueError:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise HTTPException(422, "Webhook host could not be resolved") from exc
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise HTTPException(422, "Webhook host must resolve only to public IP addresses")
    return value


def _webhook_dict(row: DeveloperWebhook):
    return {"id": row.id, "name": row.name, "endpoint_url": row.endpoint_url, "events": row.events,
            "secret_prefix": row.secret_prefix, "enabled": row.enabled, "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat()}


@router.get("/webhooks")
def list_webhooks(request: Request, db: Session = Depends(get_db)):
    claims = _session_claims(request, db)
    workspace = _workspace(db, claims["sub"])
    rows = db.scalars(select(DeveloperWebhook).where(DeveloperWebhook.workspace_id == workspace.id).order_by(DeveloperWebhook.created_at.desc())).all()
    return {"items": [_webhook_dict(row) for row in rows]}


@router.post("/webhooks", status_code=201)
def create_webhook(payload: WebhookCreate, request: Request, db: Session = Depends(get_db)):
    claims = _session_claims(request, db)
    _csrf(request, claims)
    workspace = _workspace(db, claims["sub"])
    _validate_webhook_url(payload.endpoint_url)
    if payload.project_id and not db.scalar(select(DeveloperProject.id).where(DeveloperProject.id == payload.project_id, DeveloperProject.workspace_id == workspace.id)):
        raise HTTPException(404, "Project not found in this workspace")
    secret = "whsec_" + secrets.token_urlsafe(32)
    row = DeveloperWebhook(workspace_id=workspace.id, project_id=payload.project_id, name=payload.name.strip(),
        endpoint_url=payload.endpoint_url, events=payload.events,
        secret_ciphertext=_fernet().encrypt(secret.encode()).decode(), secret_prefix=secret[:14], enabled=True)
    db.add(row)
    db.commit()
    return {"item": _webhook_dict(row), "signing_secret": secret, "warning": "Copy the signing secret now; it is not shown again."}


@router.delete("/webhooks/{webhook_id}", status_code=204)
def delete_webhook(webhook_id: str, request: Request, db: Session = Depends(get_db)):
    claims = _session_claims(request, db)
    _csrf(request, claims)
    workspace = _workspace(db, claims["sub"])
    row = db.scalar(select(DeveloperWebhook).where(DeveloperWebhook.id == webhook_id, DeveloperWebhook.workspace_id == workspace.id))
    if not row:
        raise HTTPException(404, "Webhook not found")
    db.delete(row)
    db.commit()
    return None


def _webhook_response_excerpt(status_code: int) -> str:
    """Return safe, non-sensitive metadata for webhook delivery history."""
    return f"HTTP {int(status_code)}; response body omitted"


def _deliver_webhook(webhook_id: str, workspace_id: str, event_type: str, payload: dict):
    started = time.perf_counter()
    status = "failed"
    response_status = None
    excerpt = None
    with SessionLocal() as db:
        row = db.scalar(select(DeveloperWebhook).where(
            DeveloperWebhook.id == webhook_id,
            DeveloperWebhook.workspace_id == workspace_id,
            DeveloperWebhook.enabled.is_(True),
        ))
        if not row or event_type not in (row.events or []):
            return
        delivery_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())
        body = json.dumps(
            {"id": event_id, "type": event_type, "created_at": now_utc().isoformat(), "data": payload},
            separators=(",", ":"),
        ).encode()
        for attempt in range(3):
            timestamp = str(int(time.time()))
            try:
                # Re-resolve on every attempt and reject private IPs; redirects are disabled to
                # prevent a public endpoint from redirecting delivery into an internal service.
                _validate_webhook_url(row.endpoint_url)
                secret = _fernet().decrypt(row.secret_ciphertext.encode())
                signature = hmac.new(secret, timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
                with httpx.Client(timeout=8.0, follow_redirects=False) as client:
                    response = client.post(row.endpoint_url, content=body, headers={
                        "Content-Type": "application/json",
                        "User-Agent": "PesaGuard-Webhooks/1.0",
                        "PesaGuard-Event": event_type,
                        "PesaGuard-Delivery": delivery_id,
                        "PesaGuard-Signature": f"t={timestamp},v1={signature}",
                    })
                response_status = response.status_code
                # Receiver-controlled response bodies may contain PII, credentials, or
                # internal diagnostics. Persist status metadata only; never store body text.
                excerpt = _webhook_response_excerpt(response.status_code)
                if 200 <= response.status_code < 300:
                    status = "delivered"
                    break
                status = "failed"
                # Retry only transient receiver/gateway responses; most 4xx errors require
                # customer action and should not be repeatedly sent.
                if response.status_code not in {408, 425, 429} and response.status_code < 500:
                    break
            except (httpx.HTTPError, InvalidToken, OSError, ValueError, HTTPException) as exc:
                status = "failed"
                response_status = None
                excerpt = type(exc).__name__
            if attempt < 2:
                time.sleep(0.25 * (2 ** attempt))
        db.add(DeveloperWebhookDelivery(
            webhook_id=row.id,
            event_type=event_type,
            status=status,
            response_status=response_status,
            response_excerpt=excerpt,
            duration_ms=round((time.perf_counter() - started) * 1000),
        ))
        db.commit()


@router.post("/webhooks/{webhook_id}/test", status_code=202)
def test_webhook(webhook_id: str, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    claims = _session_claims(request, db)
    _csrf(request, claims)
    workspace = _workspace(db, claims["sub"])
    row = db.scalar(select(DeveloperWebhook).where(DeveloperWebhook.id == webhook_id, DeveloperWebhook.workspace_id == workspace.id))
    if not row:
        raise HTTPException(404, "Webhook not found")
    if "webhook.test" not in row.events:
        raise HTTPException(422, "Subscribe this endpoint to webhook.test before sending a test")
    background_tasks.add_task(_deliver_webhook, row.id, workspace.id, "webhook.test", {"test": True, "message": "PesaGuard test event"})
    return {"accepted": True, "message": "Test delivery queued. Refresh delivery history for the outcome."}


@router.get("/webhooks/{webhook_id}/deliveries")
def webhook_deliveries(webhook_id: str, request: Request, db: Session = Depends(get_db), limit: int = 50):
    claims = _session_claims(request, db)
    workspace = _workspace(db, claims["sub"])
    row = db.scalar(select(DeveloperWebhook.id).where(DeveloperWebhook.id == webhook_id, DeveloperWebhook.workspace_id == workspace.id))
    if not row:
        raise HTTPException(404, "Webhook not found")
    deliveries = db.scalars(select(DeveloperWebhookDelivery).where(DeveloperWebhookDelivery.webhook_id == webhook_id).order_by(DeveloperWebhookDelivery.created_at.desc()).limit(max(1, min(limit, 100)))).all()
    return {"items": [{"id": d.id, "event_type": d.event_type, "status": d.status, "response_status": d.response_status,
                       "response_excerpt": d.response_excerpt, "duration_ms": d.duration_ms, "created_at": d.created_at.isoformat()} for d in deliveries]}


@router.get("/projects")
def list_projects(request: Request, db: Session = Depends(get_db)):
    claims = _session_claims(request, db)
    workspace = _workspace(db, claims["sub"])
    rows = db.scalars(select(DeveloperProject).where(DeveloperProject.workspace_id == workspace.id).order_by(DeveloperProject.created_at)).all()
    return {"items": [{"id": p.id, "name": p.name, "slug": p.slug, "created_at": p.created_at.isoformat()} for p in rows]}


@router.get("/production-access/requests")
def list_production_requests(request: Request, db: Session = Depends(get_db)):
    claims = _session_claims(request, db)
    workspace = _workspace(db, claims["sub"])
    rows = db.scalars(select(DeveloperProductionAccessRequest).where(DeveloperProductionAccessRequest.workspace_id == workspace.id).order_by(DeveloperProductionAccessRequest.created_at.desc()).limit(100)).all()
    return {"items": [{"id": row.id, "use_case": row.use_case, "expected_volume": row.expected_volume, "status": row.status,
                       "reviewer_note": row.reviewer_note, "created_at": row.created_at.isoformat()} for row in rows]}
