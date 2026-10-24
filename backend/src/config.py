from urllib.parse import urlparse
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
 app_name:str='PesaGuard Registry System'
 app_env:str='development'
 database_url:str='sqlite:///./registry.db'
 registry_api_keys:str=''
 api_environment:str='production'
 api_key_auth_jwt_secret:str=''
 api_key_auth_jwt_keys_json:str=''
 api_key_auth_jwt_active_kid:str='current'
 api_key_auth_jwt_issuer:str=''
 api_key_auth_jwt_audience:str=''
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
 worker_retry_max_seconds:int=900
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
 session_secret:str=''
 admin_password_hash:str=''
 session_ttl_seconds:int=28800
 session_cookie_secure:bool=True
 admin_login_max_attempts_per_minute:int=10
 public_base_url:str=''
 google_oauth_client_id:str=''
 google_oauth_client_secret:str=''
 github_oauth_client_id:str=''
 github_oauth_client_secret:str=''
 admin_oauth_allowed_emails:str=''
 admin_signup_allowed_emails:str=''
 auth_otp_ttl_seconds:int=600
 auth_otp_max_attempts:int=5
 auth_otp_pepper:str=''
 resend_api_key:str=''
 resend_from_email:str=''
 smtp_host:str=''
 smtp_port:int=587
 smtp_username:str=''
 smtp_password:str=''
 smtp_from_email:str=''
 smtp_use_starttls:bool=True
 smtp_use_ssl:bool=False
 developer_access_token_secret:str=''
 developer_access_token_issuer:str='pesaguard-developer-platform'
 developer_access_token_audience:str='pesaguard-developer-api'
 developer_access_token_ttl_seconds:int=900
 developer_session_ttl_seconds:int=2592000
 developer_webhook_encryption_key:str=''
 developer_public_base_url:str='https://sandbox-api.pesaguard.co.ke'
 developer_oauth_callback_base_url:str=''
 developer_frontend_url:str=''
 developer_production_base_url:str='https://api.pesaguard.co.ke'
 worker_commit_interval_seconds:int=60
 entity_resolution_max_candidates:int=200
 upload_ttl_grace_seconds:int=900
 ingestion_row_savepoints:bool=True
 model_config=SettingsConfigDict(env_file='.env',extra='ignore',case_sensitive=False)
 @property
 def cors_origin_list(self): return [x.strip() for x in self.cors_origins.split(',') if x.strip()]
 @property
 def api_key_list(self): return [x.strip() for x in self.registry_api_keys.split(',') if x.strip()]
 @property
 def admin_oauth_email_list(self): return [x.strip().lower() for x in self.admin_oauth_allowed_emails.split(',') if x.strip()]
 @property
 def admin_signup_email_list(self): return [x.strip().lower() for x in self.admin_signup_allowed_emails.split(',') if x.strip()]
 @property
 def auth_email_delivery_configured(self):
  resend_ready = bool(self.resend_api_key and self.resend_from_email)
  smtp_ready = bool(self.smtp_host and self.smtp_from_email and (self.smtp_username and self.smtp_password or not self.smtp_username and not self.smtp_password))
  return bool(len(self.auth_otp_pepper) >= 32 and (resend_ready or smtp_ready))
@lru_cache
def get_settings(): return Settings()
settings=get_settings()


