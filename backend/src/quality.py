from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from .database import get_db
from .models import Organization, IngestionJob, RegistrySource
from .security import require_api_key
router=APIRouter(prefix='/api/v1',tags=['data quality'],dependencies=[Depends(require_api_key)])

@router.get('/quality/summary')
def quality_summary(stale_after_days:int=Query(default=180,ge=1,le=3650),db:Session=Depends(get_db)):
 total=db.scalar(select(func.count()).select_from(Organization)) or 0
 missing_registration=db.scalar(select(func.count()).select_from(Organization).where(or_(Organization.normalized_registration_number.is_(None),Organization.normalized_registration_number==''))) or 0
 missing_tax_pin=db.scalar(select(func.count()).select_from(Organization).where(or_(Organization.normalized_tax_pin.is_(None),Organization.normalized_tax_pin==''))) or 0
 unreviewed=db.scalar(select(func.count()).select_from(Organization).where(Organization.data_quality_status.in_(['UNREVIEWED','UNKNOWN','PENDING']))) or 0
 cutoff=datetime.now(timezone.utc)-timedelta(days=stale_after_days)
 stale=db.scalar(select(func.count()).select_from(Organization).where(Organization.last_seen_at<cutoff)) or 0
 failed_jobs=db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status=='FAILED')) or 0
 return {'total_records':total,'missing_registration_number':missing_registration,'missing_tax_pin':missing_tax_pin,'unreviewed_records':unreviewed,'stale_records':stale,'failed_ingestion_jobs':failed_jobs,'stale_after_days':stale_after_days,'generated_at':datetime.now(timezone.utc).isoformat(),'interpretation':'Quality indicators only. Missing data and imported records are not proof of fraud or legal non-compliance.'}

@router.get('/registry/match-candidates')
def match_candidates(q:str=Query(min_length=2,max_length=200),limit:int=Query(default=10,ge=1,le=50),db:Session=Depends(get_db)):
 from rapidfuzz import fuzz
 from .ingestion.normalizer import normalize_legal_name
 normalized=normalize_legal_name(q) or ''
 rows=db.scalars(select(Organization).where(Organization.normalized_legal_name.ilike(f'%{normalized}%')).limit(250)).all()
 candidates=[]
 for row in rows:
  score=float(fuzz.WRatio(normalized,row.normalized_legal_name or ''))
  if score>=55:
   candidates.append({'organization_id':row.id,'legal_name':row.legal_name,'registration_number':row.registration_number,'tax_pin_present':bool(row.normalized_tax_pin),'source_name':row.source_name,'score':round(score,1),'review_status':'candidate_only'})
 candidates.sort(key=lambda item:item['score'],reverse=True)
 return {'query':q,'items':candidates[:limit],'count':min(len(candidates),limit),'warning':'Similarity is only a review aid. Do not auto-merge or treat a name match as identity verification.'}

@router.get('/sources/freshness')
def source_freshness(db:Session=Depends(get_db)):
 sources=db.scalars(select(RegistrySource).order_by(RegistrySource.precedence,RegistrySource.display_name)).all()
 return {'items':[{'source_key':s.source_key,'display_name':s.display_name,'enabled':s.enabled,'freshness_sla_hours':s.freshness_sla_hours,'last_import_at':None,'freshness_status':'unknown','note':'Last successful source import timestamps are not yet persisted per source.'} for s in sources],'generated_at':datetime.now(timezone.utc).isoformat()}
