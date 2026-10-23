"""Verification case orchestration with explicit no-provider/no-verification states."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .database import get_db
from .models import VerificationCase, VerificationProviderCheck
from .security import require_api_key

router = APIRouter(prefix="/api/v1/verification", tags=["verification"])

PROVIDER_CATALOG = [
    {"provider_key":"kenya_brs","display_name":"Kenya Business Registration Service","status":"not_configured","integration_stage":"adapter_and_access_required","live_enabled":False},
    {"provider_key":"kenya_kra","display_name":"Kenya Revenue Authority","status":"not_configured","integration_stage":"adapter_and_access_required","live_enabled":False},
    {"provider_key":"peleza","display_name":"Peleza","status":"not_configured","integration_stage":"adapter_and_access_required","live_enabled":False},
]

class VerificationCaseRequest(BaseModel):
    legal_name: str | None = Field(default=None, max_length=500)
    registration_number: str | None = Field(default=None, max_length=120)
    tax_pin: str | None = Field(default=None, max_length=80)
    correlation_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def require_subject(self):
        if not (self.legal_name or "").strip() and not (self.registration_number or "").strip() and not (self.tax_pin or "").strip():
            raise ValueError("Provide a legal name, registration number, or tax PIN")
        return self

def _case_out(case):
    return {
        "id":case.id,"subject_type":case.subject_type,"legal_name":case.legal_name,
        "registration_number":case.registration_number,"tax_pin":case.tax_pin,
        "status":case.status,"correlation_id":case.correlation_id,
        "requested_by":case.requested_by,"result_summary":case.result_summary or {},
        "created_at":case.created_at.isoformat() if case.created_at else None,
        "updated_at":case.updated_at.isoformat() if case.updated_at else None,
    }

def _check_out(check):
    return {
        "id":check.id,"provider_key":check.provider_key,"status":check.status,
        "provider_reference":check.provider_reference,"response_code":check.response_code,
        "safe_result":check.safe_result or {},"error_category":check.error_category,
        "started_at":check.started_at.isoformat() if check.started_at else None,
        "completed_at":check.completed_at.isoformat() if check.completed_at else None,
        "created_at":check.created_at.isoformat() if check.created_at else None,
    }

@router.get("/providers", dependencies=[Depends(require_api_key)])
def list_verification_providers():
    return {"items":PROVIDER_CATALOG,"count":len(PROVIDER_CATALOG),
            "message":"No external provider check is executed until an approved, configured adapter is available."}

@router.post("/cases", status_code=201, dependencies=[Depends(require_api_key)])
def create_verification_case(payload:VerificationCaseRequest, request:Request, db:Session=Depends(get_db)):
    correlation_id=(payload.correlation_id or getattr(request.state,"request_id",None) or str(uuid.uuid4()))[:100]
    case=VerificationCase(
        legal_name=(payload.legal_name or "").strip() or None,
        registration_number=(payload.registration_number or "").strip() or None,
        tax_pin=(payload.tax_pin or "").strip() or None,
        correlation_id=correlation_id,
        status="not_configured",
        requested_by="internal-service",
        result_summary={"verification_performed":False,"reason":"no_provider_configured",
                        "message":"No live verification adapter is configured. This case is not verified."},
    )
    db.add(case)
    db.flush()
    for provider in PROVIDER_CATALOG:
        db.add(VerificationProviderCheck(
            case_id=case.id,provider_key=provider["provider_key"],status="not_configured",
            safe_result={"verification_performed":False,"reason":"adapter_or_access_not_configured"},
            error_category="PROVIDER_NOT_CONFIGURED",
        ))
    db.commit()
    db.refresh(case)
    return {"case":_case_out(case),"checks":[_check_out(check) for check in db.scalars(
        select(VerificationProviderCheck).where(VerificationProviderCheck.case_id==case.id).order_by(VerificationProviderCheck.provider_key)
    ).all()]}

@router.get("/cases", dependencies=[Depends(require_api_key)])
def list_verification_cases(page:int=Query(default=1,ge=1),page_size:int=Query(default=25,ge=1,le=100),db:Session=Depends(get_db)):
    total=db.scalar(select(func.count()).select_from(VerificationCase)) or 0
    cases=db.scalars(select(VerificationCase).order_by(VerificationCase.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return {"items":[_case_out(case) for case in cases],"total":total,"page":page,"page_size":page_size}

@router.get("/cases/{case_id}", dependencies=[Depends(require_api_key)])
def get_verification_case(case_id:str,db:Session=Depends(get_db)):
    case=db.get(VerificationCase,case_id)
    if not case:raise HTTPException(404,"Verification case not found")
    checks=db.scalars(select(VerificationProviderCheck).where(VerificationProviderCheck.case_id==case_id).order_by(VerificationProviderCheck.created_at)).all()
    return {"case":_case_out(case),"checks":[_check_out(check) for check in checks]}
