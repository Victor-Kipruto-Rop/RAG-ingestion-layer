import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .config import settings
from .database import Base,engine
from . import models
from .api import router
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
@asynccontextmanager
async def lifespan(app):
 if settings.app_env.lower()!='production':Base.metadata.create_all(bind=engine)
 yield
app=FastAPI(title=settings.app_name,version='1.0.0',description='Internal registry ingestion and lookup API',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origin_list,allow_credentials=False,allow_methods=['GET','POST','PATCH','OPTIONS'],allow_headers=['Content-Type','X-API-Key','X-Correlation-ID','Idempotency-Key','X-Registry-Source'])
app.include_router(router)
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
