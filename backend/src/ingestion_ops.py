"""Operational endpoints for reliable ingestion job inspection and recovery.

These endpoints deliberately expose metadata and sanitized row diagnostics only;
raw object keys, file contents, and traceback text are never returned.
"""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import AuditLog, FailedImportDLQ, IngestionJob, IngestionRowError, WarehouseRawImport
from .security import require_api_key

router = APIRouter(prefix="/api/v1/ingestion/jobs", tags=["ingestion operations"])


def safe_csv_cell(value):
    """Prevent spreadsheet formula injection in user-controlled CSV diagnostics."""
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + text
    return text


def _iso(value):
    return value.isoformat() if value else None


def _job_payload(job, raw):
    return {
        "id": job.id,
        "file_name": job.file_name,
        "correlation_id": job.correlation_id,
        "status": job.status,
        "attempts": job.attempts,
        "max_attempts": settings.worker_max_attempts,
        "source_name": job.source_name,
        "records_processed": job.records_processed,
        "records_inserted": job.records_inserted,
        "records_updated": job.records_updated,
        "records_skipped": job.records_skipped,
        "last_processed_row": job.last_processed_row,
        "error_summary": job.error_summary,
        "created_at": _iso(job.created_at),
        "started_at": _iso(job.started_at),
        "completed_at": _iso(job.completed_at),
        "next_attempt_at": _iso(job.next_attempt_at),
        "file": ({
            "size_bytes": raw.byte_size,
            "sha256": raw.sha256_hex,
            "import_status": raw.import_status,
            "uploaded_at": _iso(raw.created_at),
        } if raw else None),
        "progress_note": (
            "Row counters are committed progress, not a percentage estimate. "
            "PDF jobs requiring review are not automatically converted into registry records."
        ),
    }


@router.get("/{job_id}")
def get_ingestion_job(
    job_id: str,
    _: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    job = db.get(IngestionJob, job_id)
    if not job:
        raise HTTPException(404, "Ingestion job not found")
    raw = db.scalar(select(WarehouseRawImport).where(WarehouseRawImport.ingestion_job_id == job_id))
    return _job_payload(job, raw)


@router.post("/{job_id}/retry", status_code=202)
def retry_ingestion_job(
    job_id: str,
    _: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    """Requeue a failed CSV from its last committed checkpoint."""
    job = db.get(IngestionJob, job_id)
    if not job:
        raise HTTPException(404, "Ingestion job not found")
    if job.status != "FAILED":
        raise HTTPException(
            409,
            {"code": "JOB_NOT_RETRYABLE", "message": "Only failed jobs can be retried."},
        )
    suffix = "." + job.file_name.rsplit(".", 1)[-1].lower() if "." in job.file_name else ""
    if suffix != ".csv":
        raise HTTPException(
            409,
            {
                "code": "MANUAL_REVIEW_REQUIRED",
                "message": "PDF jobs are not automatically imported. Review the PDF diagnostics instead.",
            },
        )

    raw = db.scalar(select(WarehouseRawImport).where(WarehouseRawImport.ingestion_job_id == job_id))
    if not job.object_key or not raw:
        raise HTTPException(
            409,
            {"code": "SOURCE_OBJECT_MISSING", "message": "The original source object is unavailable."},
        )

    job.status = "QUEUED"
    job.attempts = 0
    job.next_attempt_at = None
    job.started_at = None
    job.completed_at = None
    job.error_summary = None
    raw.import_status = "QUEUED"
    db.add(
        AuditLog(
            action="registry_ingestion_manually_retried",
            actor="internal-service",
            file_name=job.file_name,
            details={
                "job_id": job.id,
                "correlation_id": job.correlation_id,
                "resume_from_row": job.last_processed_row,
            },
        )
    )
    db.commit()
    db.refresh(job)
    return {
        "job_id": job.id,
        "status": job.status,
        "resume_from_row": job.last_processed_row,
        "message": "Job queued from the last committed checkpoint.",
    }


@router.get("/{job_id}/errors.csv")
def download_job_errors_csv(
    job_id: str,
    _: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    if not db.get(IngestionJob, job_id):
        raise HTTPException(404, "Ingestion job not found")

    def rows():
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(["row_number", "error_code", "message", "created_at"])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        stmt = (
            select(IngestionRowError)
            .where(IngestionRowError.job_id == job_id)
            .order_by(IngestionRowError.row_number)
            .execution_options(yield_per=500)
        )
        for error in db.scalars(stmt):
            writer.writerow([
                error.row_number,
                safe_csv_cell(error.error_code),
                safe_csv_cell(error.message),
                _iso(error.created_at),
            ])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    return StreamingResponse(
        rows(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="ingestion-errors-{job_id}.csv"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{job_id}/dead-letter")
def get_job_dead_letters(
    job_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    _: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    if not db.get(IngestionJob, job_id):
        raise HTTPException(404, "Ingestion job not found")
    stmt = select(FailedImportDLQ).where(FailedImportDLQ.job_id == job_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(FailedImportDLQ.row_number)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "job_id": job_id,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "row_number": item.row_number,
                "error_code": item.error_code,
                "error_type": item.error_type,
                "message": item.message,
                "sanitized_row": item.sanitized_row or {},
                "resolved_at": _iso(item.resolved_at),
                "created_at": _iso(item.created_at),
            }
            for item in items
        ],
        "notice": "Tracebacks and raw source rows are intentionally not exposed by this endpoint.",
    }
