import uuid
from datetime import datetime,timezone
from sqlalchemy import DateTime,Integer,BigInteger,String,Text,UniqueConstraint,Index,ForeignKey,Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
json_type=JSON().with_variant(JSONB,'postgresql')
def now_utc(): return datetime.now(timezone.utc)
class Organization(Base):
 __tablename__='internal_organizations'
 __table_args__=(UniqueConstraint('normalized_registration_number',name='uq_org_registration'),Index('ix_org_normalized_name','normalized_legal_name'))
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 legal_name:Mapped[str]=mapped_column(String(500),nullable=False)
 normalized_legal_name:Mapped[str]=mapped_column(String(500),nullable=False,index=True)
 registration_number:Mapped[str|None]=mapped_column(String(120),nullable=True)
 normalized_registration_number:Mapped[str|None]=mapped_column(String(120),nullable=True,index=True)
 tax_pin:Mapped[str|None]=mapped_column(String(80),nullable=True)
 normalized_tax_pin:Mapped[str|None]=mapped_column(String(80),nullable=True,index=True)
 status:Mapped[str]=mapped_column(String(30),default='ACTIVE',nullable=False)
 registry_payload:Mapped[dict]=mapped_column(json_type,default=dict,nullable=False)
 source_file:Mapped[str|None]=mapped_column(String(500))
 source_row:Mapped[int|None]=mapped_column(Integer)
 source_name:Mapped[str|None]=mapped_column(String(200))
 source_record_id:Mapped[str|None]=mapped_column(String(200))
 source_published_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 last_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
 data_quality_status:Mapped[str]=mapped_column(String(30),default='UNREVIEWED',nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,onupdate=now_utc,nullable=False)
class OrganizationRecordVersion(Base):
 __tablename__='organization_record_versions'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 organization_id:Mapped[str]=mapped_column(String(36),ForeignKey('internal_organizations.id',ondelete='CASCADE'),index=True,nullable=False)
 change_type:Mapped[str]=mapped_column(String(30),nullable=False)
 snapshot:Mapped[dict]=mapped_column(json_type,default=dict,nullable=False)
 source_name:Mapped[str|None]=mapped_column(String(200))
 source_file:Mapped[str|None]=mapped_column(String(500))
 source_row:Mapped[int|None]=mapped_column(Integer)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
class RegistrySource(Base):
 __tablename__='registry_sources'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 source_key:Mapped[str]=mapped_column(String(100),unique=True,nullable=False,index=True)
 display_name:Mapped[str]=mapped_column(String(200),nullable=False)
 jurisdiction:Mapped[str]=mapped_column(String(100),default='KE',nullable=False)
 source_type:Mapped[str]=mapped_column(String(40),default='IMPORTED_DATASET',nullable=False)
 authority_url:Mapped[str|None]=mapped_column(String(1000))
 licence_reference:Mapped[str|None]=mapped_column(String(500))
 freshness_sla_hours:Mapped[int|None]=mapped_column(Integer)
 precedence:Mapped[int]=mapped_column(Integer,default=100,nullable=False)
 enabled:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
 notes:Mapped[str|None]=mapped_column(Text)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,onupdate=now_utc,nullable=False)
