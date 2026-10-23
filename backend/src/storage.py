import os
from pathlib import Path
import boto3
from botocore.config import Config
from .config import settings
class StorageNotConfigured(RuntimeError):pass
def configured():return all([settings.r2_account_id,settings.r2_access_key_id,settings.r2_secret_access_key,settings.r2_bucket_name])
def client():
 if not configured():raise StorageNotConfigured('Cloudflare R2 is not configured')
 endpoint=settings.r2_endpoint_url or f'https://{settings.r2_account_id}.r2.cloudflarestorage.com'
 return boto3.client('s3',endpoint_url=endpoint,aws_access_key_id=settings.r2_access_key_id,aws_secret_access_key=settings.r2_secret_access_key,region_name='auto',config=Config(signature_version='s3v4',retries={'max_attempts':3,'mode':'standard'}))
def upload_bytes(key,body,content_type):
 if configured():
  client().put_object(Bucket=settings.r2_bucket_name,Key=key,Body=body,ContentType=content_type,ServerSideEncryption='AES256')
  return f'r2://{key}'
 if settings.app_env.lower()=='production':raise StorageNotConfigured('Cloudflare R2 is required in production')
 root=Path(settings.local_storage_path).resolve()
 target=(root/key).resolve()
 if root not in target.parents:raise ValueError('Invalid storage key')
 target.parent.mkdir(parents=True,exist_ok=True)
 target.write_bytes(body)
 return f'local://{key}'
def download_bytes(key):
 if key.startswith('r2://'):key=key[5:]
 if key.startswith('local://'):key=key[8:]
 if configured():return client().get_object(Bucket=settings.r2_bucket_name,Key=key)['Body'].read()
 root=Path(settings.local_storage_path).resolve();target=(root/key).resolve()
 if root not in target.parents:raise ValueError('Invalid storage key')
 return target.read_bytes()
def health_check():
 if not configured():raise StorageNotConfigured('Cloudflare R2 is not configured')
 client().head_bucket(Bucket=settings.r2_bucket_name);return True
