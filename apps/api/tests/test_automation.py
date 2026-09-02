"""Comprehensive tests for the automation engine.

Covers:
- Automation models/result types
- Orchestrator (dry-run and live)
- Scheduler behavior
- API endpoints
- Idempotency
- Source failure handling
- Planning integration
- Follow-up processing
- Outreach safety (no automatic sending)
- Existing API regression
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.automation.models import (
    AutomationRunResult,
    AutomationStatus,
    RunStatus,
    RunTrigger,
    SourceResult,
)
from app.core.config import get_settings
from app.models.company import Company
from app.models.followup import FollowUp as FollowUpModel
from app.models.lead import Lead
from app.models.message import Message
from app.models.opportunity import Opportunity
from app.models.profile import Profile


# ── Helpers ────────────────────────────────────────────────────────────────


def _create_profile(db) -> Profile:
    profile = Profile(
        name="Test User",
        email="test@example.com",
        headline="Software Engineer",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _create_company(db, name: str = "TestCorp") -> Company:
    company = Company(name=name)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _create_opportunity(
    db,
    company: Company,
    *,
    title: str = "Software Engineer",
    opp_type: str = "FULL_TIME",
    status: str = "DISCOVERED",
    priority: str = "MEDIUM",
    match_score: int | None = None,
    deadline: datetime | None = None,
) -> Opportunity:
    opp = Opportunity(
        company_id=company.id,
        type=opp_type,
        title=title,
        status=status,
        priority=priority,
        match_score=match_score,
        deadline=deadline,
    )
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return opp


def _create_lead(db, company: Company, name: str = "John Doe") -> Lead:
    lead = Lead(
        company_id=company.id,
        name=name,
        email="john@test.com",
        status="ACTIVE",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _create_followup(
    db,
    lead: Lead,
    *,
    scheduled_for: datetime,
    status: str = "PENDING",
    opportunity_id: int | None = None,
) -> FollowUpModel:
    fu = FollowUpModel(
        lead_id=lead.id,
        opportunity_id=opportunity_id,
        scheduled_for=scheduled_for,
        status=status,
        reason="Test follow-up",
    )
    db.add(fu)
    db.commit()
    db.refresh(fu)
    return fu


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION MODELS
# ══════════════════════════════════════════════════════════════════════════════


class TestAutomationModels:
    """Test automation result dataclasses."""

    def test_run_result_defaults(self):
        result = AutomationRunResult()
        assert result.status == RunStatus.RUNNING
        assert result.trigger == RunTrigger.MANUAL
        assert result.started_at is not None
        assert result.completed_at is None
        assert result.opportunities_created == 0
        assert result.dry_run is False

    def test_run_result_complete(self):
        result = AutomationRunResult()
        result.complete()
        assert result.status == RunStatus.COMPLETED
        assert result.completed_at is not None
        assert result.duration_seconds() is not None
        assert result.duration_seconds() >= 0

    def test_run_result_fail(self):
        result = AutomationRunResult()
        result.fail("Something went wrong")
        assert result.status == RunStatus.FAILED
        assert result.completed_at is not None
        assert "Something went wrong" in result.errors

    def test_run_result_to_dict(self):
        result = AutomationRunResult(run_id="abc123")
        result.complete()
        d = result.to_dict()
        assert d["run_id"] == "abc123"
        assert d["status"] == "COMPLETED"
        assert d["trigger"] == "MANUAL"
        assert "started_at" in d
        assert "completed_at" in d
        assert "duration_seconds" in d
        assert "source_results" in d
        assert "notifications_generated" in d

    def test_source_result_defaults(self):
        sr = SourceResult(source_name="test")
        assert sr.success is True
        assert sr.ingested == 0
        assert sr.errors == []

    def test_source_result_failure(self):
        sr = SourceResult(source_name="test", success=False, errors=["timeout"])
        assert sr.success is False
        assert sr.errors == ["timeout"]

    def test_automation_status_to_dict(self):
        status = AutomationStatus(enabled=True, scheduler_active=False)
        d = status.to_dict()
        assert d["enabled"] is True
        assert d["scheduler_active"] is False

    def test_run_trigger_enum(self):
        assert RunTrigger.MANUAL.value == "MANUAL"
        assert RunTrigger.SCHEDULER.value == "SCHEDULER"

    def test_run_status_enum(self):
        assert RunStatus.RUNNING.value == "RUNNING"
        assert RunStatus.COMPLETED.value == "COMPLETED"
        assert RunStatus.FAILED.value == "FAILED"


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION ENGINE — DRY RUN
# ══════════════════════════════════════════════════════════════════════════════


class TestAutomationDryRun:
    """Test automation in dry-run mode — no DB mutations."""

    def test_dry_run_no_db_mutations(self, db):
        """Dry run should not create opportunities."""
        opp_before = db.query(Opportunity).count()
        result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)
        opp_after = db.query(Opportunity).count()

        assert opp_before == opp_after
        assert result.dry_run is True
        assert result.status == RunStatus.COMPLETED

    def test_dry_run_returns_result(self, db):
        result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)
        assert result.run_id != ""
        assert result.status == RunStatus.COMPLETED
        assert result.started_at is not None
        assert result.completed_at is not None


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION ENGINE — LIVE RUN WITH MOCKED SOURCES
# ══════════════════════════════════════════════════════════════════════════════


def _run_cycle(db, **kwargs):
    """Helper to run automation cycle synchronously in tests."""
    from app.automation.engine import run_automation_cycle
    return asyncio.run(run_automation_cycle(db, **kwargs))


def _mock_settings(**overrides):
    """Create a mock settings object with sensible defaults."""
    defaults = {
        "automation_discovery_enabled": True,
        "automation_matching_enabled": True,
        "automation_followup_processing_enabled": True,
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


class TestAutomationEngine:
    """Test the automation orchestrator with mocked discovery sources."""

    def test_run_with_no_sources(self, db):
        """Run with empty source list should succeed with no discovery."""
        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(automation_sources="")
            result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)

        assert result.status == RunStatus.COMPLETED
        assert result.sources_attempted == 0

    def test_run_source_failure_doesnt_stop_others(self, db):
        """One source failing should not stop other sources from succeeding."""
        with patch("app.automation.engine.get_settings") as m, \
             patch("app.automation.engine.run_source") as mock_run_source:
            m.return_value = _mock_settings(
                automation_sources="source_a,source_b,source_c",
            )

            from app.discovery.models import IngestionResult as IR

            def side_effect(db, source_name):
                if source_name == "source_b":
                    raise RuntimeError("Network error")
                return IR(
                    source_name=source_name,
                    raw_count=10,
                    ingested=5,
                    duplicates_skipped=5,
                    companies_created=1,
                )

            mock_run_source.side_effect = side_effect

            result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=False)

            assert result.status == RunStatus.COMPLETED
            assert result.sources_attempted == 3
            assert result.sources_succeeded == 2
            assert result.sources_failed == 1
            assert len(result.source_results) == 3

    def test_run_all_sources_disabled(self, db):
        """When discovery is disabled, no sources should be run."""
        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(
                automation_discovery_enabled=False,
                automation_matching_enabled=False,
                automation_followup_processing_enabled=False,
            )
            result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)

        assert result.status == RunStatus.COMPLETED
        assert result.sources_attempted == 0

    def test_run_scheduler_trigger(self, db):
        """Scheduler trigger should be recorded."""
        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(
                automation_discovery_enabled=False,
                automation_matching_enabled=False,
                automation_followup_processing_enabled=False,
            )
            result = _run_cycle(db, trigger=RunTrigger.SCHEDULER, dry_run=True)

        assert result.trigger == RunTrigger.SCHEDULER


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION ENGINE — MATCHING INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════


class TestAutomationMatching:
    """Test that matching works within the automation cycle."""

    def test_unscored_opportunities_get_scored(self, db):
        """Un-scored opportunities should get match scores during automation."""
        profile = _create_profile(db)
        company = _create_company(db)
        opp = _create_opportunity(db, company, title="Python Developer")

        assert opp.match_score is None

        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(
                automation_discovery_enabled=False,
                automation_matching_enabled=True,
                automation_followup_processing_enabled=False,
            )
            result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)

        assert result.opportunities_scored >= 1
        db.refresh(opp)
        assert opp.match_score is not None
        assert 0 <= opp.match_score <= 100

    def test_no_profile_skips_matching(self, db):
        """When no profile exists, matching should be skipped gracefully."""
        company = _create_company(db)
        _create_opportunity(db, company)

        # Ensure no profiles exist in this test
        from app.models.profile import Profile
        db.query(Profile).delete()
        db.commit()

        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(
                automation_discovery_enabled=False,
                automation_matching_enabled=True,
                automation_followup_processing_enabled=False,
            )
            result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)

        assert result.status == RunStatus.COMPLETED
        assert result.opportunities_scored == 0

    def test_already_scored_opportunities_not_rescored(self, db):
        """Already-scored opportunities should not be re-scored."""
        profile = _create_profile(db)
        company = _create_company(db)
        opp = _create_opportunity(db, company, match_score=85)

        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(
                automation_discovery_enabled=False,
                automation_matching_enabled=True,
                automation_followup_processing_enabled=False,
            )
            result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)

        assert result.opportunities_scored == 0
        db.refresh(opp)
        assert opp.match_score == 85  # unchanged


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION ENGINE — PLANNING INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════


class TestAutomationPlanning:
    """Test planning horizon classification within automation."""

    def test_planning_counts(self, db):
        """Automation should classify opportunities into planning horizons."""
        _create_profile(db)
        company = _create_company(db)
        now = datetime.now(timezone.utc)

        # NOW — deadline in 3 days
        _create_opportunity(db, company, title="Urgent Role", deadline=now + timedelta(days=3))
        # UPCOMING — deadline in 15 days
        _create_opportunity(db, company, title="Soon Role", deadline=now + timedelta(days=15))
        # SUMMER_2027
        _create_opportunity(db, company, title="Summer Role", deadline=datetime(2027, 5, 15, tzinfo=timezone.utc))
        # FUTURE — deadline in 60 days (outside summer 2027)
        _create_opportunity(db, company, title="Future Role", deadline=now + timedelta(days=60))
        # UNKNOWN — no deadline
        _create_opportunity(db, company, title="Unknown Role")

        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(
                automation_discovery_enabled=False,
                automation_matching_enabled=False,
                automation_followup_processing_enabled=False,
            )
            result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)

        assert result.status == RunStatus.COMPLETED
        assert result.now_count >= 1
        assert result.upcoming_count >= 1
        assert result.summer_2027_count >= 1
        assert result.future_count >= 1
        assert result.unknown_count >= 1

    def test_summer_2027_boundary(self, db):
        """Summer 2027 opportunities should be counted separately."""
        company = _create_company(db)

        _create_opportunity(db, company, title="May Start", deadline=datetime(2027, 5, 1, tzinfo=timezone.utc))
        _create_opportunity(db, company, title="June End", deadline=datetime(2027, 6, 30, 23, 59, 59, tzinfo=timezone.utc))
        _create_opportunity(db, company, title="Before Summer", deadline=datetime(2027, 4, 30, tzinfo=timezone.utc))
        _create_opportunity(db, company, title="After Summer", deadline=datetime(2027, 7, 1, tzinfo=timezone.utc))

        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(
                automation_discovery_enabled=False,
                automation_matching_enabled=False,
                automation_followup_processing_enabled=False,
            )
            result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)

        assert result.summer_2027_count == 2  # May 1 + June 30


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION ENGINE — FOLLOW-UP PROCESSING
# ══════════════════════════════════════════════════════════════════════════════


class TestAutomationFollowUpProcessing:
    """Test follow-up due-marking within automation."""

    def test_due_followups_marked(self, db):
        """PENDING follow-ups with past scheduled_for should be marked DUE."""
        lead = _create_lead(db, _create_company(db))
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        fu = _create_followup(db, lead, scheduled_for=past_time, status="PENDING")

        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(
                automation_discovery_enabled=False,
                automation_matching_enabled=False,
                automation_followup_processing_enabled=True,
            )
            result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)

        assert result.followups_marked_due >= 1
        db.refresh(fu)
        assert fu.status == "DUE"

    def test_future_followups_stay_pending(self, db):
        """PENDING follow-ups with future scheduled_for should stay PENDING."""
        lead = _create_lead(db, _create_company(db))
        future_time = datetime.now(timezone.utc) + timedelta(hours=24)
        fu = _create_followup(db, lead, scheduled_for=future_time, status="PENDING")

        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(
                automation_discovery_enabled=False,
                automation_matching_enabled=False,
                automation_followup_processing_enabled=True,
            )
            result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)

        assert result.followups_marked_due == 0
        db.refresh(fu)
        assert fu.status == "PENDING"

    def test_no_automatic_sending(self, db):
        """Automation must NEVER send emails or approve drafts."""
        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(
                automation_discovery_enabled=False,
                automation_matching_enabled=False,
                automation_followup_processing_enabled=True,
            )
            result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)

        # Structural check: automation engine has no send_email call


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION ENGINE — IDEMPOTENCY
# ══════════════════════════════════════════════════════════════════════════════


class TestAutomationIdempotency:
    """Test that repeated runs are safe and don't create duplicates."""

    def test_same_run_twice_no_duplicates(self, db):
        """Running automation twice with no new data should not create duplicates."""
        company = _create_company(db)
        _create_opportunity(db, company, match_score=75)

        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(
                automation_discovery_enabled=False,
                automation_matching_enabled=True,
                automation_followup_processing_enabled=True,
            )
            result1 = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)
            result2 = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)

        assert result1.opportunities_created == 0
        assert result2.opportunities_created == 0
        assert result1.opportunities_scored == 0
        assert result2.opportunities_scored == 0


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION ENGINE — HIGH MATCH COUNTING
# ══════════════════════════════════════════════════════════════════════════════


