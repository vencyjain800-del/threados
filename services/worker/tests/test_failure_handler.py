"""
Unit tests for the RQ job failure handler.

Covers:
  _handle_job_failure  Logs at ERROR with job_id, func_name, queue, exc_type, exc_message
  _handle_job_failure  Handles None exc_type / exc_value / traceback gracefully
  _handle_job_failure  Returns None so RQ default handler chain continues
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def _make_job(job_id: str = "abc-123", func_name: str = "worker.jobs.sync.run_backfill", origin: str = "default") -> MagicMock:
    job = MagicMock()
    job.id = job_id
    job.func_name = func_name
    job.origin = origin
    return job


def test_handle_job_failure_logs_error() -> None:
    """Failure handler emits a structured ERROR log with all required fields."""
    from worker.main import _handle_job_failure  # noqa: PLC0415

    job = _make_job()
    exc = ValueError("something went wrong")

    with patch("worker.main.log") as mock_log:
        result = _handle_job_failure(job, ValueError, exc, None)

    mock_log.error.assert_called_once()
    call_kwargs = mock_log.error.call_args
    # First positional arg is the event name
    assert call_kwargs.args[0] == "job.failed"
    kw = call_kwargs.kwargs
    assert kw["job_id"] == "abc-123"
    assert kw["func_name"] == "worker.jobs.sync.run_backfill"
    assert kw["queue"] == "default"
    assert kw["exc_type"] == "ValueError"
    assert kw["exc_message"] == "something went wrong"
    # Returns None so RQ's default handler chain continues
    assert result is None


def test_handle_job_failure_none_exc() -> None:
    """Failure handler does not crash when exc_type / exc_value / tb are None."""
    from worker.main import _handle_job_failure  # noqa: PLC0415

    job = _make_job()

    with patch("worker.main.log") as mock_log:
        result = _handle_job_failure(job, None, None, None)

    mock_log.error.assert_called_once()
    kw = mock_log.error.call_args.kwargs
    assert kw["exc_type"] == "Unknown"
    assert kw["exc_message"] == ""
    assert result is None


def test_handle_job_failure_includes_traceback() -> None:
    """Failure handler captures traceback text when a tb is provided."""
    from worker.main import _handle_job_failure  # noqa: PLC0415

    job = _make_job()

    import sys
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        _, exc_value, tb = sys.exc_info()

    with patch("worker.main.log") as mock_log:
        _handle_job_failure(job, RuntimeError, exc_value, tb)

    kw = mock_log.error.call_args.kwargs
    assert "RuntimeError" in kw["traceback"] or "boom" in kw["traceback"]
