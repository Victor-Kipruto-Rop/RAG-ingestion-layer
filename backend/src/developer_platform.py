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
from urllib.parse import urlparse
import ipaddress

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
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
    if not settings.auth_email_delivery_configured:
        raise HTTPException(503, "Email verification and recovery are unavailable until SMTP and AUTH_OTP_PEPPER are configured")


def _email(email: str) -> str:
    value = email.strip().lower()
    if len(value) > 320 or "@" not in value or value.startswith("@") or value.endswith("@"):
        raise HTTPException(422, "Enter a valid email address")
    return value


def _otp_digest(email: str, purpose: str, code: str) -> str:
    return hmac.new(settings.auth_otp_pepper.encode(), f"{purpose}:{email}:{code}".encode(), hashlib.sha256).hexdigest()


def _send_email(to_email: str, subject: str, body: str):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message.set_content(body)
    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10, context=ssl.create_default_context()) as server:
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.ehlo()
            if settings.smtp_use_starttls:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)


def _issue_access_token(account: DeveloperAccount, workspace: DeveloperWorkspace) -> str:
    now = int(time.time())
    claims = {
        "iss": settings.developer_access_token_issuer,
        "aud": settings.developer_access_token_audience,
        "sub": account.id,
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
        "access_token": _issue_access_token(account, workspace),
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
    configured = bool(settings.developer_access_token_secret and settings.session_secret and settings.auth_email_delivery_configured)
    return {"signup_enabled": configured, "password_reset_enabled": configured, "password_min_length": 12,
            "otp_ttl_seconds": settings.auth_otp_ttl_seconds, "social_auth_enabled": False,
            "social_auth_note": "Developer OAuth must be configured separately from internal operator OAuth."}


@router.post("/auth/signup/request-otp")
def signup_request_otp(payload: SignupRequest, request: Request, db: Session = Depends(get_db)):
    _require_platform_config()
    _check_login_rate(request.client.host if request.client else "unknown")
    email = _email(str(payload.email))
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
                    f"Your verification code is {code}. It expires in {max(1, settings.auth_otp_ttl_seconds // 60)} minutes. If you did not request this, ignore this email.")
    except Exception as exc:
        challenge.consumed_at = now_utc()
        db.commit()
        raise HTTPException(503, "Verification email could not be sent. Please retry later.") from exc
    return {"accepted": True, "message": "If this address can register, a verification code will arrive shortly."}


@router.post("/auth/signup/verify-otp")
def signup_verify_otp(payload: VerifyOtpRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    _require_platform_config()
    _check_login_rate(request.client.host if request.client else "unknown")
    email = _email(str(payload.email))
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
    return result


@router.post("/auth/login")
def developer_login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    _require_platform_config()
    _check_login_rate(request.client.host if request.client else "unknown")
    email = _email(str(payload.email))
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
        "access_token": _issue_access_token(account, workspace),
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
                        f"Your password reset code is {code}. It expires in {max(1, settings.auth_otp_ttl_seconds // 60)} minutes. If you did not request this, ignore this email.")
        except Exception as exc:
            raise HTTPException(503, "Recovery email could not be sent. Please retry later.") from exc
    return {"accepted": True, "message": "If an active account exists for this address, a reset code will arrive shortly."}


@router.post("/auth/password-reset/confirm")
def password_reset_confirm(payload: ResetConfirmRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    _require_platform_config()
    _check_login_rate(request.client.host if request.client else "unknown")
    email = _email(str(payload.email))
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
    return {"updated": True, "message": "Password updated. Sign in again."}


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


@router.post("/production-access/request", status_code=201)
def request_production_access(payload: ProductionAccessRequestBody, request: Request, db: Session = Depends(get_db)):
    claims = _session_claims(request, db)
    _csrf(request, claims)
    account = claims["account"]
    workspace = _workspace(db, account.id)
    pending = db.scalar(select(DeveloperProductionAccessRequest).where(
        DeveloperProductionAccessRequest.workspace_id == workspace.id,
        DeveloperProductionAccessRequest.status == "pending"))
    if pending:
        raise HTTPException(409, "A production-access request is already pending")
    row = DeveloperProductionAccessRequest(workspace_id=workspace.id, requested_by_user_id=account.id,
        use_case=payload.use_case.strip(), expected_volume=payload.expected_volume.strip())
    db.add(row)
    db.commit()
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


def _deliver_webhook(webhook_id: str, workspace_id: str, event_type: str, payload: dict):
    started = time.perf_counter()
    status = "failed"
    response_status = None
    excerpt = None
    with SessionLocal() as db:
        row = db.scalar(select(DeveloperWebhook).where(DeveloperWebhook.id == webhook_id, DeveloperWebhook.workspace_id == workspace_id, DeveloperWebhook.enabled.is_(True)))
        if not row or event_type not in (row.events or []):
            return
        delivery_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())
        body = json.dumps({"id": event_id, "type": event_type, "created_at": now_utc().isoformat(), "data": payload}, separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        try:
            secret = _fernet().decrypt(row.secret_ciphertext.encode())
            signature = hmac.new(secret, timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
            with httpx.Client(timeout=8.0, follow_redirects=False) as client:
                response = client.post(row.endpoint_url, content=body, headers={
                    "Content-Type": "application/json", "User-Agent": "PesaGuard-Webhooks/1.0",
                    "PesaGuard-Event": event_type, "PesaGuard-Delivery": delivery_id,
                    "PesaGuard-Signature": f"t={timestamp},v1={signature}",
                })
            response_status = response.status_code
            excerpt = response.text[:500]
            status = "delivered" if 200 <= response.status_code < 300 else "failed"
        except (httpx.HTTPError, InvalidToken, OSError, ValueError) as exc:
            excerpt = type(exc).__name__
        db.add(DeveloperWebhookDelivery(webhook_id=row.id, event_type=event_type, status=status,
            response_status=response_status, response_excerpt=excerpt, duration_ms=int((time.perf_counter()-started)*1000)))
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
