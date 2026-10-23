import os
import shutil
import tempfile
from contextlib import contextmanager
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

def upload_fileobj(key,file_obj,content_type):
 """Upload a seekable file in bounded memory; boto3 handles multipart R2 uploads."""
 file_obj.seek(0)
 if configured():
  client().upload_fileobj(file_obj,settings.r2_bucket_name,key,ExtraArgs={'ContentType':content_type,'ServerSideEncryption':'AES256'})
  return f'r2://{key}'
 if settings.app_env.lower()=='production':raise StorageNotConfigured('Cloudflare R2 is required in production')
 root=Path(settings.local_storage_path).resolve();target=(root/key).resolve()
 if root not in target.parents:raise ValueError('Invalid storage key')
 target.parent.mkdir(parents=True,exist_ok=True)
 with target.open('wb') as out:
  while True:
   chunk=file_obj.read(1024*1024)
   if not chunk:break
   out.write(chunk)
 file_obj.seek(0)
 return f'local://{key}'


@contextmanager
def download_spooled_file(key, max_memory_bytes=1024 * 1024):
    """Download an object to a seekable spool that spills to disk above 1 MiB."""
    spool = tempfile.SpooledTemporaryFile(max_size=max_memory_bytes, mode='w+b')
    body = None
    try:
        if key.startswith('r2://'): key = key[5:]
        if key.startswith('local://'): key = key[8:]
        if configured():
            body = client().get_object(Bucket=settings.r2_bucket_name, Key=key)['Body']
            while True:
                chunk = body.read(1024 * 1024)
                if not chunk: break
                spool.write(chunk)
        else:
            root = Path(settings.local_storage_path).resolve()
            target = (root / key).resolve()
            if root not in target.parents: raise ValueError('Invalid storage key')
            with target.open('rb') as source: shutil.copyfileobj(source, spool, length=1024 * 1024)
        spool.seek(0)
        yield spool
    finally:
        if body is not None: body.close()
        spool.close()
