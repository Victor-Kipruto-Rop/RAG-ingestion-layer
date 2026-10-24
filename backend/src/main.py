import logging
from contextlib import asynccontextmanager
import re,time,uuid
from datetime import datetime,timezone,timedelta
import hmac
import structlog
from prometheus_client import Counter,Histogram,Gauge,generate_latest,CONTENT_TYPE_LATEST
from fastapi import Request,Header
from fastapi.responses import Response
from sqlalchemy import event,func,select
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .config import settings,validate_runtime_config
from .database import engine,SessionLocal
from . import models
from .api import router
from .api_keys import router as api_keys_router
from .admin_auth import router as admin_router, COOKIE_NAME, session_from_request, refresh_session_token
from .developer_platform import router as developer_router
from .models import WarehouseAccessLog, AdminSession, now_utc
from . import storage as storage_module
from .security import _redis_client
structlog.configure(processors=[structlog.processors.TimeStamper(fmt='iso'),structlog.processors.add_log_level,structlog.processors.format_exc_info,structlog.processors.JSONRenderer()],logger_factory=structlog.stdlib.LoggerFactory())
logging.basicConfig(level=logging.INFO,format='%(message)s')
log=structlog.get_logger('registry.api')
HTTP_REQUESTS=Counter('registry_http_requests_total','HTTP requests handled by the registry API',['method','route','status'])
HTTP_DURATION=Histogram('registry_http_request_duration_seconds','HTTP request duration in seconds',['method','route'])
DB_QUERY_DURATION=Histogram('registry_db_query_duration_seconds','Database statement duration in seconds')
INGESTION_QUEUE_DEPTH=Gauge('registry_ingestion_queue_depth','Number of queued ingestion jobs')
INGESTION_ROWS_PROCESSED=Gauge('registry_ingestion_rows_processed','Cumulative row count reported by ingestion jobs')
INGESTION_ROWS_PER_SECOND_5M=Gauge('registry_ingestion_rows_per_second_5m','Rows processed in completed jobs over the last five minutes divided by 300 seconds')

@event.listens_for(engine, 'before_cursor_execute')
def _start_query_timer(conn, cursor, statement, parameters, context, executemany):
 conn.info.setdefault('_registry_query_start', []).append(time.perf_counter())

@event.listens_for(engine, 'after_cursor_execute')
def _finish_query_timer(conn, cursor, statement, parameters, context, executemany):
 starts=conn.info.get('_registry_query_start', [])
 if starts: DB_QUERY_DURATION.observe(max(0.0,time.perf_counter()-starts.pop()))
@asynccontextmanager
async def lifespan(app):
 validate_runtime_config()
 yield
app=FastAPI(title=settings.app_name,version='1.0.0',description='Internal registry ingestion and lookup API',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origin_list,allow_credentials=True,allow_methods=['GET','POST','PATCH','DELETE','OPTIONS'],allow_headers=['Content-Type','X-API-Key','Authorization','X-Correlation-ID','Idempotency-Key','X-Registry-Source','X-CSRF-Token'])
app.include_router(router)
app.include_router(api_keys_router)
app.include_router(admin_router)
app.include_router(developer_router)
@app.middleware('http')
async def warehouse_access_telemetry(request,call_next):
 path=request.url.path
 if not path.startswith('/api/v1/warehouse/'):
  return await call_next(request)
 started=time.perf_counter();request_id=getattr(request.state,'request_id',None) or request.headers.get('X-Correlation-ID') or str(uuid.uuid4())
 response=None;outcome='ERROR'
 try:
  response=await call_next(request)
  outcome='SUCCESS' if response.status_code<400 else ('NOT_FOUND' if response.status_code==404 else 'ERROR')
  return response
 finally:
  status_code=response.status_code if response else 500
  # never let unauthenticated or throttled traffic write to the database
  if status_code not in (401,403,429):
   duration=(time.perf_counter()-started)*1000
   claimed=re.sub(r'[^A-Za-z0-9._:-]','',request.headers.get('X-Caller-Service') or '')[:100]
   caller='claimed:'+claimed if claimed else 'unknown'
   try:
    with SessionLocal() as db:
     db.add(WarehouseAccessLog(request_id=request_id,caller_service=caller,endpoint=path[:300],http_method=request.method[:12],response_status=status_code,duration_ms=round(duration,3),outcome=outcome,query_type='organization_lookup' if path.endswith('query-organization') else 'telemetry'))
     db.commit()
   except Exception:
    log.exception('warehouse_access_telemetry_persist_failed',request_id=request_id)

