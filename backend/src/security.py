import hmac
from fastapi import Header,HTTPException
from .config import settings
def require_api_key(x_api_key:str|None=Header(default=None,alias='X-API-Key')):
 keys=settings.api_key_list
 if not keys:
  raise HTTPException(503,'Service authentication is not configured')
 if not x_api_key or not any(hmac.compare_digest(x_api_key,key) for key in keys):
  raise HTTPException(401,'Invalid or missing API key')
 return 'internal-service'