class IngestionJob(Base):
 __tablename__='ingestion_jobs'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 file_name:Mapped[str]=mapped_column(String(500),nullable=False)
 correlation_id:Mapped[str|None]=mapped_column(String(100),index=True)
 object_key:Mapped[str|None]=mapped_column(String(1000))
 content_type:Mapped[str|None]=mapped_column(String(200))
 source_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('registry_sources.id'))
 source_name:Mapped[str|None]=mapped_column(String(200))
 idempotency_key:Mapped[str|None]=mapped_column(String(200),unique=True)
 status:Mapped[str]=mapped_column(String(40),default='QUEUED',nullable=False,index=True)
 attempts:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 records_processed:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 records_inserted:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 records_updated:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 records_skipped:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 last_processed_row:Mapped[int]=mapped_column(Integer,default=1,nullable=False)
 error_summary:Mapped[str|None]=mapped_column(Text)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
 started_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 next_attempt_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),index=True)
 completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class IngestionRowError(Base):
 __tablename__='ingestion_row_errors'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 job_id:Mapped[str]=mapped_column(String(36),ForeignKey('ingestion_jobs.id',ondelete='CASCADE'),index=True,nullable=False)
 row_number:Mapped[int|None]=mapped_column(Integer)
 error_code:Mapped[str]=mapped_column(String(80),nullable=False)
 message:Mapped[str]=mapped_column(Text,nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
class AuditLog(Base):
 __tablename__='ingestion_audit_logs'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 action:Mapped[str]=mapped_column(String(100),nullable=False)
 actor:Mapped[str]=mapped_column(String(200),default='internal-service',nullable=False)
 file_name:Mapped[str|None]=mapped_column(String(500))
 details:Mapped[dict]=mapped_column(json_type,default=dict,nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class WarehouseRawImport(Base):
 __tablename__='warehouse_raw_imports'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 ingestion_job_id:Mapped[str]=mapped_column(String(36),ForeignKey('ingestion_jobs.id',ondelete='CASCADE'),unique=True,nullable=False)
 object_key:Mapped[str]=mapped_column(String(1000),nullable=False)
 original_filename:Mapped[str]=mapped_column(String(500),nullable=False)
 content_type:Mapped[str|None]=mapped_column(String(200))
 byte_size:Mapped[int]=mapped_column(BigInteger,default=0,nullable=False)
 sha256_hex:Mapped[str|None]=mapped_column(String(64),index=True)
 source_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('registry_sources.id'))
 source_name:Mapped[str|None]=mapped_column(String(200))
 source_published_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 uploaded_by:Mapped[str]=mapped_column(String(200),default='internal-service',nullable=False)
 import_status:Mapped[str]=mapped_column(String(40),default='QUEUED',nullable=False,index=True)
 metadata_json:Mapped[dict]=mapped_column('metadata',json_type,default=dict,nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
class WarehouseAccessLog(Base):
 __tablename__='warehouse_access_logs'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 request_id:Mapped[str|None]=mapped_column(String(100))
 caller_service:Mapped[str]=mapped_column(String(200),default='unknown',nullable=False)
 endpoint:Mapped[str]=mapped_column(String(300),nullable=False)
 http_method:Mapped[str]=mapped_column(String(12),nullable=False)
 response_status:Mapped[int]=mapped_column(Integer,nullable=False)
 duration_ms:Mapped[float]=mapped_column(nullable=False,default=0)
 outcome:Mapped[str]=mapped_column(String(40),default='UNKNOWN',nullable=False)
 query_type:Mapped[str|None]=mapped_column(String(40))
 result_count:Mapped[int|None]=mapped_column(Integer)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)


class FailedImportDLQ(Base):
 __tablename__='failed_imports_dlq'
 __table_args__=(UniqueConstraint('job_id','row_number','error_code',name='uq_failed_import_job_row_code'),Index('ix_failed_imports_dlq_created_at','created_at'))
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 job_id:Mapped[str]=mapped_column(String(36),ForeignKey('ingestion_jobs.id',ondelete='RESTRICT'),nullable=False,index=True)
 row_number:Mapped[int]=mapped_column(Integer,nullable=False)
 error_code:Mapped[str]=mapped_column(String(80),nullable=False)
 error_type:Mapped[str]=mapped_column(String(200),nullable=False)
 message:Mapped[str]=mapped_column(Text,nullable=False)
 sanitized_row:Mapped[dict]=mapped_column(json_type,default=dict,nullable=False)
 traceback_text:Mapped[str]=mapped_column(Text,nullable=False)
 resolved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)


class ManagedAPIKey(Base):
 __tablename__='managed_api_keys'
 __table_args__=(Index('ix_managed_api_keys_environment_status','environment','status'),)
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 name:Mapped[str]=mapped_column(String(120),nullable=False)
 environment:Mapped[str]=mapped_column(String(20),nullable=False)
 key_prefix:Mapped[str]=mapped_column(String(80),nullable=False,unique=True)
 secret_hash:Mapped[str]=mapped_column(String(64),nullable=False,unique=True)
 scopes:Mapped[list]=mapped_column(json_type,default=list,nullable=False)
 status:Mapped[str]=mapped_column(String(20),default='active',nullable=False,index=True)
 created_by:Mapped[str]=mapped_column(String(120),default='operator',nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
 last_used_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 revoked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 rotated_from_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('managed_api_keys.id'))

class APIKeySecurityEvent(Base):
 __tablename__='api_key_security_events'
 __table_args__=(Index('ix_api_key_security_events_created_at','created_at'),)
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 key_id:Mapped[str|None]=mapped_column(String(36),index=True)
 key_prefix:Mapped[str|None]=mapped_column(String(80))
 event_type:Mapped[str]=mapped_column(String(80),nullable=False)
 expected_environment:Mapped[str|None]=mapped_column(String(20))
 key_environment:Mapped[str|None]=mapped_column(String(20))
 endpoint:Mapped[str|None]=mapped_column(String(300))
 http_method:Mapped[str|None]=mapped_column(String(12))
 request_id:Mapped[str|None]=mapped_column(String(100))
 client_ip:Mapped[str|None]=mapped_column(String(80))
 details:Mapped[dict]=mapped_column(json_type,default=dict,nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
