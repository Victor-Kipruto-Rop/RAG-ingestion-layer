import logging
from contextlib import asynccontextmanager
import time,uuid
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .config import settings
from .database import Base,engine,SessionLocal
from . import models
from .api import router
from .models import WarehouseAccessLog
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
@asynccontextmanager
async def lifespan(app):
 if settings.app_env.lower()!='production':Base.metadata.create_all(bind=engine)
 yield
app=FastAPI(title=settings.app_name,version='1.0.0',description='Internal registry ingestion and lookup API',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origin_list,allow_credentials=False,allow_methods=['GET','POST','PATCH','OPTIONS'],allow_headers=['Content-Type','X-API-Key','X-Correlation-ID','Idempotency-Key','X-Registry-Source'])
app.include_router(router)
@app.middleware('http')
async def warehouse_access_telemetry(request,call_next):
 path=request.url.path
 if not path.startswith('/api/v1/warehouse/'):
  return await call_next(request)
 started=time.perf_counter();request_id=request.headers.get('X-Correlation-ID') or str(uuid.uuid4())
 response=None;outcome='ERROR'
 try:
  response=await call_next(request)
  outcome='SUCCESS' if response.status_code<400 else ('NOT_FOUND' if response.status_code==404 else 'ERROR')
  return response
 finally:
  duration=(time.perf_counter()-started)*1000
  try:
   with SessionLocal() as db:
    db.add(WarehouseAccessLog(request_id=request_id,caller_service=(request.headers.get('X-Caller-Service') or 'unknown')[:200],endpoint=path[:300],http_method=request.method[:12],response_status=response.status_code if response else 500,duration_ms=round(duration,3),outcome=outcome,query_type='organization_lookup' if path.endswith('query-organization') else 'telemetry'))
    db.commit()
  except Exception:
   logging.exception('Unable to persist warehouse access telemetry request_id=%s',request_id)

@app.get('/health/live',tags=['health'])
def live():return {'status':'alive','service':settings.app_name}
@app.get('/health/ready',tags=['health'])
def ready():
 try:
  with engine.connect() as conn:conn.execute(text('SELECT 1'))
  return {'status':'ready','database':'healthy'}
 except Exception:
  logging.exception('Database readiness check failed');raise HTTPException(503,detail={'status':'not_ready','database':'unavailable'})
@app.get('/health',tags=['health'])
def health():
 try:
  with engine.connect() as conn:conn.execute(text('SELECT 1'))
  status='healthy'
 except Exception:status='degraded'
 return {'status':status,'database':'healthy' if status=='healthy' else 'unavailable','r2_configured':bool(settings.r2_bucket_name)}
