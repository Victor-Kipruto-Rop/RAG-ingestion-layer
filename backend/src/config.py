from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
 app_name:str='PesaGuard Registry System'
 app_env:str='development'
 database_url:str='sqlite:///./registry.db'
 registry_api_keys:str=''
 datasource_environment:str=''
 datasource_admin_token:str=''
 managed_api_keys_enabled:bool=True
 cors_origins:str='http://localhost:5173'
 max_upload_bytes:int=52428800
 max_direct_upload_bytes:int=5368709120
 direct_upload_url_ttl_seconds:int=3600
 max_records_per_file:int=1000000
 ingestion_batch_size:int=5000
 local_storage_path:str='./.registry-uploads'
 worker_poll_seconds:float=2.0
 worker_max_attempts:int=3
 worker_retry_seconds:int=30
 worker_stale_after_seconds:int=900
 worker_max_jobs_per_run:int=10
 pdf_ocr_enabled:bool=False
 pdf_ocr_max_pages:int=25
 r2_account_id:str=''
 r2_access_key_id:str=''
 r2_secret_access_key:str=''
 r2_bucket_name:str=''
 r2_endpoint_url:str=''
 redis_url:str=''
 hmac_shared_secret:str=''
 require_hmac:bool=False
 hmac_clock_skew_seconds:int=300
 hmac_nonce_ttl_seconds:int=600
 registry_rate_limit_capacity:int=60
 registry_rate_limit_refill_per_second:float=1.0
 metrics_token:str=''
 registry_cache_ttl_seconds:int=300
 registry_cache_negative_ttl_seconds:int=30
 db_pool_size:int=5
 db_max_overflow:int=5
 db_pool_timeout_seconds:int=30
 db_pool_recycle_seconds:int=1800
 model_config=SettingsConfigDict(env_file='.env',extra='ignore',case_sensitive=False)
 @property
 def cors_origin_list(self): return [x.strip() for x in self.cors_origins.split(',') if x.strip()]
 @property
 def api_key_list(self): return [x.strip() for x in self.registry_api_keys.split(',') if x.strip()]
@lru_cache
def get_settings(): return Settings()
settings=get_settings()


def validate_runtime_config():
 if settings.app_env.lower()!='production':
  return
 missing=[]
 if not settings.api_key_list or 'change-this-local-only-key-before-use' in settings.api_key_list:
  missing.append('REGISTRY_API_KEYS')
 if settings.database_url.startswith('sqlite'):
  missing.append('DATABASE_URL (PostgreSQL required in production)')
 if not all([settings.r2_account_id,settings.r2_access_key_id,settings.r2_secret_access_key,settings.r2_bucket_name]):
  missing.append('R2_ACCOUNT_ID/R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY/R2_BUCKET_NAME')
 if settings.require_hmac and not settings.hmac_shared_secret:
  missing.append('HMAC_SHARED_SECRET')
 if settings.datasource_environment.strip().lower() not in {'production','sandbox'}:
  missing.append('DATASOURCE_ENVIRONMENT must be explicitly set to production or sandbox')
 if not settings.datasource_admin_token:
  missing.append('DATASOURCE_ADMIN_TOKEN (operator API-key management)')
 if settings.require_hmac and not settings.redis_url:
  missing.append('REDIS_URL (required for distributed HMAC replay protection)')
 if missing:
  raise RuntimeError('Invalid production configuration: '+', '.join(missing))
