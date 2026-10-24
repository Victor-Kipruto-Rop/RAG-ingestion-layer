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
 __table_args__=(Index('ix_ingestion_jobs_status_next_attempt','status','next_attempt_at'),)
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
 heartbeat_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
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


class ApiKey(Base):
 __tablename__='api_keys'
 __table_args__=(Index('ix_api_keys_org_created','organization_id','created_at'),Index('ix_api_keys_status_environment','status','environment'))
 id:Mapped[str]=mapped_column(String(36),primary_key=True)
 organization_id:Mapped[str]=mapped_column(String(200),nullable=False)
 created_by_user_id:Mapped[str]=mapped_column(String(200),nullable=False)
 name:Mapped[str]=mapped_column(String(100),nullable=False)
 environment:Mapped[str]=mapped_column(String(20),nullable=False)
 key_prefix:Mapped[str]=mapped_column(String(32),nullable=False)
 secret_hash:Mapped[str]=mapped_column(String(64),unique=True,nullable=False)
 scopes:Mapped[list]=mapped_column(json_type,default=list,nullable=False)
 status:Mapped[str]=mapped_column(String(20),default='active',nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
 last_used_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 revoked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class ApiKeyAuditEvent(Base):
 __tablename__='api_key_audit_events'
 __table_args__=(Index('ix_api_key_audit_org_created','organization_id','created_at'),)
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 organization_id:Mapped[str]=mapped_column(String(200),nullable=False)
 actor_user_id:Mapped[str]=mapped_column(String(200),nullable=False)
 api_key_id:Mapped[str|None]=mapped_column(String(36))
 action:Mapped[str]=mapped_column(String(80),nullable=False)
 details:Mapped[dict]=mapped_column(json_type,default=dict,nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)


class AdminProfile(Base):
 __tablename__='admin_profiles'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default='admin')
 display_name:Mapped[str]=mapped_column(String(120),nullable=False,default='Datasource Operator')
 contact_email:Mapped[str|None]=mapped_column(String(320),nullable=True)
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,onupdate=now_utc,nullable=False)


class AdminNotificationRead(Base):
 __tablename__='admin_notification_reads'
 notification_key:Mapped[str]=mapped_column(String(300),primary_key=True)
 read_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)


class AdminAccount(Base):
 __tablename__='admin_accounts'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 email:Mapped[str]=mapped_column(String(320),unique=True,index=True,nullable=False)
 display_name:Mapped[str]=mapped_column(String(120),nullable=False)
 password_hash:Mapped[str]=mapped_column(String(255),nullable=False)
 email_verified_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
 disabled_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,onupdate=now_utc,nullable=False)


class AdminAuthChallenge(Base):
 __tablename__='admin_auth_challenges'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 email:Mapped[str]=mapped_column(String(320),index=True,nullable=False)
 purpose:Mapped[str]=mapped_column(String(32),nullable=False)
 otp_hash:Mapped[str]=mapped_column(String(64),nullable=False)
 password_hash:Mapped[str|None]=mapped_column(String(255),nullable=True)
 display_name:Mapped[str|None]=mapped_column(String(120),nullable=True)
 attempts:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
 consumed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)


class AdminSession(Base):
 __tablename__='admin_sessions'
 id:Mapped[str]=mapped_column(String(36),primary_key=True)
 email:Mapped[str|None]=mapped_column(String(320),index=True,nullable=True)
 auth_method:Mapped[str]=mapped_column(String(32),nullable=False,default='password')
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
 last_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
 expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
 revoked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
 user_agent:Mapped[str|None]=mapped_column(String(500),nullable=True)
 ip_digest:Mapped[str|None]=mapped_column(String(64),nullable=True)
 __table_args__=(Index('ix_admin_sessions_email_created','email','created_at'),Index('ix_admin_sessions_expiry','expires_at'),)


# Public developer-platform control plane. These tables are deliberately separate from
# the single-operator admin account/session tables above.
class DeveloperAccount(Base):
 __tablename__='developer_accounts'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 email:Mapped[str]=mapped_column(String(320),unique=True,index=True,nullable=False)
 display_name:Mapped[str]=mapped_column(String(120),nullable=False)
 password_hash:Mapped[str]=mapped_column(String(255),nullable=False)
 email_verified_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
 disabled_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,onupdate=now_utc,nullable=False)