@app.middleware('http')
async def sliding_admin_session(request: Request, call_next):
 response = await call_next(request)
 if request.url.path.startswith('/api/v1/admin/') and response.status_code < 400:
  claims = session_from_request(request)
  if claims:
   token, renewed = refresh_session_token(claims)
   try:
    with SessionLocal() as db:
     session_row = db.get(AdminSession, claims.get('jti'))
     if session_row and session_row.revoked_at is None:
      session_row.expires_at = datetime.fromtimestamp(int(renewed['exp']), tz=timezone.utc)
      session_row.last_seen_at = now_utc()
      db.commit()
   except Exception as exc:
    log.warning('admin_session_refresh_persist_failed', error_type=type(exc).__name__)
   response.set_cookie(COOKIE_NAME, token, max_age=max(60, settings.session_ttl_seconds),
                       httponly=True, secure=settings.session_cookie_secure, samesite='strict', path='/')
   response.headers['Cache-Control'] = 'no-store'
 return response

@app.middleware('http')
async def request_observability(request:Request,call_next):
 request_id=(request.headers.get('X-Correlation-ID') or str(uuid.uuid4()))[:100]
 request.state.request_id=request_id
 started=time.perf_counter();status=500
 try:
  response=await call_next(request)
  status=response.status_code
  response.headers['X-Correlation-ID']=request_id
  return response
 finally:
  route_obj=request.scope.get('route')
  route=getattr(route_obj,'path','unmatched')
  duration=max(0.0,time.perf_counter()-started)
  HTTP_REQUESTS.labels(request.method,route,str(status)).inc()
  HTTP_DURATION.labels(request.method,route).observe(duration)
  log.info('http_request',request_id=request_id,method=request.method,route=route,status_code=status,duration_ms=round(duration*1000,3))

@app.get('/metrics',include_in_schema=False)
def metrics(x_metrics_token:str|None=Header(default=None,alias='X-Metrics-Token')):
 if not settings.metrics_token or not x_metrics_token or not hmac.compare_digest(settings.metrics_token,x_metrics_token):
  raise HTTPException(404,'Not found')
 with SessionLocal() as db:
  queued=db.scalar(select(func.count()).select_from(models.IngestionJob).where(models.IngestionJob.status=='QUEUED')) or 0
  rows=db.scalar(select(func.coalesce(func.sum(models.IngestionJob.records_processed),0))) or 0
  recent=db.scalar(select(func.coalesce(func.sum(models.IngestionJob.records_processed),0)).where(models.IngestionJob.completed_at>=datetime.now(timezone.utc)-timedelta(minutes=5))) or 0
  INGESTION_QUEUE_DEPTH.set(queued)
  INGESTION_ROWS_PROCESSED.set(rows)
  INGESTION_ROWS_PER_SECOND_5M.set(float(recent)/300.0)
 return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)

@app.get('/health/live',tags=['health'])
def live():return {'status':'alive','service':settings.app_name}
def _health_snapshot():
 checks = {}
 try:
  with engine.connect() as conn:
   conn.execute(text('SELECT 1'))
  checks['database'] = 'healthy'
 except Exception as exc:
  checks['database'] = 'unavailable'
  log.warning('database_readiness_check_failed', error_type=type(exc).__name__)

 production = settings.app_env.lower() == 'production'
 if storage_module.configured():
  try:
   storage_module.health_check()
   checks['object_storage'] = 'healthy'
  except Exception as exc:
   checks['object_storage'] = 'unavailable'
   log.warning('object_storage_readiness_check_failed', error_type=type(exc).__name__)
 else:
  checks['object_storage'] = 'unavailable' if production else 'not_configured'

 if settings.redis_url:
  try:
   client = _redis_client()
   if client is None:
    raise RuntimeError('Redis client unavailable')
   client.ping()
   checks['redis'] = 'healthy'
  except Exception as exc:
   checks['redis'] = 'unavailable'
   log.warning('redis_readiness_check_failed', error_type=type(exc).__name__)
 else:
  checks['redis'] = 'unavailable' if (production or settings.require_hmac) else 'not_configured'

 ready = checks['database'] == 'healthy'
 if production:
  ready = ready and checks['object_storage'] == 'healthy' and checks['redis'] == 'healthy'
 elif settings.require_hmac:
  ready = ready and checks['redis'] == 'healthy'
 return ready, checks


@app.get('/health/ready',tags=['health'])
def ready():
 is_ready, dependencies = _health_snapshot()
 if not is_ready:
  raise HTTPException(503, detail={'status':'not_ready','dependencies':dependencies})
 return {'status':'ready','dependencies':dependencies}


@app.get('/health',tags=['health'])
def health():
 is_ready, dependencies = _health_snapshot()
 return {'status':'healthy' if is_ready else 'degraded','dependencies':dependencies}
