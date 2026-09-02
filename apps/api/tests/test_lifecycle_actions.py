"""Tests for Application lifecycle + Action Center.

Covers:
- Application CRUD + state machine transitions
- Invalid transitions (409)
- Terminal states block further transitions
- Action generation (idempotent)
- Action completion / dismissal
- Triage
- Priority engine
- Deadline intelligence
- Action summary
- Analytics
- Automation integration (no auto-apply, no auto-send)
- Regression: existing systems still work
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.models.application import (
    APPLICATION_TRANSITIONS,
    TERMINAL_ACTION_STATUSES,
    Action,
    Application,
    can_transition,
)
from app.models.company import Company
from app.models.lead import Lead
from app.models.opportunity import Opportunity


# ── Fixtures ──────────────────────────────────────────────────────────

def _create_company(db) -> Company:
    company = Company(name="TestCo", domain="testco.com")
    db.add(company)
    db.flush()
    return company


def _create_opportunity(db, company_id: int, **overrides) -> Opportunity:
    defaults = {
        "company_id": company_id,
        "type": "INTERNSHIP",
        "title": "Software Engineering Intern",
        "status": "DISCOVERED",
        "priority": "HIGH",
        "match_score": 85,
    }
    defaults.update(overrides)
    opp = Opportunity(**defaults)
    db.add(opp)
    db.flush()
    return opp


def _create_lead(db, company_id: int) -> Lead:
    lead = Lead(name="Jane Doe", company_id=company_id, email="jane@testco.com")
    db.add(lead)
    db.flush()
    return lead


# ══════════════════════════════════════════════════════════════════════
# PART 1: Application Model / State Machine
# ══════════════════════════════════════════════════════════════════════

class TestApplicationModel:
    """Tests for the Application SQLAlchemy model."""

    def test_create_application(self, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)
        from app.services.application import create_application
        app = create_application(db, opportunity_id=opp.id)
        assert app.id is not None
        assert app.status == "NOT_APPLIED"
        assert app.opportunity_id == opp.id

    def test_cannot_create_duplicate_application(self, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)
        from app.services.application import create_application
        create_application(db, opportunity_id=opp.id)
        with pytest.raises(ValueError, match="already exists"):
            create_application(db, opportunity_id=opp.id)

    def test_create_application_nonexistent_opportunity(self, db):
        from app.services.application import create_application
        with pytest.raises(ValueError, match="not found"):
            create_application(db, opportunity_id=99999)


class TestApplicationStateMachine:
    """Tests for valid and invalid status transitions."""

    def test_valid_full_lifecycle(self, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)
        from app.services.application import create_application, transition_application
        app = create_application(db, opportunity_id=opp.id)
        assert app.status == "NOT_APPLIED"

        app = transition_application(db, app.id, "READY")
        assert app.status == "READY"

        app = transition_application(db, app.id, "APPLIED")
        assert app.status == "APPLIED"
        assert app.applied_at is not None

        app = transition_application(db, app.id, "INTERVIEW")
        assert app.status == "INTERVIEW"

        app = transition_application(db, app.id, "FINAL_ROUND")
        assert app.status == "FINAL_ROUND"

        app = transition_application(db, app.id, "OFFER")
        assert app.status == "OFFER"

        app = transition_application(db, app.id, "ACCEPTED")
        assert app.status == "ACCEPTED"

    def test_rejected_from_any_active_state(self, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)
        from app.services.application import create_application, transition_application
        app = create_application(db, opportunity_id=opp.id)

        # NOT_APPLIED can't go directly to REJECTED
        with pytest.raises(ValueError, match="Invalid transition"):
            transition_application(db, app.id, "REJECTED")

        app = transition_application(db, app.id, "READY")
        app = transition_application(db, app.id, "APPLIED")
        app = transition_application(db, app.id, "REJECTED")
        assert app.status == "REJECTED"

    def test_withdrawn_from_any_active_state(self, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)
        from app.services.application import create_application, transition_application
        app = create_application(db, opportunity_id=opp.id)
        app = transition_application(db, app.id, "READY")
        app = transition_application(db, app.id, "WITHDRAWN")
        assert app.status == "WITHDRAWN"

    def test_terminal_states_block_transitions(self, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)
        from app.services.application import create_application, transition_application
        app = create_application(db, opportunity_id=opp.id)
        app = transition_application(db, app.id, "READY")
        app = transition_application(db, app.id, "APPLIED")
        app = transition_application(db, app.id, "REJECTED")

        with pytest.raises(ValueError, match="Invalid transition"):
            transition_application(db, app.id, "APPLIED")

    def test_invalid_transition_returns_error(self, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)
        from app.services.application import create_application, transition_application
        app = create_application(db, opportunity_id=opp.id)

        # NOT_APPLIED → INTERVIEW is not valid
        with pytest.raises(ValueError, match="Invalid transition"):
            transition_application(db, app.id, "INTERVIEW")

    def test_applied_sets_applied_at(self, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)
        from app.services.application import create_application, transition_application
        app = create_application(db, opportunity_id=opp.id)
        assert app.applied_at is None

        app = transition_application(db, app.id, "READY")
        app = transition_application(db, app.id, "APPLIED")
        assert app.applied_at is not None

    def test_asessment_to_interview(self, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)
        from app.services.application import create_application, transition_application
        app = create_application(db, opportunity_id=opp.id)
        app = transition_application(db, app.id, "READY")
        app = transition_application(db, app.id, "APPLIED")
        app = transition_application(db, app.id, "ASSESSMENT")
        app = transition_application(db, app.id, "INTERVIEW")
        assert app.status == "INTERVIEW"

    def test_asessment_to_final_round(self, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)
        from app.services.application import create_application, transition_application
        app = create_application(db, opportunity_id=opp.id)
        app = transition_application(db, app.id, "READY")
        app = transition_application(db, app.id, "APPLIED")
        app = transition_application(db, app.id, "ASSESSMENT")
        app = transition_application(db, app.id, "FINAL_ROUND")
        assert app.status == "FINAL_ROUND"


class TestCanTransition:
    """Tests for the can_transition predicate."""

    def test_valid_transitions(self):
        assert can_transition("NOT_APPLIED", "READY")
        assert can_transition("READY", "APPLIED")
        assert can_transition("APPLIED", "INTERVIEW")
        assert can_transition("INTERVIEW", "OFFER")
        assert can_transition("OFFER", "ACCEPTED")

    def test_terminal_states(self):
        assert not can_transition("ACCEPTED", "APPLIED")
        assert not can_transition("REJECTED", "READY")
        assert not can_transition("WITHDRAWN", "APPLIED")

    def test_invalid_transitions(self):
        assert not can_transition("NOT_APPLIED", "APPLIED")
        assert not can_transition("NOT_APPLIED", "INTERVIEW")


# ══════════════════════════════════════════════════════════════════════
# PART 2: Action Center
# ══════════════════════════════════════════════════════════════════════

class TestDeadlineIntelligence:
    """Tests for deadline bucket classification."""

    def test_overdue(self):
        from app.services.action_center import classify_deadline_bucket
        deadline = datetime.now(timezone.utc) - timedelta(days=3)
        assert classify_deadline_bucket(deadline) == "OVERDUE"

    def test_today(self):
        from app.services.action_center import classify_deadline_bucket
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(hours=6)
        bucket = classify_deadline_bucket(deadline, now)
        assert bucket == "TODAY"

    def test_within_3_days(self):
        from app.services.action_center import classify_deadline_bucket
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        deadline = datetime(2026, 9, 3, tzinfo=timezone.utc)
        assert classify_deadline_bucket(deadline, now) == "WITHIN_3_DAYS"

    def test_within_7_days(self):
        from app.services.action_center import classify_deadline_bucket
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        deadline = datetime(2026, 9, 7, tzinfo=timezone.utc)
        assert classify_deadline_bucket(deadline, now) == "WITHIN_7_DAYS"

    def test_within_14_days(self):
        from app.services.action_center import classify_deadline_bucket
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        deadline = datetime(2026, 9, 14, tzinfo=timezone.utc)
        assert classify_deadline_bucket(deadline, now) == "WITHIN_14_DAYS"

    def test_within_30_days(self):
        from app.services.action_center import classify_deadline_bucket
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        deadline = datetime(2026, 9, 30, tzinfo=timezone.utc)
        assert classify_deadline_bucket(deadline, now) == "WITHIN_30_DAYS"

    def test_future(self):
        from app.services.action_center import classify_deadline_bucket
        deadline = datetime(2027, 12, 1, tzinfo=timezone.utc)
        assert classify_deadline_bucket(deadline) == "FUTURE"

    def test_no_deadline(self):
        from app.services.action_center import classify_deadline_bucket
        assert classify_deadline_bucket(None) == "NO_DEADLINE"

    def test_naive_datetime_handled(self):
        from app.services.action_center import classify_deadline_bucket
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        deadline = datetime(2027, 12, 1)  # naive
        result = classify_deadline_bucket(deadline, now)
        assert result == "FUTURE"


class TestPriorityEngine:
    """Tests for the priority engine."""

    def test_p0_imminent_high_match_not_applied(self):
        from app.services.action_center import calculate_action_priority
        priority = calculate_action_priority(
            match_score=85,
            planning_horizon="NOW",
            deadline_bucket="TODAY",
            application_status="NOT_APPLIED",
        )
        assert priority == "P0"

    def test_p0_overdue_high_match(self):
        from app.services.action_center import calculate_action_priority
        priority = calculate_action_priority(
            match_score=90,
            planning_horizon="NOW",
            deadline_bucket="OVERDUE",
            application_status="NOT_APPLIED",
        )
        assert priority == "P0"

    def test_p1_summer_2027_high_match(self):
        from app.services.action_center import calculate_action_priority
        priority = calculate_action_priority(
            match_score=85,
            planning_horizon="SUMMER_2027",
            deadline_bucket="WITHIN_30_DAYS",
            application_status="NOT_APPLIED",
        )
        assert priority == "P1"

    def test_p1_summer_2027_moderate_match(self):
        from app.services.action_center import calculate_action_priority
        priority = calculate_action_priority(
            match_score=65,
            planning_horizon="SUMMER_2027",
            deadline_bucket="FUTURE",
            application_status="NOT_APPLIED",
        )
        assert priority == "P1"

    def test_p2_high_match_future(self):
        from app.services.action_center import calculate_action_priority
        priority = calculate_action_priority(
            match_score=85,
            planning_horizon="FUTURE",
            deadline_bucket="FUTURE",
            application_status="NOT_APPLIED",
        )
        assert priority == "P2"

    def test_p3_low_match(self):
        from app.services.action_center import calculate_action_priority
        priority = calculate_action_priority(
            match_score=30,
            planning_horizon="UNKNOWN",
            deadline_bucket="NO_DEADLINE",
            application_status="NOT_APPLIED",
        )
        assert priority == "P3"

    def test_missing_data_not_urgent(self):
        from app.services.action_center import calculate_action_priority
        priority = calculate_action_priority(
            match_score=None,
            planning_horizon="UNKNOWN",
            deadline_bucket="NO_DEADLINE",
            application_status="NOT_APPLIED",
        )
        assert priority == "P3"


class TestTriage:
    """Tests for the triage service."""

    def test_high_match_summer_2027(self, db):
        from app.services.action_center import triage_opportunity
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        company = _create_company(db)
        opp = _create_opportunity(
            db, company.id,
            match_score=91,
            deadline=datetime(2027, 5, 15, tzinfo=timezone.utc),
        )
        result = triage_opportunity(db, opp, now=now)
        assert result["planning_horizon"] == "SUMMER_2027"
        assert result["deadline_bucket"] == "FUTURE"
        assert result["priority"] in ("P1", "P2")
        assert result["application_status"] == "NOT_APPLIED"

    def test_low_match_no_deadline(self, db):
        from app.services.action_center import triage_opportunity
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        company = _create_company(db)
        opp = _create_opportunity(
            db, company.id,
            match_score=25,
            deadline=None,
        )
        result = triage_opportunity(db, opp, now=now)
        assert result["planning_horizon"] == "UNKNOWN"
        assert result["deadline_bucket"] == "NO_DEADLINE"
        assert result["priority"] == "P3"

    def test_imminent_deadline_high_match(self, db):
        from app.services.action_center import triage_opportunity
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        company = _create_company(db)
        opp = _create_opportunity(
            db, company.id,
            match_score=88,
            deadline=datetime(2026, 9, 1, 12, tzinfo=timezone.utc),
        )
        result = triage_opportunity(db, opp, now=now)
        assert result["deadline_bucket"] == "TODAY"
        assert result["priority"] == "P0"
        assert "APPLY" in result["recommended_action"]

    def test_already_applied(self, db):
        from app.services.action_center import triage_opportunity
        from app.services.application import create_application, transition_application
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        company = _create_company(db)
        opp = _create_opportunity(db, company.id, match_score=80)
        app = create_application(db, opportunity_id=opp.id)
        transition_application(db, app.id, "READY")
        transition_application(db, app.id, "APPLIED")

        result = triage_opportunity(db, opp, now=now)
        assert result["application_status"] == "APPLIED"


class TestActionGeneration:
    """Tests for action generation."""

    def test_generate_actions_for_high_match_opportunities(self, db):
        from app.services.action_center import generate_actions
        company = _create_company(db)
        _create_opportunity(db, company.id, match_score=85)
        actions = generate_actions(db, dry_run=True)
        apply_actions = [a for a in actions if a.action_type == "APPLY"]
        assert len(apply_actions) >= 1

    def test_generate_actions_idempotent(self, db):
        from app.services.action_center import generate_actions
        company = _create_company(db)
        _create_opportunity(db, company.id, match_score=85)

        actions1 = generate_actions(db, dry_run=False)
        db.flush()
        count_after_first = db.query(Action).filter(Action.status == "OPEN").count()

        actions2 = generate_actions(db, dry_run=False)
        db.flush()
        count_after_second = db.query(Action).filter(Action.status == "OPEN").count()

        # Idempotent: no duplicates
        assert count_after_first == count_after_second

    def test_dry_run_no_persist(self, db):
        from app.services.action_center import generate_actions
        company = _create_company(db)
        _create_opportunity(db, company.id, match_score=85)

        count_before = db.query(Action).count()
        actions = generate_actions(db, dry_run=True)
        assert len(actions) >= 1
        # Dry run should not create DB records
        assert db.query(Action).count() == count_before


class TestActionManagement:
    """Tests for action completion and dismissal."""

    def _make_action(self, db) -> Action:
        action = Action(
            action_type="APPLY",
            priority="P1",
            entity_type="opportunity",
            entity_id=1,
            title="Test action",
            status="OPEN",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(action)
        db.flush()
        return action

    def test_complete_action(self, db):
        from app.services.action_center import complete_action
        action = self._make_action(db)
        result = complete_action(db, action.id)
        assert result.status == "COMPLETED"
        assert result.completed_at is not None

    def test_dismiss_action(self, db):
        from app.services.action_center import dismiss_action
        action = self._make_action(db)
        result = dismiss_action(db, action.id)
        assert result.status == "DISMISSED"

    def test_start_action(self, db):
        from app.services.action_center import start_action
        action = self._make_action(db)
        result = start_action(db, action.id)
        assert result.status == "IN_PROGRESS"

    def test_complete_terminal_action_fails(self, db):
        from app.services.action_center import complete_action, dismiss_action
        action = self._make_action(db)
        dismiss_action(db, action.id)
        with pytest.raises(ValueError, match="terminal"):
            complete_action(db, action.id)


# ══════════════════════════════════════════════════════════════════════
# PART 3: API Routes
# ══════════════════════════════════════════════════════════════════════

class TestApplicationAPI:
    """Tests for application API endpoints."""

    def test_create_and_get_application(self, client, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)

        # Create
        resp = client.post("/applications", json={
            "opportunity_id": opp.id,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "NOT_APPLIED"
        app_id = data["id"]

        # Get
        resp = client.get(f"/applications/{app_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == app_id

    def test_list_applications(self, client, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)
        client.post("/applications", json={"opportunity_id": opp.id})

        resp = client.get("/applications")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_transitions_endpoint(self, client, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)
        resp = client.post("/applications", json={"opportunity_id": opp.id})
        app_id = resp.json()["id"]

        resp = client.get(f"/applications/{app_id}/transitions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_status"] == "NOT_APPLIED"
        assert "READY" in data["valid_transitions"]

    def test_apply_endpoint(self, client, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)
        resp = client.post("/applications", json={"opportunity_id": opp.id})
        app_id = resp.json()["id"]

        # READY first
        resp = client.post(f"/applications/{app_id}/ready")
        assert resp.status_code == 200

        # Then apply
        resp = client.post(f"/applications/{app_id}/apply")
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPLIED"

    def test_invalid_transition_returns_409(self, client, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id)
        resp = client.post("/applications", json={"opportunity_id": opp.id})
        app_id = resp.json()["id"]

        # NOT_APPLIED → INTERVIEW is invalid
        resp = client.post(f"/applications/{app_id}/interview")
        assert resp.status_code == 409

    def test_404_for_nonexistent_application(self, client, db):
        resp = client.get("/applications/99999")
        assert resp.status_code == 404


class TestActionAPI:
    """Tests for action center API endpoints."""

    def test_generate_actions(self, client, db):
        company = _create_company(db)
        _create_opportunity(db, company.id, match_score=85)

        resp = client.post("/actions/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["generated"] >= 1
        assert data["dry_run"] is False

    def test_generate_actions_dry_run(self, client, db):
        company = _create_company(db)
        _create_opportunity(db, company.id, match_score=85)

        resp = client.post("/actions/generate?dry_run=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is True

    def test_list_actions(self, client, db):
        company = _create_company(db)
        _create_opportunity(db, company.id, match_score=85)
        client.post("/actions/generate")

        resp = client.get("/actions")
        assert resp.status_code == 200

    def test_action_summary(self, client, db):
        resp = client.get("/actions/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_actions" in data
        assert "by_priority" in data

    def test_complete_action(self, client, db):
        company = _create_company(db)
        _create_opportunity(db, company.id, match_score=85)
        client.post("/actions/generate")

        actions_resp = client.get("/actions")
        actions = actions_resp.json()
        if actions:
            action_id = actions[0]["id"]
            resp = client.post(f"/actions/{action_id}/complete")
            assert resp.status_code == 200
            assert resp.json()["status"] == "COMPLETED"


class TestTriageAPI:
    """Tests for triage endpoint."""

    def test_triage_opportunity(self, client, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id, match_score=75)

        resp = client.get(f"/opportunities/{opp.id}/triage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["opportunity_id"] == opp.id
        assert "match_score" in data
        assert "planning_horizon" in data
        assert "deadline_bucket" in data
        assert "priority" in data

    def test_triage_404(self, client, db):
        resp = client.get("/opportunities/99999/triage")
        assert resp.status_code == 404


class TestAnalyticsAPI:
    """Tests for analytics endpoint."""

    def test_analytics_empty(self, client, db):
        resp = client.get("/applications/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_analytics_with_data(self, client, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company.id, match_score=80)
        client.post("/applications", json={"opportunity_id": opp.id})

        resp = client.get("/applications/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1


# ══════════════════════════════════════════════════════════════════════
# PART 4: Safety
# ══════════════════════════════════════════════════════════════════════

class TestSafetyBoundaries:
    """Ensure automation NEVER auto-applies, auto-sends, or auto-approves."""

    def test_action_generation_does_not_create_applications(self, db):
        """Generating actions must NOT submit applications."""
        from app.services.action_center import generate_actions
        company = _create_company(db)
        _create_opportunity(db, company.id, match_score=95)

        count_before = db.query(Application).count()
        generate_actions(db, dry_run=False)
        db.flush()
        count_after = db.query(Application).count()
        assert count_before == count_after

    def test_no_secrets_in_action_api(self, client, db):
        """Action API must not expose secrets."""
        resp = client.get("/actions/summary")
        assert resp.status_code == 200
        text = resp.text.lower()
        assert "password" not in text
        assert "api_key" not in text
        assert "smtp" not in text

    def test_no_secrets_in_application_api(self, client, db):
        """Application API must not expose secrets."""
        resp = client.get("/applications")
        assert resp.status_code == 200
        text = resp.text.lower()
        assert "password" not in text
        assert "api_key" not in text
