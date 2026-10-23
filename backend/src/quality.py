from datetime import datetime, timezone, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from .database import get_db
from .models import Organization, IngestionJob, RegistrySource, AuditLog
from .security import require_api_key

router = APIRouter(prefix='/api/v1', tags=['data quality'], dependencies=[Depends(require_api_key)])


class ReviewDecisionInput(BaseModel):
    organization_id: str = Field(min_length=1, max_length=36)
    candidate_organization_id: str | None = Field(default=None, max_length=36)
    decision: Literal['same_entity', 'different_entities', 'needs_more_evidence']
    rationale: str = Field(min_length=10, max_length=2000)


def _audit_out(row):
    return {
        'id': row.id,
        'action': row.action,
        'actor': row.actor,
        'details': row.details or {},
        'created_at': row.created_at.isoformat() if row.created_at else None,
    }


@router.get('/quality/summary')
def quality_summary(stale_after_days: int = Query(default=180, ge=1, le=3650), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(Organization)) or 0
    missing_registration = db.scalar(select(func.count()).select_from(Organization).where(or_(Organization.normalized_registration_number.is_(None), Organization.normalized_registration_number == ''))) or 0
    missing_tax_pin = db.scalar(select(func.count()).select_from(Organization).where(or_(Organization.normalized_tax_pin.is_(None), Organization.normalized_tax_pin == ''))) or 0
    unreviewed = db.scalar(select(func.count()).select_from(Organization).where(Organization.data_quality_status.in_(['UNREVIEWED', 'UNKNOWN', 'PENDING']))) or 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_after_days)
    stale = db.scalar(select(func.count()).select_from(Organization).where(Organization.last_seen_at < cutoff)) or 0
    failed_jobs = db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status == 'FAILED')) or 0
    return {'total_records': total, 'missing_registration_number': missing_registration, 'missing_tax_pin': missing_tax_pin, 'unreviewed_records': unreviewed, 'stale_records': stale, 'failed_ingestion_jobs': failed_jobs, 'stale_after_days': stale_after_days, 'generated_at': datetime.now(timezone.utc).isoformat(), 'interpretation': 'Quality indicators only. Missing data and imported records are not proof of fraud or legal non-compliance.'}


@router.get('/registry/match-candidates')
def match_candidates(q: str = Query(min_length=2, max_length=200), limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db)):
    from rapidfuzz import fuzz
    from .ingestion.normalizer import normalize_legal_name
    normalized = normalize_legal_name(q) or ''
    rows = db.scalars(select(Organization).where(Organization.normalized_legal_name.ilike(f'%{normalized}%')).limit(250)).all()
    candidates = []
    for row in rows:
        score = float(fuzz.WRatio(normalized, row.normalized_legal_name or ''))
        if score >= 55:
            candidates.append({'organization_id': row.id, 'legal_name': row.legal_name, 'registration_number': row.registration_number, 'tax_pin_present': bool(row.normalized_tax_pin), 'source_name': row.source_name, 'score': round(score, 1), 'review_status': 'candidate_only'})
    candidates.sort(key=lambda item: item['score'], reverse=True)
    return {'query': q, 'items': candidates[:limit], 'count': min(len(candidates), limit), 'warning': 'Similarity is only a review aid. Do not auto-merge or treat a name match as identity verification.'}


@router.post('/quality/review-decisions', status_code=201)
def create_review_decision(payload: ReviewDecisionInput, request: Request, db: Session = Depends(get_db)):
    """Persist a human review decision as an append-only audit event; never merge records."""
    if payload.candidate_organization_id == payload.organization_id:
        raise HTTPException(422, 'The candidate organization must be different from the primary organization.')
    primary = db.get(Organization, payload.organization_id)
    if primary is None:
        raise HTTPException(404, 'Primary organization record not found.')
    candidate = None
    if payload.candidate_organization_id:
        candidate = db.get(Organization, payload.candidate_organization_id)
        if candidate is None:
            raise HTTPException(404, 'Candidate organization record not found.')
    details = {
        'organization_id': primary.id,
        'organization_name': primary.legal_name,
        'candidate_organization_id': candidate.id if candidate else None,
        'candidate_organization_name': candidate.legal_name if candidate else None,
        'decision': payload.decision,
        'rationale': payload.rationale.strip(),
        'review_status': 'recorded_manual_decision',
        'automatic_merge_performed': False,
        'request_id': getattr(request.state, 'request_id', None),
    }
    actor = getattr(request.state, 'api_key_id', None) or 'authenticated-api-client'
    event = AuditLog(action='organization_review_decision', actor=str(actor)[:200], details=details)
    db.add(event)
    db.commit()
    db.refresh(event)
    return {'item': _audit_out(event), 'warning': 'This decision is an auditable reviewer annotation only. It does not verify legal identity, alter canonical records, or merge organizations.'}


