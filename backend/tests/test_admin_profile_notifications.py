from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.admin_auth import NotificationReadRequest, ProfileUpdateRequest, _job_notification


def test_profile_update_requires_display_name_and_limits_length():
    assert ProfileUpdateRequest(display_name="Data Operator").display_name == "Data Operator"
    with pytest.raises(ValidationError):
        ProfileUpdateRequest(display_name="x")
    with pytest.raises(ValidationError):
        ProfileUpdateRequest(display_name="x" * 121)


def test_notification_read_request_limits_batch_size():
    assert NotificationReadRequest(notification_keys=["job:1:failed:now"]).notification_keys
    with pytest.raises(ValidationError):
        NotificationReadRequest(notification_keys=[])
    with pytest.raises(ValidationError):
        NotificationReadRequest(notification_keys=[f"job:{i}" for i in range(101)])


def test_failed_job_creates_critical_notification_with_stable_read_key():
    changed = datetime(2026, 10, 24, 12, 30, tzinfo=timezone.utc)
    job = SimpleNamespace(id="job-123", status="FAILED", updated_at=changed,
                          completed_at=None, created_at=changed,
                          error_summary="Input validation failed", file_name="registry.csv")

    notification = _job_notification(job)

    assert notification["severity"] == "critical"
    assert notification["status"] == "failed"
    assert notification["detail"] == "Input validation failed"
    assert notification["id"] == "job:job-123:failed:2026-10-24T12:30:00+00:00"


def test_successful_job_without_warning_does_not_create_notification():
    job = SimpleNamespace(id="job-456", status="COMPLETED", updated_at=None,
                          completed_at=None, created_at=None,
                          error_summary=None, file_name="registry.csv")

    assert _job_notification(job) is None
