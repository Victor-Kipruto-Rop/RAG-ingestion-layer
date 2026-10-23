"""Durable data-quality review workflow.

This service records reviewer decisions but never automatically merges organizations,
changes identifiers, or treats a similarity score as proof of identity.
"""
import json
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuditLog, Organization, QualityReviewCase, QualityReviewDecision
from .security import require_api_key

router = APIRouter(prefix="/api/v1/quality/reviews", tags=["quality review"], dependencies=[Depends(require_api_key)])

CaseType = Literal["possible_duplicate", "identifier_conflict", "missing_data", "stale_record", "source_conflict", "other"]
CaseStatus = Literal["open", "in_review", "resolved", "dismissed"]
DecisionType = Literal["same_entity", "different_entities", "needs_more_evidence", "data_quality_issue", "dismissed"]


def _bounded_evidence(value: dict) -> dict:
    if len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")) > 16_384:
        raise HTTPException(413, "Review evidence must be 16 KiB or smaller")
    return value


def _case_out(case: QualityReviewCase, decisions=None):
    result = {
        "id": case.id, "organization_id": case.organization_id,
        "related_organization_id": case.related_organization_id,
        "case_type": case.case_type, "status": case.status, "severity": case.severity,
        "summary": case.summary, "evidence": case.evidence or {},
        "created_by": case.created_by, "assigned_to": case.assigned_to,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }
    if decisions is not None:
        result["decisions"] = [
            {"id": d.id, "decision": d.decision, "notes": d.notes, "evidence": d.evidence or {},
             "reviewer_ref": d.reviewer_ref, "request_id": d.request_id,
             "created_at": d.created_at.isoformat() if d.created_at else None}
            for d in decisions
        ]
    return result


class ReviewCaseCreate(BaseModel):
    organization_id: str = Field(min_length=1, max_length=36)
    related_organization_id: str | None = Field(default=None, max_length=36)
    case_type: CaseType
    severity: Literal["low", "review", "high"] = "review"
    summary: str = Field(min_length=5, max_length=1000)
    evidence: dict = Field(default_factory=dict)
    assigned_to: str | None = Field(default=None, max_length=200)


class ReviewDecisionCreate(BaseModel):
    decision: DecisionType
    notes: str = Field(min_length=3, max_length=4000)
    evidence: dict = Field(default_factory=dict)


@router.post("", status_code=201)
def create_review_case(payload: ReviewCaseCreate, request: Request, identity: str = Depends(require_api_key), db: Session = Depends(get_db)):
    summary = payload.summary.strip()
    if not summary:
        raise HTTPException(422, "summary cannot be blank")
    _bounded_evidence(payload.evidence)
    if payload.related_organization_id == payload.organization_id:
        raise HTTPException(422, "A related organization must differ from the primary organization")
    if not db.get(Organization, payload.organization_id):
        raise HTTPException(404, "Primary organization was not found")
    if payload.related_organization_id and not db.get(Organization, payload.related_organization_id):
        raise HTTPException(404, "Related organization was not found")
    actor = getattr(request.state, "api_key_id", None) or identity[:200]
    case = QualityReviewCase(
        id=str(uuid.uuid4()), organization_id=payload.organization_id,
        related_organization_id=payload.related_organization_id, case_type=payload.case_type,
        status="open", severity=payload.severity, summary=summary, evidence=payload.evidence,
        created_by=actor,
        assigned_to=payload.assigned_to.strip() if payload.assigned_to and payload.assigned_to.strip() else None,
    )
    db.add(case)
    db.add(AuditLog(action="quality_review_case_created", actor=actor, details={
        "case_id": case.id, "organization_id": case.organization_id,
        "related_organization_id": case.related_organization_id, "case_type": case.case_type,
        "request_id": getattr(request.state, "request_id", None),
    }))
    db.commit()
    db.refresh(case)
    return {"item": _case_out(case), "warning": "Review cases record human review. They do not merge or certify organizations."}


@router.get("")
def list_review_cases(
    status: CaseStatus | None = None, case_type: CaseType | None = None,
    page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(QualityReviewCase)
    if status:
        stmt = stmt.where(QualityReviewCase.status == status)
    if case_type:
        stmt = stmt.where(QualityReviewCase.case_type == case_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(QualityReviewCase.created_at.desc(), QualityReviewCase.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_case_out(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/{case_id}")
def get_review_case(case_id: str, db: Session = Depends(get_db)):
    case = db.get(QualityReviewCase, case_id)
    if not case:
        raise HTTPException(404, "Review case was not found")
    decisions = db.scalars(select(QualityReviewDecision).where(QualityReviewDecision.case_id == case_id)
                           .order_by(QualityReviewDecision.created_at, QualityReviewDecision.id)).all()
    return {"item": _case_out(case, decisions)}


@router.post("/{case_id}/decisions", status_code=201)
def record_review_decision(
    case_id: str, payload: ReviewDecisionCreate, request: Request,
    identity: str = Depends(require_api_key), db: Session = Depends(get_db),
):
    case = db.get(QualityReviewCase, case_id)
    if not case:
        raise HTTPException(404, "Review case was not found")
    if case.status in {"resolved", "dismissed"}:
        raise HTTPException(409, "This review case is closed; create a new case to record a new review")
    if payload.decision in {"same_entity", "different_entities"} and not case.related_organization_id:
        raise HTTPException(422, "Entity comparison decisions require both primary and related organization IDs")
    notes = payload.notes.strip()
    if not notes:
        raise HTTPException(422, "Decision notes cannot be blank")
    _bounded_evidence(payload.evidence)
    reviewer = getattr(request.state, "api_key_id", None) or identity[:200]
    decision = QualityReviewDecision(
        id=str(uuid.uuid4()), case_id=case.id, decision=payload.decision, notes=notes,
        evidence=payload.evidence, reviewer_ref=reviewer,
        request_id=getattr(request.state, "request_id", None),
    )
    case.status = "open" if payload.decision == "needs_more_evidence" else ("dismissed" if payload.decision == "dismissed" else "resolved")
    db.add(decision)
    db.add(AuditLog(action="quality_review_decision_recorded", actor=reviewer, details={
        "case_id": case.id, "decision_id": decision.id, "decision": payload.decision,
        "request_id": getattr(request.state, "request_id", None),
        "organization_id": case.organization_id,
        "note": "No organization record was merged or rewritten.",
    }))
    db.commit()
    db.refresh(decision)
    db.refresh(case)
    return {
        "item": _case_out(case),
        "decision": {"id": decision.id, "decision": decision.decision, "notes": decision.notes,
                     "evidence": decision.evidence or {}, "reviewer_ref": decision.reviewer_ref,
                     "request_id": decision.request_id,
                     "created_at": decision.created_at.isoformat() if decision.created_at else None},
        "message": "Decision recorded. Organization records were not automatically changed or merged.",
    }