@router.get('/quality/review-decisions')
def list_review_decisions(
    organization_id: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(AuditLog).where(AuditLog.action == 'organization_review_decision')
    if organization_id:
        stmt = stmt.where(or_(
            AuditLog.details['organization_id'].as_string() == organization_id,
            AuditLog.details['candidate_organization_id'].as_string() == organization_id,
        ))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit)).all()
    return {'items': [_audit_out(row) for row in rows], 'count': len(rows), 'total': total, 'limit': limit, 'offset': offset, 'next_offset': offset + len(rows) if offset + len(rows) < total else None}


@router.get('/sources/freshness')
def source_freshness(db: Session = Depends(get_db)):
    sources = db.scalars(select(RegistrySource).order_by(RegistrySource.precedence, RegistrySource.display_name)).all()
    now = datetime.now(timezone.utc)
    items = []
    for source in sources:
        job = db.scalar(select(IngestionJob).where(IngestionJob.source_id == source.id, IngestionJob.status.in_(['COMPLETED', 'COMPLETED_WITH_ERRORS'])).order_by(IngestionJob.completed_at.desc()).limit(1))
        last = job.completed_at if job else None
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age_hours = (now - last).total_seconds() / 3600 if last else None
        if last is None:
            state = 'unknown'
        elif source.freshness_sla_hours is not None and age_hours > source.freshness_sla_hours:
            state = 'stale'
        else:
            state = 'fresh'
        items.append({'source_key': source.source_key, 'display_name': source.display_name, 'enabled': source.enabled, 'freshness_sla_hours': source.freshness_sla_hours, 'last_import_at': last.isoformat() if last else None, 'age_hours': round(age_hours, 2) if age_hours is not None else None, 'freshness_status': state})
    return {'items': items, 'generated_at': now.isoformat()}


@router.get('/quality/rules')
def quality_rules():
    return {'items': [
        {'id': 'legal-name-required', 'name': 'Legal name required', 'severity': 'error', 'status': 'active', 'description': 'An organization record must include a non-empty legal name.', 'enforced_at': 'ingestion'},
        {'id': 'registration-identifier-present', 'name': 'Registration identifier present', 'severity': 'warning', 'status': 'active', 'description': 'Records without a normalized registration number are counted for review; not all entity types use the same identifier.', 'enforced_at': 'quality-report'},
        {'id': 'tax-pin-present', 'name': 'Tax PIN present', 'severity': 'warning', 'status': 'active', 'description': 'Records without a normalized tax PIN are counted for review; missing values are not proof of non-compliance.', 'enforced_at': 'quality-report'},
        {'id': 'stale-source-record', 'name': 'Record freshness', 'severity': 'info', 'status': 'active', 'description': 'Records not seen within the configured lookback are flagged as stale candidates.', 'enforced_at': 'quality-report'},
        {'id': 'similar-name-candidate', 'name': 'Potential name match', 'severity': 'review', 'status': 'active', 'description': 'Similarity results are review candidates only; records are never automatically merged.', 'enforced_at': 'manual-review'}
    ], 'note': 'These are the checks currently exposed by this service, not a configurable rules engine.'}


@router.get('/audit/logs')
def audit_logs(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0), action: str | None = None, db: Session = Depends(get_db)):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action[:100])
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit)).all()
    return {'items': [{'id': r.id, 'action': r.action, 'actor': r.actor, 'file_name': r.file_name, 'details': r.details or {}, 'created_at': r.created_at.isoformat() if r.created_at else None} for r in rows], 'count': len(rows), 'total': total, 'limit': limit, 'offset': offset, 'next_offset': offset + len(rows) if offset + len(rows) < total else None}
