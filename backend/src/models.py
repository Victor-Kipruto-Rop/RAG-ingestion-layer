import uuid
from datetime import datetime,timezone
from sqlalchemy import DateTime,Integer,String,Text,UniqueConstraint,Index,ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
json_type=JSON().with_variant(JSONB,'postgresql')
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
 last_seen_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
 data_quality_status:Mapped[str]=mapped_column(String(30),default='UNREVIEWED',nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
 updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),onupdate=lambda:datetime.now(timezone.utc),nullable=False)
class OrganizationRecordVersion(Base):
 __tablename__='organization_record_versions'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 organization_id:Mapped[str]=mapped_column(String(36),ForeignKey('internal_organizations.id',ondelete='CASCADE'),index=True,nullable=False)
 change_type:Mapped[str]=mapped_column(String(30),nullable=False)
 snapshot:Mapped[dict]=mapped_column(json_type,default=dict,nullable=False)
 source_name:Mapped[str|None]=mapped_column(String(200))
 source_file:Mapped[str|None]=mapped_column(String(500))
 source_row:Mapped[int|None]=mapped_column(Integer)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
class IngestionJob(Base):
 __tablename__='ingestion_jobs'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 file_name:Mapped[str]=mapped_column(String(500),nullable=False)
 object_key:Mapped[str|None]=mapped_column(String(1000))
 status:Mapped[str]=mapped_column(String(40),default='QUEUED',nullable=False)
 records_processed:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 records_inserted:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 records_updated:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 records_skipped:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 error_summary:Mapped[str|None]=mapped_column(Text)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
 completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class AuditLog(Base):
 __tablename__='ingestion_audit_logs'
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
 action:Mapped[str]=mapped_column(String(100),nullable=False)
 actor:Mapped[str]=mapped_column(String(200),default='internal-service',nullable=False)
 file_name:Mapped[str|None]=mapped_column(String(500))
 details:Mapped[dict]=mapped_column(json_type,default=dict,nullable=False)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
