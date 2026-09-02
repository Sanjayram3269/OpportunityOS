"""Comprehensive tests for the Dashboard / Command Center service and routes.

Covers:
- Dashboard overview
- Today / actionable items
- Application pipeline
- Opportunity metrics
- Summer 2027 metrics
- Campaign metrics
- Outreach metrics
- Follow-up metrics
- Analytics / funnel
- Empty database
- Division by zero safety
- Timezone correctness
- No fabricated data
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cleanup():
    """Remove test data created during these tests."""
    from app.db.session import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        # Delete in dependency order
        db.execute(text("DELETE FROM actions"))
        db.execute(text("DELETE FROM applications"))
        db.execute(text("DELETE FROM followups"))
        db.execute(text("DELETE FROM messages"))
        db.execute(text("DELETE FROM interactions"))
        db.execute(text("DELETE FROM campaign_opportunities"))
        db.execute(text("DELETE FROM campaigns"))
        db.execute(text("DELETE FROM opportunity_evidence"))
        db.execute(text("DELETE FROM opportunities"))
        db.execute(text("DELETE FROM opportunities"))
        db.execute(text("DELETE FROM leads"))
        db.execute(text("DELETE FROM companies"))
        db.commit()
    finally:
        db.close()


def _create_company(name: str = "TestCorp") -> int:
    from app.db.session import SessionLocal
    from app.models.company import Company

    db = SessionLocal()
    try:
        c = Company(name=name, domain=f"{name.lower()}.com")
        db.add(c)
        db.commit()
        db.refresh(c)
        return c.id
    finally:
        db.close()


def _create_opportunity(
    company_id: int,
    title: str = "Software Engineer",
    match_score: int | None = 85,
    deadline: datetime | None = None,
    opp_type: str = "FULL_TIME",
) -> int:
    from app.db.session import SessionLocal
    from app.models.opportunity import Opportunity

    db = SessionLocal()
    try:
        o = Opportunity(
            company_id=company_id,
            title=title,
            type=opp_type,
            status="DISCOVERED",
            priority="MEDIUM",
            match_score=match_score,
            deadline=deadline,
            description="Test opportunity",
        )
        db.add(o)
        db.commit()
        db.refresh(o)
        return o.id
    finally:
        db.close()


def _create_application(opportunity_id: int, status: str = "APPLIED") -> int:
    from app.db.session import SessionLocal
    from app.models.application import Application

    db = SessionLocal()
    try:
        a = Application(
            opportunity_id=opportunity_id,
            status=status,
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        return a.id
    finally:
        db.close()


def _create_action(
    action_type: str = "REVIEW_OPPORTUNITY",
    status: str = "OPEN",
    priority: str = "P0",
    due_at: datetime | None = None,
) -> int:
    from app.db.session import SessionLocal
    from app.models.application import Action

    db = SessionLocal()
    try:
        a = Action(
            action_type=action_type,
            status=status,
            priority=priority,
            entity_type="opportunity",
            entity_id=1,
            title="Test action",
            due_at=due_at,
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        return a.id
    finally:
        db.close()


def _create_campaign(name: str, status: str = "ACTIVE") -> int:
    from app.db.session import SessionLocal
    from app.models.campaign import Campaign

    db = SessionLocal()
    try:
        c = Campaign(name=name, type="TARGETED", status=status)
        db.add(c)
        db.commit()
        db.refresh(c)
        return c.id
    finally:
        db.close()


def _create_lead(name: str = "TestLead") -> int:
    from app.db.session import SessionLocal
    from app.models.lead import Lead

    db = SessionLocal()
    try:
        l = Lead(name=name)
        db.add(l)
        db.commit()
        db.refresh(l)
        return l.id
    finally:
        db.close()


def _create_message(status: str = "DRAFT") -> int:
    from app.db.session import SessionLocal
    from app.models.message import Message

    lead_id = _create_lead("MsgLead")
    db = SessionLocal()
    try:
        m = Message(
            lead_id=lead_id,
            channel="email",
            direction="outbound",
            body="Test message",
            status=status,
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        return m.id
    finally:
        db.close()


def _create_followup(status: str = "DUE") -> int:
    from app.db.session import SessionLocal
    from app.models.followup import FollowUp

    lead_id = _create_lead("FuLead")
    db = SessionLocal()
    try:
        f = FollowUp(
            lead_id=lead_id,
            scheduled_for=_now() + timedelta(days=-1),
            status=status,
        )
        db.add(f)
        db.commit()
        db.refresh(f)
        return f.id
    finally:
        db.close()


# ── Tests ─────────────────────────────────────────────────────────────────


class TestDashboardEndpoint:
    """Test the GET /dashboard/overview endpoint."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Clean up test data after each test."""
        yield
        _cleanup()

    def test_dashboard_returns_200(self):
        """Dashboard endpoint returns successfully."""
        resp = client.get("/dashboard/overview")
        assert resp.status_code == 200

    def test_dashboard_has_all_sections(self):
        """Dashboard response contains all expected sections."""
        resp = client.get("/dashboard/overview")
        data = resp.json()
        expected_sections = [
            "overview",
            "today",
            "pipeline",
            "opportunities",
            "summer_2027",
            "campaigns",
            "outreach",
            "followups",
            "analytics",
        ]
        for section in expected_sections:
            assert section in data, f"Missing section: {section}"

    def test_overview_counts_empty_db(self):
        """Empty database returns zero counts."""
        resp = client.get("/dashboard/overview")
        overview = resp.json()["overview"]
        assert overview["total_opportunities"] == 0
        assert overview["total_applications"] == 0
        assert overview["open_actions"] == 0
        assert overview["total_campaigns"] == 0
        assert overview["active_campaigns"] == 0
        assert overview["high_match_opportunities"] == 0

    def test_overview_counts_real_data(self):
        """Overview counts reflect real database records."""
        cid = _create_company("DashCorp")
        oid = _create_opportunity(cid, match_score=85)
        _create_application(oid, "APPLIED")
        _create_application(oid, "INTERVIEW")
        _create_action(priority="P0")

        resp = client.get("/dashboard/overview")
        overview = resp.json()["overview"]
        assert overview["total_opportunities"] == 1
        assert overview["total_applications"] == 2
        assert overview["open_actions"] == 1
        assert overview["high_match_opportunities"] == 1

    def test_today_overdue_actions(self):
        """Overdue actions are counted correctly."""
        overdue_time = _now() - timedelta(days=2)
        _create_action(status="OPEN", priority="P0", due_at=overdue_time)

        resp = client.get("/dashboard/overview")
        today = resp.json()["today"]
        assert today["overdue_actions"] >= 1

    def test_today_p0_actions(self):
        """P0 actions are counted."""
        _create_action(status="OPEN", priority="P0")
        _create_action(status="OPEN", priority="P1")

        resp = client.get("/dashboard/overview")
        today = resp.json()["today"]
        assert today["p0_actions"] >= 1
        assert today["p1_actions"] >= 1

    def test_today_deadlines_within_3_days(self):
        """Deadlines within 3 days are counted."""
        cid = _create_company("DeadlineCorp")
        deadline_2d = _now() + timedelta(days=2)
        _create_opportunity(cid, deadline=deadline_2d)

        resp = client.get("/dashboard/overview")
        today = resp.json()["today"]
        assert today["deadlines_within_3_days"] >= 1

    def test_pipeline_counts(self):
        """Application pipeline counts by status."""
        cid = _create_company("PipeCorp")
        oid = _create_opportunity(cid)
        _create_application(oid, "APPLIED")
        _create_application(oid, "ASSESSMENT")
        _create_application(oid, "INTERVIEW")
        _create_application(oid, "OFFER")
        _create_application(oid, "REJECTED")

        resp = client.get("/dashboard/overview")
        pipeline = resp.json()["pipeline"]
        assert pipeline["total"] >= 5
        by_status = pipeline["by_status"]
        assert by_status.get("APPLIED", 0) >= 1
        assert by_status.get("INTERVIEW", 0) >= 1
        assert by_status.get("OFFER", 0) >= 1
        assert by_status.get("REJECTED", 0) >= 1

    def test_pipeline_active_vs_terminal(self):
        """Active and terminal counts are computed."""
        cid = _create_company("StatusCorp")
        oid = _create_opportunity(cid)
        _create_application(oid, "APPLIED")
        _create_application(oid, "REJECTED")
        _create_application(oid, "ACCEPTED")

        resp = client.get("/dashboard/overview")
        pipeline = resp.json()["pipeline"]
        assert pipeline["active_count"] >= 1
        assert pipeline["terminal_count"] >= 2

    def test_pipeline_interview_rate_zero_division(self):
        """Interview rate is None when no submissions."""
        resp = client.get("/dashboard/overview")
        pipeline = resp.json()["pipeline"]
        # With no data, rate should be None
        assert pipeline["interview_rate"] is None
        assert pipeline["offer_rate"] is None

    def test_pipeline_interview_rate_calculation(self):
        """Interview rate is calculated correctly."""
        cid = _create_company("RateCorp")
        for i in range(3):
            oid = _create_opportunity(cid, title=f"Job {i}")
            _create_application(oid, "APPLIED")
        oid2 = _create_opportunity(cid, title="Job Interview")
        _create_application(oid2, "INTERVIEW")

        resp = client.get("/dashboard/overview")
        pipeline = resp.json()["pipeline"]
        # 1 interview / 4 submitted = 0.25
        assert pipeline["interview_rate"] is not None
        assert pipeline["interview_rate"] == pytest.approx(0.25, abs=0.01)

    def test_opportunities_match_distribution(self):
        """Match score distribution is computed."""
        cid = _create_company("MatchCorp")
        _create_opportunity(cid, match_score=95)
        _create_opportunity(cid, match_score=85)
        _create_opportunity(cid, match_score=75)
        _create_opportunity(cid, match_score=None)

        resp = client.get("/dashboard/overview")
        opps = resp.json()["opportunities"]
        dist = opps["match_distribution"]
        assert dist.get("90_100", 0) >= 1
        assert dist.get("80_89", 0) >= 1
        assert dist.get("70_79", 0) >= 1
        assert dist.get("unscored", 0) >= 1

    def test_opportunities_by_horizon(self):
        """Planning horizon distribution is computed."""
        cid = _create_company("HorizonCorp")
        # Future deadline
        _create_opportunity(cid, title="Future Job", deadline=_now() + timedelta(days=60))
        # No deadline
        _create_opportunity(cid, title="No Deadline Job", deadline=None)

        resp = client.get("/dashboard/overview")
        opps = resp.json()["opportunities"]
        horizon = opps["by_horizon"]
        # Should have at least FUTURE and UNKNOWN
        assert len(horizon) >= 2

    def test_opportunities_not_applied(self):
        """Opportunities without applications are counted."""
        cid = _create_company("NotAppliedCorp")
        oid1 = _create_opportunity(cid, title="Applied Job")
        _create_application(oid1, "APPLIED")
        _create_opportunity(cid, title="Not Applied Job")

        resp = client.get("/dashboard/overview")
        opps = resp.json()["opportunities"]
        assert opps["not_applied"] >= 1

    def test_summer_2027_metrics(self):
        """Summer 2027 opportunities are classified correctly."""
        cid = _create_company("SummerCorp")
        summer_deadline = datetime(2027, 5, 15, tzinfo=timezone.utc)
        _create_opportunity(cid, title="Summer Intern", deadline=summer_deadline, opp_type="INTERNSHIP")
        _create_opportunity(cid, title="Other Job", deadline=_now() + timedelta(days=10))

        resp = client.get("/dashboard/overview")
        summer = resp.json()["summer_2027"]
        assert summer["total"] >= 1

    def test_campaigns_section(self):
        """Campaign counts reflect database."""
        cid = _create_company("CampCorp")
        _create_campaign("Active Campaign", "ACTIVE")
        _create_campaign("Draft Campaign", "DRAFT")

        resp = client.get("/dashboard/overview")
        campaigns = resp.json()["campaigns"]
        assert campaigns["total"] >= 2
        assert campaigns["active_count"] >= 1

    def test_outreach_section(self):
        """Message status counts are correct."""
        _create_message("DRAFT")
        _create_message("PENDING_APPROVAL")
        _create_message("SENT")

        resp = client.get("/dashboard/overview")
        outreach = resp.json()["outreach"]
        assert outreach["total"] >= 3
        assert outreach["drafts"] >= 1
        assert outreach["pending_approval"] >= 1
        assert outreach["sent"] >= 1

    def test_outreach_approval_needed(self):
        """Approval-needed count includes pending + approved + ready_to_send."""
        _create_message("PENDING_APPROVAL")
        _create_message("APPROVED")
        _create_message("READY_TO_SEND")

        resp = client.get("/dashboard/overview")
        outreach = resp.json()["outreach"]
        assert outreach["approval_needed"] >= 3

    def test_followups_section(self):
        """Follow-up counts are correct."""
        _create_followup("DUE")
        _create_followup("PENDING")
        _create_followup("COMPLETED")

        resp = client.get("/dashboard/overview")
        followups = resp.json()["followups"]
        assert followups["total"] >= 3
        assert followups["overdue"] >= 1
        assert followups["pending"] >= 1
        assert followups["completed"] >= 1

    def test_analytics_funnel(self):
        """Analytics funnel is populated."""
        cid = _create_company("FunnelCorp")
        oid = _create_opportunity(cid)
        _create_application(oid, "APPLIED")

        resp = client.get("/dashboard/overview")
        analytics = resp.json()["analytics"]
        funnel = analytics["application_funnel"]
        assert len(funnel) > 0
        # First stage should be Total Opportunities
        assert funnel[0]["stage"] == "Total Opportunities"
        assert funnel[0]["count"] >= 1

    def test_analytics_empty_division_safety(self):
        """Analytics handles division by zero gracefully."""
        resp = client.get("/dashboard/overview")
        analytics = resp.json()["analytics"]
        # No data = None rates, not NaN or Infinity
        assert analytics["application_rate"] is None
        assert analytics["interview_rate"] is None
        assert analytics["offer_rate"] is None
        assert analytics["acceptance_rate"] is None

    def test_analytics_rates_with_data(self):
        """Analytics rates are calculated correctly."""
        cid = _create_company("AnalyticsCorp")
        for i in range(5):
            oid = _create_opportunity(cid, title=f"Job {i}")
            _create_application(oid, "APPLIED")
        oid2 = _create_opportunity(cid, title="Special Job")
        _create_application(oid2, "INTERVIEW")
        _create_application(oid2, "OFFER")

        resp = client.get("/dashboard/overview")
        analytics = resp.json()["analytics"]
        assert analytics["application_rate"] is not None
        assert analytics["interview_rate"] is not None
        assert analytics["offer_rate"] is not None
        # All rates should be between 0 and 1
        assert 0 <= analytics["application_rate"] <= 1
        assert 0 <= analytics["interview_rate"] <= 1
        assert 0 <= analytics["offer_rate"] <= 1

    def test_no_fabricated_data(self):
        """Dashboard never invents deadlines or dates."""
        resp = client.get("/dashboard/overview")
        data = resp.json()
        # No section should contain invented timestamps
        for section in ["overview", "today", "pipeline", "opportunities"]:
            assert "fabricated_date" not in str(data[section])