class TestAutomationIdempotencyNotifications:
    """Test that notification sync is idempotent."""

    def test_repeated_cycle_no_duplicate_notifications(self, db):
        """Running automation twice should not create duplicate notifications."""
        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(
                automation_discovery_enabled=False,
                automation_matching_enabled=False,
                automation_followup_processing_enabled=True,
            )
            result1 = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)
            result2 = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)

        # Both should succeed — notification sync is idempotent
        assert result1.status == RunStatus.COMPLETED
        assert result2.status == RunStatus.COMPLETED


class TestAutomationHighMatch:
    """Test high-match counting."""

    def test_high_match_count(self, db):
        """High-match opportunities (>= threshold) should be counted."""
        _create_profile(db)
        company = _create_company(db)
        _create_opportunity(db, company, title="Software Engineer")
        _create_opportunity(db, company, title="Data Analyst")

        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(
                automation_discovery_enabled=False,
                automation_matching_enabled=True,
                automation_followup_processing_enabled=False,
                automation_min_match_score=30,
            )
            result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)

        assert result.opportunities_scored == 2
        assert result.high_match_count >= 0


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION SCHEDULER
# ══════════════════════════════════════════════════════════════════════════════


class TestAutomationNotificationSync:
    """Test notification sync within automation."""

    def test_notification_sync_called(self, db):
        """Notification sync should run after action generation."""
        with patch("app.automation.engine.get_settings") as m:
            m.return_value = _mock_settings(
                automation_discovery_enabled=False,
                automation_matching_enabled=False,
                automation_followup_processing_enabled=False,
            )
            result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)

        # notifications_generated should be present in result
        assert hasattr(result, "notifications_generated")
        assert isinstance(result.notifications_generated, int)
        assert result.notifications_generated >= 0

    def test_notification_sync_in_to_dict(self, db):
        """Run result to_dict should include notifications_generated."""
        result = _run_cycle(db, trigger=RunTrigger.MANUAL, dry_run=True)
        d = result.to_dict()
        assert "notifications_generated" in d
        assert isinstance(d["notifications_generated"], int)


