import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session

from .database import get_db
from .models import Organization, OrganizationReviewDecision, AuditLog
from .security import require_api_key

router = APIRouter(prefix="/api/v1/reviews", tags=["manual review"], dependencies=[Depends(require_api_key)])

DECISIONS = {"possible_duplicate", "not_duplicate", "needs_more_evidence", "record_incorrect", "reopened"}


class ReviewDecisionInput(BaseModel):
    decision: Literal["possible_duplicate", "not_duplicate", "needs_more_evidence", "record_incorrect", "reopened"]
    reason: str = Field(min_length=5, max_length=2000)
    evidence: dict = Field(default_factory=dict)


def decision_out(row):
    return {
        "id": row.id,
        "organization_id": row.organization_id,
        "decision": row.decision,
        "reason": row.reason,
        "evidence": row.evidence or {},
        "reviewer": row.reviewer,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "warning": "A manual review decision is an internal assessment, not authoritative legal or government verification.",
    }


@router.get("/queue")
def review_queue(limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    latest_decision = (
        select(OrganizationReviewDecision.decision)
        .where(OrganizationReviewDecision.organization_id == Organization.id)
        .order_by(OrganizationReviewDecision.created_at.desc(), OrganizationReviewDecision.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    base = select(Organization).where(
        or_(
            latest_decision.is_(None),
            latest_decision.in_(["needs_more_evidence", "reopened"]),
        )
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(Organization.created_at.asc(), Organization.id.asc()).offset(offset).limit(limit)).all()
    return {
        "items": [
            {
                "organization_id": row.id,
                "legal_name": row.legal_name,
                "registration_number": row.registration_number,
                "tax_pin_present": bool(row.normalized_tax_pin),
                "source_name": row.source_name,
                "data_quality_status": row.data_quality_status,
                "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
                "latest_decision": None,
                "warning": "Queue membership is not evidence of fraud or non-compliance.",
            }
            for row in rows
        ],
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": offset + len(rows) if offset + len(rows) < total else None,
    }


@router.get("/{organization_id}/decisions")
def list_decisions(organization_id: str, limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    if not db.get(Organization, organization_id):
        raise HTTPException(404, "Organization record not found")
    rows = db.scalars(
        select(OrganizationReviewDecision)
        .where(OrganizationReviewDecision.organization_id == organization_id)
        .order_by(OrganizationReviewDecision.created_at.desc(), OrganizationReviewDecision.id.desc())
        .limit(limit)
    ).all()
    return {"items": [decision_out(row) for row in rows], "count": len(rows)}


@router.post("/{organization_id}/decisions", status_code=201)
def create_decision(organization_id: str, payload: ReviewDecisionInput, request, reviewer: str = Depends(require_api_key), db: Session = Depends(get_db)):
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(404, "Organization record not found")
    if payload.decision == "reopened":
        # Reopening is explicit and audited; it does not alter the underlying registry record.
        pass
    row = OrganizationReviewDecision(
        id=str(uuid.uuid4()),
        organization_id=organization_id,
        decision=payload.decision,
        reason=payload.reason.strip(),
        evidence=payload.evidence,
        reviewer=reviewer[:200],
    )
    db.add(row)
    db.add(AuditLog(
        action="organization_review_decision_recorded",
        actor=reviewer[:200],
        details={
            "organization_id": organization_id,
            "decision_id": row.id,
            "decision": payload.decision,
            "request_id": getattr(request.state, "request_id", None),
        },
    ))
    db.commit()
    db.refresh(row)
    return {"item": decision_out(row), "message": "Review decision recorded. Canonical registry fields were not changed."}