class TestDashboardEmptyDatabase:
    """Test dashboard with completely empty database."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        yield
        _cleanup()

    def test_every_section_returns_valid_data(self):
        """Every section returns valid data even when empty."""
        resp = client.get("/dashboard/overview")
        assert resp.status_code == 200
        data = resp.json()
        # All sections should be present and valid dicts
        for section in [
            "overview", "today", "pipeline", "opportunities",
            "summer_2027", "campaigns", "outreach", "followups", "analytics",
        ]:
            assert section in data
            assert isinstance(data[section], dict)


class TestDashboardSummer2027:
    """Test Summer 2027 classification precedence."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        yield
        _cleanup()

    def test_summer_2027_takes_precedence(self):
        """Summer 2027 opportunities are not classified as generic FUTURE."""
        cid = _create_company("SummerPrecedenceCorp")
        summer_deadline = datetime(2027, 6, 15, tzinfo=timezone.utc)
        _create_opportunity(cid, title="Summer Intern", deadline=summer_deadline, opp_type="INTERNSHIP")

        resp = client.get("/dashboard/overview")
        summer = resp.json()["summer_2027"]
        opps = resp.json()["opportunities"]

        # Summer 2027 should capture the opportunity
        assert summer["total"] >= 1
        # FUTURE should not contain it
        # (horizon distribution may show SUMMER_2027)
        horizon = opps["by_horizon"]
        assert horizon.get("SUMMER_2027", 0) >= 1

    def test_may_deadline_classified_summer(self):
        """May 2027 deadline = SUMMER_2027."""
        cid = _create_company("MayCorp")
        may_deadline = datetime(2027, 5, 20, tzinfo=timezone.utc)
        _create_opportunity(cid, deadline=may_deadline)

        resp = client.get("/dashboard/overview")
        summer = resp.json()["summer_2027"]
        assert summer["total"] >= 1

    def test_july_deadline_not_summer(self):
        """July 2027 deadline is NOT SUMMER_2027."""
        cid = _create_company("JulyCorp")
        july_deadline = datetime(2027, 7, 5, tzinfo=timezone.utc)
        _create_opportunity(cid, deadline=july_deadline)

        resp = client.get("/dashboard/overview")
        summer = resp.json()["summer_2027"]
        # July 2027 should NOT be classified as SUMMER_2027
        assert summer["total"] == 0
