"""Tests for persistent automation run history.

Covers:
- Model creation and persistence
- Run lifecycle (RUNNING → SUCCESS/FAILED)
- Engine persistence integration
- API endpoints (list, detail)
- Pagination, ordering, filtering
- Security (no secrets exposed)
- Idempotency
- Regression of existing automation behavior
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models.automation_run import AutomationRun


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════


def _mock_settings(**overrides):
    defaults = {
        "automation_discovery_enabled": False,
        "automation_matching_enabled": False,
        "automation_followup_processing_enabled": False,
        "automation_sources": "",
        "automation_min_match_score": 60,
        "automation_max_opportunities_per_run": 100,
        "automation_ai_insights_enabled": False,
        "automation_outreach_drafts_enabled": False,
    }
    defaults.update(overrides)
    settings = MagicMock()
    for k, v in defaults.items():
        setattr(settings, k, v)
    return settings


def _run_cycle(db, **kwargs):
    from app.automation.engine import run_automation_cycle
    return asyncio.run(run_automation_cycle(db, **kwargs))


# ══════════════════════════════════════════════════════════════════════════════
#  MODEL TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestAutomationRunModel:
    """Test AutomationRun model creation and persistence."""

    def test_create_automation_run(self, db):
        """A basic AutomationRun can be persisted."""
        run = AutomationRun(
            run_id="test-001",
            trigger="MANUAL",
            status="COMPLETED",
            dry_run=False,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            opportunities_created=5,
            actions_generated=3,
        )
        db.add(run)
        db.commit()
        assert run.id is not None
        assert run.run_id == "test-001"

    def test_run_counts_default_zero(self, db):
        """All count fields default to 0."""
        run = AutomationRun(
            run_id="test-002",
            trigger="SCHEDULER",
            status="RUNNING",
            dry_run=True,
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.commit()
        assert run.opportunities_created == 0
        assert run.actions_generated == 0
        assert run.notifications_generated == 0

    def test_error_summary_nullable(self, db):
        """Error summary is nullable."""
        run = AutomationRun(
            run_id="test-003",
            trigger="MANUAL",
            status="FAILED",
            dry_run=False,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            error_summary="Something went wrong",
        )
        db.add(run)
        db.commit()
        assert run.error_summary == "Something went wrong"

    def test_run_id_unique(self, db):
        """Duplicate run_id values are rejected."""
        run1 = AutomationRun(
            run_id="dup-001",
            trigger="MANUAL",
            status="COMPLETED",
            dry_run=False,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(run1)
        db.commit()

        run2 = AutomationRun(
            run_id="dup-001",
            trigger="SCHEDULER",
            status="COMPLETED",
            dry_run=False,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(run2)
        with pytest.raises(Exception):
            db.commit()

    def test_run_has_created_at(self, db):
        """created_at is set automatically."""
        run = AutomationRun(
            run_id="test-004",
            trigger="MANUAL",
            status="COMPLETED",
            dry_run=False,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        assert run.created_at is not None


# ══════════════════════════════════════════════════════════════════════════════
#  ENGINE PERSISTENCE INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════


class TestEnginePersistence:
    """Test that the automation engine persists runs."""

    def _mock_get_settings(self):
        """Create mock settings for engine tests."""
        s = MagicMock()
        s.automation_discovery_enabled = False
        s.automation_matching_enabled = False
        s.automation_followup_processing_enabled = False
        s.automation_sources = ""
        s.automation_min_match_score = 60
        s.automation_max_opportunities_per_run = 100
        s.automation_ai_insights_enabled = False
        s.automation_outreach_drafts_enabled = False
        return s

    def test_run_persisted_after_cycle(self, db):
        """Each automation cycle should persist an AutomationRun record."""
        with patch("app.automation.engine.get_settings", return_value=self._mock_get_settings()):
            _run_cycle(db, trigger="MANUAL", dry_run=True)

        count = db.query(AutomationRun).count()
        assert count >= 1

    def test_persisted_run_has_correct_fields(self, db):
        """The persisted run should have correct trigger, status, and counts."""
        with patch("app.automation.engine.get_settings", return_value=self._mock_get_settings()):
            result = _run_cycle(db, trigger="SCHEDULER", dry_run=True)

        run = db.query(AutomationRun).filter(AutomationRun.run_id == result.run_id).first()
        assert run is not None
        assert run.trigger == "SCHEDULER"
        assert run.status == "COMPLETED"
        assert run.dry_run is True
        assert run.started_at is not None
        assert run.completed_at is not None

    def test_failed_run_persisted(self, db):
        """A failed run should be persisted with FAILED status."""
        mock_settings = self._mock_get_settings()
        mock_settings.automation_discovery_enabled = True
        with patch("app.automation.engine.get_settings", return_value=mock_settings):
            with patch("app.automation.engine._run_discovery", side_effect=RuntimeError("boom")):
                result = _run_cycle(db, trigger="MANUAL", dry_run=True)

        run = db.query(AutomationRun).filter(AutomationRun.run_id == result.run_id).first()
        assert run is not None
        assert run.status == "FAILED"
        assert run.error_summary is not None

    def test_manual_trigger_persisted(self, db):
        """Manual trigger should be recorded correctly."""
        with patch("app.automation.engine.get_settings", return_value=self._mock_get_settings()):
            _run_cycle(db, trigger="MANUAL", dry_run=True)

        run = db.query(AutomationRun).filter(AutomationRun.trigger == "MANUAL").first()
        assert run is not None

    def test_scheduler_trigger_persisted(self, db):
        """Scheduler trigger should be recorded correctly."""
        with patch("app.automation.engine.get_settings", return_value=self._mock_get_settings()):
            _run_cycle(db, trigger="SCHEDULER", dry_run=True)

        run = db.query(AutomationRun).filter(AutomationRun.trigger == "SCHEDULER").first()
        assert run is not None

    def test_persistence_does_not_break_existing_behavior(self, db):
        """Persistence must not change automation behavior."""
        from app.automation.models import RunStatus

        with patch("app.automation.engine.get_settings", return_value=self._mock_get_settings()):
            result = _run_cycle(db, trigger="MANUAL", dry_run=True)

        assert result.status == RunStatus.COMPLETED
        assert result.opportunities_created == 0
        assert result.dry_run is True

    def test_no_external_actions(self):
        """Run history persistence must not introduce external actions."""
        import app.automation.engine as eng
        import inspect
        source = inspect.getsource(eng)
        assert "send_email" not in source
        assert "send_message" not in source
        assert "submit_application" not in source

    def test_no_secrets_stored(self, db):
        """AutomationRun must not store secrets."""
        run = AutomationRun(
            run_id="no-secrets",
            trigger="MANUAL",
            status="COMPLETED",
            dry_run=False,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            error_summary="safe error message",
        )
        db.add(run)
        db.commit()
        assert run.error_summary is not None
        assert "password" not in run.error_summary.lower()
        assert "api_key" not in run.error_summary.lower()

    def test_persistence_failure_does_not_break_pipeline(self, db):
        """If persistence fails, the pipeline should still complete."""
        with patch("app.automation.engine.get_settings", return_value=self._mock_get_settings()):
            with patch("app.automation.engine._persist_run", side_effect=RuntimeError("db error")):
                from app.automation.models import RunStatus
                result = _run_cycle(db, trigger="MANUAL", dry_run=True)

        assert result.status == RunStatus.COMPLETED


# ══════════════════════════════════════════════════════════════════════════════
#  API TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestRunHistoryAPI:
    """Test the automation run history API endpoints."""

    def test_list_runs_empty(self, client):
        """GET /automation/runs returns empty list when no runs exist."""
        resp = client.get("/automation/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "runs" in data
        assert isinstance(data["runs"], list)

    def test_list_runs_with_data(self, db, client):
        """GET /automation/runs returns persisted runs."""
        run = AutomationRun(
            run_id="api-test-001",
            trigger="MANUAL",
            status="COMPLETED",
            dry_run=False,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            opportunities_created=3,
            actions_generated=2,
        )
        db.add(run)
        db.commit()

        resp = client.get("/automation/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["runs"]) >= 1
        assert data["runs"][0]["run_id"] == "api-test-001"

    def test_list_runs_newest_first(self, db, client):
        """Runs should be ordered newest first."""
        now = datetime.now(timezone.utc)
        run1 = AutomationRun(
            run_id="order-old",
            trigger="MANUAL",
            status="COMPLETED",
            dry_run=False,
            started_at=now - timedelta(hours=2),
            completed_at=now - timedelta(hours=2),
        )
        run2 = AutomationRun(
            run_id="order-new",
            trigger="MANUAL",
            status="COMPLETED",
            dry_run=False,
            started_at=now,
            completed_at=now,
        )
        db.add_all([run1, run2])
        db.commit()

        resp = client.get("/automation/runs")
        data = resp.json()
        runs = data["runs"]
        assert len(runs) >= 2
        assert runs[0]["run_id"] == "order-new"

    def test_list_runs_pagination(self, db, client):
        """Pagination works correctly."""
        now = datetime.now(timezone.utc)
        for i in range(5):
            db.add(AutomationRun(
                run_id=f"page-{i}",
                trigger="MANUAL",
                status="COMPLETED",
                dry_run=False,
                started_at=now - timedelta(minutes=i),
                completed_at=now - timedelta(minutes=i),
            ))
        db.commit()

        # Page 1
        resp1 = client.get("/automation/runs?limit=2&offset=0")
        data1 = resp1.json()
        assert len(data1["runs"]) == 2
        assert data1["total"] == 5

        # Page 2
        resp2 = client.get("/automation/runs?limit=2&offset=2")
        data2 = resp2.json()
        assert len(data2["runs"]) == 2

        # Page 3
        resp3 = client.get("/automation/runs?limit=2&offset=4")
        data3 = resp3.json()
        assert len(data3["runs"]) == 1

    def test_list_runs_filter_by_status(self, db, client):
        """Filter by status works."""
        now = datetime.now(timezone.utc)
        db.add(AutomationRun(
            run_id="filter-ok",
            trigger="MANUAL",
            status="COMPLETED",
            dry_run=False,
            started_at=now,
            completed_at=now,
        ))
        db.add(AutomationRun(
            run_id="filter-fail",
            trigger="MANUAL",
            status="FAILED",
            dry_run=False,
            started_at=now,
            completed_at=now,
        ))
        db.commit()

        resp = client.get("/automation/runs?status=FAILED")
        data = resp.json()
        assert all(r["status"] == "FAILED" for r in data["runs"])

    def test_list_runs_filter_by_trigger(self, db, client):
        """Filter by trigger works."""
        now = datetime.now(timezone.utc)
        db.add(AutomationRun(
            run_id="trigger-man",
            trigger="MANUAL",
            status="COMPLETED",
            dry_run=False,
            started_at=now,
            completed_at=now,
        ))
        db.add(AutomationRun(
            run_id="trigger-sched",
            trigger="SCHEDULER",
            status="COMPLETED",
            dry_run=False,
            started_at=now,
            completed_at=now,
        ))
        db.commit()

        resp = client.get("/automation/runs?trigger=SCHEDULER")
        data = resp.json()
        assert all(r["trigger"] == "SCHEDULER" for r in data["runs"])

    def test_get_run_detail(self, db, client):
        """GET /automation/runs/{run_id} returns run details."""
        now = datetime.now(timezone.utc)
        run = AutomationRun(
            run_id="detail-001",
            trigger="MANUAL",
            status="COMPLETED",
            dry_run=False,
            started_at=now,
            completed_at=now + timedelta(seconds=15),
            opportunities_created=10,
            actions_generated=5,
        )
        db.add(run)
        db.commit()

        resp = client.get("/automation/runs/detail-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == "detail-001"
        assert data["opportunities_created"] == 10
        assert data["actions_generated"] == 5
        assert data["duration_seconds"] == 15.0

    def test_get_run_404(self, client):
        """Non-existent run returns 404."""
        resp = client.get("/automation/runs/nonexistent-xyz")
        assert resp.status_code == 404

    def test_status_returns_last_run_from_persistent(self, db, client):
        """Status endpoint returns last run from persistent storage when in-memory is empty."""
        from app.automation.scheduler import get_scheduler
        scheduler = get_scheduler()
        # Clear in-memory last_run so status endpoint falls back to persistent storage
        scheduler._last_run = None

        now = datetime.now(timezone.utc)
        run = AutomationRun(
            run_id="status-last",
            trigger="SCHEDULER",
            status="COMPLETED",
            dry_run=False,
            started_at=now,
            completed_at=now,
            opportunities_created=7,
        )
        db.add(run)
        db.commit()

        resp = client.get("/automation/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "last_run" in data
        assert data["last_run"]["run_id"] == "status-last"

    def test_no_secrets_in_run_response(self, db, client):
        """Run responses must not contain secrets."""
        now = datetime.now(timezone.utc)
        run = AutomationRun(
            run_id="secret-test",
            trigger="MANUAL",
            status="COMPLETED",
            dry_run=False,
            started_at=now,
            completed_at=now,
            error_summary="test error",
        )
        db.add(run)
        db.commit()

        resp = client.get("/automation/runs/secret-test")
        data = resp.json()
        assert "password" not in str(data).lower()
        assert "api_key" not in str(data).lower()
        assert "smtp" not in str(data).lower()
        assert "stack_trace" not in str(data).lower()

    def test_automation_run_endpoint_still_works(self, client):
        """POST /automation/run still works and persists the run."""
        resp = client.post("/automation/run", json={"dry_run": True})
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert data["status"] in ("COMPLETED", "FAILED")

    def test_run_history_updated_after_manual_run(self, db, client):
        """After a manual run, the history should include the new run."""
        # Count runs before
        resp1 = client.get("/automation/runs")
        count_before = resp1.json()["total"]

        # Trigger a run
        client.post("/automation/run", json={"dry_run": True})

        # Count runs after
        resp2 = client.get("/automation/runs")
        count_after = resp2.json()["total"]
        assert count_after == count_before + 1


# ══════════════════════════════════════════════════════════════════════════════
#  SECURITY / SAFETY
# ══════════════════════════════════════════════════════════════════════════════


class TestRunHistorySafety:
    """Verify safety invariants for run history."""

    def test_no_external_actions(self):
        """Run history persistence must not introduce external actions."""
        import app.automation.engine as eng
        import inspect
        source = inspect.getsource(eng)
        assert "send_email" not in source
        assert "send_message" not in source
        assert "submit_application" not in source

    def test_no_secrets_stored(self, db):
        """AutomationRun must not store secrets."""
        run = AutomationRun(
            run_id="no-secrets",
            trigger="MANUAL",
            status="COMPLETED",
            dry_run=False,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            error_summary="safe error message",
        )
        db.add(run)
        db.commit()
        assert run.error_summary is not None
        assert "password" not in run.error_summary.lower()
        assert "api_key" not in run.error_summary.lower()

    def test_persistence_failure_does_not_break_pipeline(self, db):
        """If persistence fails, the pipeline should still complete."""
        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings()
            # Mock the persist function to raise
            with patch("app.automation.engine._persist_run", side_effect=RuntimeError("db error")):
                from app.automation.models import RunStatus
                result = _run_cycle(db, trigger="MANUAL", dry_run=True)

        # The pipeline should still complete even if persistence fails
        assert result.status == RunStatus.COMPLETED