def validate_runtime_config():
 sandbox_url = urlparse(settings.developer_public_base_url.strip())
 production_url = urlparse(settings.developer_production_base_url.strip())
 if not sandbox_url.hostname or not production_url.hostname:
  raise RuntimeError('Invalid configuration: DEVELOPER_PUBLIC_BASE_URL and DEVELOPER_PRODUCTION_BASE_URL must be absolute URLs')
 if settings.developer_public_base_url.rstrip('/') == settings.developer_production_base_url.rstrip('/'):
  raise RuntimeError('Invalid configuration: sandbox and production API base URLs must be different')
 if settings.app_env.lower() in {'staging', 'production'}:
  if sandbox_url.scheme != 'https' or production_url.scheme != 'https':
   raise RuntimeError('Invalid configuration: developer sandbox and production base URLs must use HTTPS in production')
  if sandbox_url.hostname.lower() == production_url.hostname.lower():
   raise RuntimeError('Invalid configuration: sandbox and production must use different hostnames in production')
 if settings.cors_origin_list and '*' in settings.cors_origin_list:
  raise RuntimeError("Invalid configuration: CORS_ORIGINS must list explicit origins; '*' is not allowed because the dashboard uses credentialed requests")
 if settings.auth_otp_ttl_seconds < 60 or settings.auth_otp_ttl_seconds > 1800 or settings.auth_otp_max_attempts < 1 or settings.auth_otp_max_attempts > 10:
  raise RuntimeError('Invalid configuration: AUTH_OTP_TTL_SECONDS must be 60-1800 and AUTH_OTP_MAX_ATTEMPTS must be 1-10')
 if settings.smtp_use_ssl and settings.smtp_use_starttls:
  raise RuntimeError('Invalid configuration: SMTP_USE_SSL and SMTP_USE_STARTTLS cannot both be enabled')
 if settings.app_env.lower() in {'staging', 'production'} and settings.admin_signup_email_list and not settings.auth_email_delivery_configured:
  raise RuntimeError('Invalid configuration: RESEND_API_KEY + RESEND_FROM_EMAIL (preferred) or SMTP settings, and AUTH_OTP_PEPPER >= 32 characters are required for operator sign-up')
 if settings.app_env.lower() in {'staging', 'production'} and settings.admin_signup_email_list and len(settings.auth_otp_pepper) < 32:
  raise RuntimeError('Invalid configuration: AUTH_OTP_PEPPER must contain at least 32 characters')
 if settings.developer_access_token_secret and len(settings.developer_access_token_secret.encode()) < 32:
  raise RuntimeError('Invalid configuration: DEVELOPER_ACCESS_TOKEN_SECRET must be at least 32 characters')
 if settings.developer_access_token_ttl_seconds < 300 or settings.developer_access_token_ttl_seconds > 3600:
  raise RuntimeError('Invalid configuration: DEVELOPER_ACCESS_TOKEN_TTL_SECONDS must be 300-3600')
 if settings.developer_session_ttl_seconds < 3600 or settings.developer_session_ttl_seconds > 7776000:
  raise RuntimeError('Invalid configuration: DEVELOPER_SESSION_TTL_SECONDS must be 3600-7776000')
 if settings.app_env.lower() in {'staging', 'production'} and settings.developer_access_token_secret and not settings.developer_webhook_encryption_key:
  raise RuntimeError('Invalid configuration: DEVELOPER_WEBHOOK_ENCRYPTION_KEY is required when the developer platform is enabled in production')
 if settings.developer_webhook_encryption_key and len(settings.developer_webhook_encryption_key.encode()) < 32:
  raise RuntimeError('Invalid configuration: DEVELOPER_WEBHOOK_ENCRYPTION_KEY must be at least 32 characters')
 if settings.admin_password_hash and len(settings.session_secret)<32:
  raise RuntimeError('Invalid configuration: SESSION_SECRET must be at least 32 characters when ADMIN_PASSWORD_HASH is set')
 # Validate worker safety limits in every environment, not only production.
 if settings.worker_poll_seconds <= 0:
  raise RuntimeError('Invalid configuration: WORKER_POLL_SECONDS must be greater than zero')
 if settings.worker_max_attempts < 1:
  raise RuntimeError('Invalid configuration: WORKER_MAX_ATTEMPTS must be at least 1')
 if settings.worker_retry_seconds < 1:
  raise RuntimeError('Invalid configuration: WORKER_RETRY_SECONDS must be at least 1')
 if settings.worker_retry_max_seconds < settings.worker_retry_seconds:
  raise RuntimeError('Invalid configuration: WORKER_RETRY_MAX_SECONDS must be greater than or equal to WORKER_RETRY_SECONDS')
 if settings.worker_stale_after_seconds < 1:
  raise RuntimeError('Invalid configuration: WORKER_STALE_AFTER_SECONDS must be at least 1')
 if settings.worker_max_jobs_per_run < 1:
  raise RuntimeError('Invalid configuration: WORKER_MAX_JOBS_PER_RUN must be at least 1')
 if settings.ingestion_batch_size < 1:
  raise RuntimeError('Invalid configuration: INGESTION_BATCH_SIZE must be at least 1')
 if settings.max_upload_bytes < 1 or settings.max_direct_upload_bytes < 1:
  raise RuntimeError('Invalid configuration: upload size limits must be greater than zero')
 if settings.direct_upload_url_ttl_seconds < 1:
  raise RuntimeError('Invalid configuration: DIRECT_UPLOAD_URL_TTL_SECONDS must be at least 1')
 if settings.hmac_clock_skew_seconds < 0 or settings.hmac_nonce_ttl_seconds < 1:
  raise RuntimeError('Invalid configuration: HMAC clock skew must be non-negative and nonce TTL must be at least 1')
 if settings.registry_rate_limit_capacity < 1 or settings.registry_rate_limit_refill_per_second <= 0:
  raise RuntimeError('Invalid configuration: registry rate-limit capacity and refill rate must be positive')
 if settings.registry_cache_ttl_seconds < 0 or settings.registry_cache_negative_ttl_seconds < 0:
  raise RuntimeError('Invalid configuration: registry cache TTL values must be non-negative')
 if settings.app_env.lower() not in {'staging', 'production'}:
  return
 missing=[]
 if not settings.api_key_list or {'change-this-local-only-key-before-use','replace-with-a-long-random-secret'} & set(settings.api_key_list):
  missing.append('REGISTRY_API_KEYS')
 if settings.database_url.startswith('sqlite'):
  missing.append('DATABASE_URL (PostgreSQL required in production)')
 if not all([settings.r2_account_id,settings.r2_access_key_id,settings.r2_secret_access_key,settings.r2_bucket_name]):
  missing.append('R2_ACCOUNT_ID/R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY/R2_BUCKET_NAME')
 if settings.require_hmac and not settings.hmac_shared_secret:
  missing.append('HMAC_SHARED_SECRET')
 if not settings.redis_url:
  redis_reason = 'distributed production rate limiting and shared coordination'
  if settings.require_hmac:
   redis_reason += ' and HMAC replay protection'
  missing.append('REDIS_URL (required for ' + redis_reason + ')')
 if not (settings.api_key_auth_jwt_secret or settings.api_key_auth_jwt_keys_json or settings.developer_access_token_secret):
  missing.append('PesaGuard identity signing keys or DEVELOPER_ACCESS_TOKEN_SECRET')
 if (settings.api_key_auth_jwt_secret or settings.api_key_auth_jwt_keys_json) and not (settings.api_key_auth_jwt_issuer and settings.api_key_auth_jwt_audience) and not settings.developer_access_token_secret:
  missing.append('API_KEY_AUTH_JWT_ISSUER/API_KEY_AUTH_JWT_AUDIENCE (PesaGuard identity token validation)')
 if settings.api_environment.lower().strip() not in {'sandbox','production'}:
  missing.append('API_ENVIRONMENT (must be sandbox or production)')
 if settings.admin_password_hash and not settings.session_cookie_secure:
  missing.append('SESSION_COOKIE_SECURE=true (required for dashboard sessions in production)')
 if settings.admin_password_hash and not settings.redis_url:
  missing.append('REDIS_URL (required for distributed admin login rate limiting)')
 if missing:
  raise RuntimeError('Invalid production configuration: '+', '.join(missing))