class DeveloperWorkspace(Base):
 __tablename__='developer_workspaces'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 name:Mapped[str]=mapped_column(String(160),nullable=False)
 owner_user_id:Mapped[str]=mapped_column(String(36),ForeignKey('developer_accounts.id',ondelete='CASCADE'),index=True,nullable=False)
 verified:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
 production_access_approved:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class DeveloperProject(Base):
 __tablename__='developer_projects'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 workspace_id:Mapped[str]=mapped_column(String(36),ForeignKey('developer_workspaces.id',ondelete='CASCADE'),index=True,nullable=False)
 name:Mapped[str]=mapped_column(String(160),nullable=False)
 slug:Mapped[str]=mapped_column(String(180),unique=True,index=True,nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class DeveloperAuthChallenge(Base):
 __tablename__='developer_auth_challenges'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 email:Mapped[str]=mapped_column(String(320),index=True,nullable=False)
 purpose:Mapped[str]=mapped_column(String(32),nullable=False)
 otp_hash:Mapped[str]=mapped_column(String(64),nullable=False)
 password_hash:Mapped[str|None]=mapped_column(String(255),nullable=True)
 display_name:Mapped[str|None]=mapped_column(String(120),nullable=True)
 attempts:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
 consumed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class DeveloperSession(Base):
 __tablename__='developer_sessions'
 id:Mapped[str]=mapped_column(String(36),primary_key=True)
 user_id:Mapped[str]=mapped_column(String(36),ForeignKey('developer_accounts.id',ondelete='CASCADE'),index=True,nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
 last_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
 expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
 revoked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
 user_agent:Mapped[str|None]=mapped_column(String(500),nullable=True)
 ip_digest:Mapped[str|None]=mapped_column(String(64),nullable=True)

class DeveloperWebhook(Base):
 __tablename__='developer_webhooks'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 workspace_id:Mapped[str]=mapped_column(String(36),ForeignKey('developer_workspaces.id',ondelete='CASCADE'),index=True,nullable=False)
 project_id:Mapped[str|None]=mapped_column(String(36),ForeignKey('developer_projects.id',ondelete='SET NULL'),nullable=True)
 name:Mapped[str]=mapped_column(String(120),nullable=False)
 endpoint_url:Mapped[str]=mapped_column(String(2000),nullable=False)
 events:Mapped[list]=mapped_column(json_type,default=list,nullable=False)
 secret_ciphertext:Mapped[str]=mapped_column(Text,nullable=False)
 secret_prefix:Mapped[str]=mapped_column(String(24),nullable=False)
 enabled:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,onupdate=now_utc,nullable=False)

class DeveloperWebhookDelivery(Base):
 __tablename__='developer_webhook_deliveries'
 __table_args__=(Index('ix_dev_webhook_deliveries_hook_created','webhook_id','created_at'),)
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 webhook_id:Mapped[str]=mapped_column(String(36),ForeignKey('developer_webhooks.id',ondelete='CASCADE'),index=True,nullable=False)
 event_type:Mapped[str]=mapped_column(String(120),nullable=False)
 status:Mapped[str]=mapped_column(String(32),nullable=False)
 response_status:Mapped[int|None]=mapped_column(Integer,nullable=True)
 response_excerpt:Mapped[str|None]=mapped_column(String(500),nullable=True)
 duration_ms:Mapped[int|None]=mapped_column(Integer,nullable=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class DeveloperProductionAccessRequest(Base):
 __tablename__='developer_production_access_requests'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 workspace_id:Mapped[str]=mapped_column(String(36),ForeignKey('developer_workspaces.id',ondelete='CASCADE'),index=True,nullable=False)
 requested_by_user_id:Mapped[str]=mapped_column(String(36),ForeignKey('developer_accounts.id',ondelete='CASCADE'),nullable=False)
 use_case:Mapped[str]=mapped_column(Text,nullable=False)
 expected_volume:Mapped[str]=mapped_column(String(100),nullable=False)
 status:Mapped[str]=mapped_column(String(24),default='pending',nullable=False)
 reviewer_note:Mapped[str|None]=mapped_column(String(1000),nullable=True)
 reviewed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
