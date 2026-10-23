from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
 app_name:str='PesaGuard Registry System'
 app_env:str='development'
 database_url:str='sqlite:///./registry.db'
 registry_api_keys:str=''
 cors_origins:str='http://localhost:5173'
 max_upload_bytes:int=52428800
 max_records_per_file:int=1000000
 r2_account_id:str=''
 r2_access_key_id:str=''
 r2_secret_access_key:str=''
 r2_bucket_name:str=''
 r2_endpoint_url:str=''
 model_config=SettingsConfigDict(env_file='.env',extra='ignore',case_sensitive=False)
 @property
 def cors_origin_list(self): return [x.strip() for x in self.cors_origins.split(',') if x.strip()]
 @property
 def api_key_list(self): return [x.strip() for x in self.registry_api_keys.split(',') if x.strip()]
@lru_cache
def get_settings(): return Settings()
settings=get_settings()
