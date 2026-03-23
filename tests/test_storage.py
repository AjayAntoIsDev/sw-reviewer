"""Tests for storage layer (T04 + storage package)."""

import pytest
from pathlib import Path
from sw_reviewer.state import JobRepository, JobStatus, JobState
from sw_reviewer.storage.jobs import JobStore
from sw_reviewer.storage.artifacts import ArtifactRepository
from sw_reviewer.storage.sqlite import init_schema


def make_job(review_id="rev-store-001"):
    return JobState(
        review_id=review_id,
        status=JobStatus.PENDING,
        repository_url="https://github.com/test/repo",
    )


def test_job_repository_create_and_get(tmp_path):
    repo = JobRepository(db_path=str(tmp_path / "test.db"))
    job = make_job()
    repo.create_job(job)
    retrieved = repo.get_job(job.review_id)
    assert retrieved is not None
    assert retrieved.review_id == job.review_id
    assert retrieved.status == JobStatus.PENDING


def test_job_repository_update_status(tmp_path):
    repo = JobRepository(db_path=str(tmp_path / "test.db"))
    job = make_job("rev-update-001")
    repo.create_job(job)
    repo.update_job_status("rev-update-001", JobStatus.RUNNING)
    updated = repo.get_job("rev-update-001")
    assert updated.status == JobStatus.RUNNING


def test_job_repository_save_context(tmp_path):
    repo = JobRepository(db_path=str(tmp_path / "test.db"))
    job = make_job("rev-ctx-001")
    repo.create_job(job)
    repo.save_context("rev-ctx-001", {"key": "value"})
    updated = repo.get_job("rev-ctx-001")
    assert updated.context_data == {"key": "value"}


def test_job_store_cancel(tmp_path):
    store = JobStore(db_path=str(tmp_path / "test.db"))
    job = make_job("rev-cancel-001")
    store.create(job)
    result = store.cancel("rev-cancel-001")
    assert result is True
    cancelled = store.get("rev-cancel-001")
    assert cancelled.status == JobStatus.CANCELLED


def test_artifact_repository(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_schema(db_path)
    # Create job first for FK constraint
    repo = JobRepository(db_path=db_path)
    job = make_job("rev-artifact-001")
    repo.create_job(job)

    artifacts = ArtifactRepository(db_path=db_path)
    row_id = artifacts.save_artifact("rev-artifact-001", "pdf_report", "/tmp/report.pdf")
    assert row_id > 0

    items = artifacts.get_artifacts("rev-artifact-001")
    assert len(items) == 1
    assert items[0]["artifact_type"] == "pdf_report"


def test_artifact_get_by_type(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_schema(db_path)
    repo = JobRepository(db_path=db_path)
    job = make_job("rev-artifact-002")
    repo.create_job(job)

    artifacts = ArtifactRepository(db_path=db_path)
    artifacts.save_artifact("rev-artifact-002", "typ_report", "/tmp/report.typ")
    artifacts.save_artifact("rev-artifact-002", "pdf_report", "/tmp/report.pdf")

    pdf = artifacts.get_artifact_by_type("rev-artifact-002", "pdf_report")
    assert pdf is not None
    assert pdf["file_path"] == "/tmp/report.pdf"