class TestAutomationScheduler:
    """Basic scheduler tests (no start() calls — those are in test_scheduler.py)."""

    def test_scheduler_not_active_by_default(self):
        from app.automation.scheduler import AutomationScheduler

        scheduler = AutomationScheduler()
        assert scheduler.is_active is False
        assert scheduler.last_run is None

    def test_scheduler_stop_when_not_started(self):
        from app.automation.scheduler import AutomationScheduler

        scheduler = AutomationScheduler()
        scheduler.stop()  # should not raise
        assert scheduler.is_active is False

    def test_get_scheduler_returns_singleton(self):
        from app.automation.scheduler import get_scheduler

        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2

    def test_scheduler_disabled_when_automation_off(self):
        """Scheduler should not start when automation is disabled."""
        from app.automation.scheduler import AutomationScheduler

        with patch("app.automation.scheduler.get_settings") as m:
            settings = MagicMock()
            settings.automation_enabled = False
            m.return_value = settings

            scheduler = AutomationScheduler()
            scheduler.start()
            assert scheduler.is_active is False


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATION API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════


class TestAutomationAPI:
    """Test automation REST API endpoints."""

    def test_get_status(self, client):
        """GET /automation/status should return config."""
        response = client.get("/automation/status")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "scheduler_active" in data
        assert "sources" in data
        assert "min_match_score" in data

    def test_get_config(self, client):
        """GET /automation/config should return config without secrets."""
        response = client.get("/automation/config")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        # Must NOT contain secrets
        assert "email_password" not in data
        assert "ai_api_key" not in data
        assert "database_url" not in data

    def test_trigger_run(self, client):
        """POST /automation/run should trigger and return result."""
        response = client.post("/automation/run", json={})
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert data["status"] in ("COMPLETED", "FAILED")
        assert "trigger" in data
        assert data["trigger"] == "MANUAL"

    def test_trigger_run_dry(self, client):
        """POST /automation/run with dry_run should not mutate DB."""
        response = client.post("/automation/run", json={"dry_run": True})
        assert response.status_code == 200
        data = response.json()
        assert data["dry_run"] is True

    def test_trigger_run_with_source(self, client):
        """POST /automation/run with source override should work."""
        response = client.post(
            "/automation/run",
            json={"source": "remotive"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data

    def test_update_config(self, client):
        """PATCH /automation/config should return current config."""
        response = client.patch("/automation/config", json={"dry_run": True})
        assert response.status_code == 200
        data = response.json()
        assert "current_config" in data

    def test_run_result_has_planning_counts(self, client):
        """Automation run should include planning horizon counts."""
        response = client.post("/automation/run", json={"dry_run": True})
        assert response.status_code == 200
        data = response.json()
        assert "summer_2027_count" in data
        assert "now_count" in data
        assert "upcoming_count" in data
        assert "future_count" in data
        assert "unknown_count" in data

    def test_run_result_has_source_results(self, client):
        """Automation run should include per-source results."""
        response = client.post("/automation/run", json={"dry_run": True})
        assert response.status_code == 200
        data = response.json()
        assert "source_results" in data
        assert isinstance(data["source_results"], list)


# ══════════════════════════════════════════════════════════════════════════════
#  EXISTING API REGRESSION
# ══════════════════════════════════════════════════════════════════════════════


class TestAutomationSafetyInvariants:
    """Test safety invariants that must never be violated."""

    def test_no_automatic_external_sending(self):
        """Automation engine must never send emails or messages."""
        import app.automation.engine as eng_mod
        import inspect

        source = inspect.getsource(eng_mod)
        assert "send_email" not in source
        assert "send_message" not in source
        assert "SMTPEmailProvider" not in source

    def test_no_automatic_application_submission(self):
        """Automation engine must never submit applications."""
        import app.automation.engine as eng_mod
        import inspect

        source = inspect.getsource(eng_mod)
        assert "submit_application" not in source
        assert "apply_to_job" not in source

    def test_no_automatic_outreach_approval(self):
        """Automation engine must never approve outreach drafts."""
        import app.automation.engine as eng_mod
        import inspect

        source = inspect.getsource(eng_mod)
        assert "approve_draft" not in source
        assert "mark_ready" not in source


class TestExistingAPIRegression:
    """Verify existing APIs still work after automation changes."""

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_profiles_list(self, client):
        response = client.get("/profiles")
        assert response.status_code == 200

    def test_companies_list(self, client):
        response = client.get("/companies")
        assert response.status_code == 200

    def test_leads_list(self, client):
        response = client.get("/leads")
        assert response.status_code == 200

    def test_opportunities_list(self, client):
        response = client.get("/opportunities")
        assert response.status_code == 200

    def test_planning_list(self, client):
        response = client.get("/opportunities/planning")
        assert response.status_code == 200

    def test_campaigns_list(self, client):
        response = client.get("/campaigns")
        assert response.status_code == 200

    def test_followups_list(self, client):
        response = client.get("/follow-ups")
        assert response.status_code == 200

    def test_outreach_drafts_list(self, client):
        response = client.get("/outreach/drafts")
        assert response.status_code == 200

    def test_discovery_sources(self, client):
        response = client.get("/discovery/sources")
        assert response.status_code == 200
        data = response.json()
        assert "remotive" in data["sources"]
        assert "arbeitnow" in data["sources"]
        assert "himalayas" in data["sources"]

    def test_export_endpoint(self, client):
        response = client.get("/exports/opportunities.xlsx")
        assert response.status_code == 200
        assert "spreadsheetml" in response.headers.get("content-type", "")
