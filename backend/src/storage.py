import boto3
from botocore.config import Config
from .config import settings
class StorageNotConfigured(RuntimeError):pass
def configured():return all([settings.r2_account_id,settings.r2_access_key_id,settings.r2_secret_access_key,settings.r2_bucket_name])
def client():
 if not configured():raise StorageNotConfigured('Cloudflare R2 is not configured')
 endpoint=settings.r2_endpoint_url or f'https://{settings.r2_account_id}.r2.cloudflarestorage.com'
 return boto3.client('s3',endpoint_url=endpoint,aws_access_key_id=settings.r2_access_key_id,aws_secret_access_key=settings.r2_secret_access_key,region_name='auto',config=Config(signature_version='s3v4',retries={'max_attempts':3,'mode':'standard'}))
def upload_bytes(key,body,content_type):client().put_object(Bucket=settings.r2_bucket_name,Key=key,Body=body,ContentType=content_type,ServerSideEncryption='AES256')
def health_check():client().head_bucket(Bucket=settings.r2_bucket_name);return True
