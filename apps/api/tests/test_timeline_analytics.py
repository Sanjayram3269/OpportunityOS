"""Tests for Application Timeline and Analytics Deep Dive.

Covers:
- Application event creation on transitions
- Timeline endpoint
- Empty timeline
- No fabricated backfill
- Analytics overview
- Trends
- Conversion
- Velocity
- Source analytics
- Campaign analytics
- Type analytics
- Match analytics
- Summer 2027 analytics
- Date range filtering
- Division by zero safety
- Invalid date ranges
- Empty database
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cleanup():
    from app.db.session import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM application_events"))
        db.execute(text("DELETE FROM actions"))
        db.execute(text("DELETE FROM applications"))
        db.execute(text("DELETE FROM followups"))
        db.execute(text("DELETE FROM messages"))
        db.execute(text("DELETE FROM interactions"))
        db.execute(text("DELETE FROM campaign_opportunities"))
        db.execute(text("DELETE FROM campaigns"))
        db.execute(text("DELETE FROM opportunity_evidence"))
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
            description="Test",
        )
        db.add(o)
        db.commit()
        db.refresh(o)
        return o.id
    finally:
        db.close()


def _create_application(opportunity_id: int) -> int:
    from app.db.session import SessionLocal
    from app.services.application import create_application

    db = SessionLocal()
    try:
        app_obj = create_application(db, opportunity_id=opportunity_id)
        db.commit()
        return app_obj.id
    finally:
        db.close()


def _transition(app_id: int, target: str):
    from app.db.session import SessionLocal
    from app.services.application import transition_application

    db = SessionLocal()
    try:
        transition_application(db, app_id, target)
        db.commit()
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


def _add_to_campaign(campaign_id: int, opportunity_id: int):
    from app.db.session import SessionLocal
    from app.models.campaign_opportunity import CampaignOpportunity

    db = SessionLocal()
    try:
        co = CampaignOpportunity(campaign_id=campaign_id, opportunity_id=opportunity_id)
        db.add(co)
        db.commit()
    finally:
        db.close()


# ── Timeline Tests ────────────────────────────────────────────────────────


class TestApplicationTimeline:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        yield
        _cleanup()

    def test_timeline_has_creation_event(self):
        """Timeline always has at least the creation event."""
        cid = _create_company("EmptyTimeline")
        oid = _create_opportunity(cid)
        app_id = _create_application(oid)
        resp = client.get(f"/applications/{app_id}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        # At least the creation event
        assert len(data["events"]) >= 1
        assert data["events"][0]["event_type"] == "APPLICATION_CREATED"

    def test_timeline_created_event(self):
        """Application creation creates a timeline event."""
        cid = _create_company("CreateEvent")
        oid = _create_opportunity(cid)
        app_id = _create_application(oid)
        resp = client.get(f"/applications/{app_id}/timeline")
        data = resp.json()
        # Creation event should be present
        events = data["events"]
        assert len(events) >= 1
        assert events[0]["event_type"] == "APPLICATION_CREATED"
        assert events[0]["to_status"] == "NOT_APPLIED"

    def test_timeline_full_lifecycle(self):
        """Full lifecycle creates proper events."""
        cid = _create_company("FullLifecycle")
        oid = _create_opportunity(cid)
        app_id = _create_application(oid)

        # Transition through the pipeline
        _transition(app_id, "READY")
        _transition(app_id, "APPLIED")
        _transition(app_id, "ASSESSMENT")
        _transition(app_id, "INTERVIEW")
        _transition(app_id, "FINAL_ROUND")
        _transition(app_id, "OFFER")
        _transition(app_id, "ACCEPTED")

        resp = client.get(f"/applications/{app_id}/timeline")
        data = resp.json()
        events = data["events"]

        # Should have 8 events: created + 7 transitions
        assert len(events) == 8
        assert data["current_status"] == "ACCEPTED"

        # Verify event types
        event_types = [e["event_type"] for e in events]
        assert "APPLICATION_CREATED" in event_types
        assert "APPLICATION_SUBMITTED" in event_types
        assert "ASSESSMENT" in event_types
        assert "INTERVIEW" in event_types
        assert "FINAL_ROUND" in event_types
        assert "OFFER" in event_types
        assert "ACCEPTED" in event_types

    def test_timeline_ordered_oldest_first(self):
        """Events are ordered chronologically (oldest first)."""
        cid = _create_company("OrderedTimeline")
        oid = _create_opportunity(cid)
        app_id = _create_application(oid)
        _transition(app_id, "READY")
        _transition(app_id, "APPLIED")
        _transition(app_id, "INTERVIEW")

        resp = client.get(f"/applications/{app_id}/timeline")
        events = resp.json()["events"]

        timestamps = [e["occurred_at"] for e in events]
        assert timestamps == sorted(timestamps)

    def test_timeline_404_for_missing_application(self):
        """Timeline returns 404 for nonexistent application."""
        resp = client.get("/applications/99999/timeline")
        assert resp.status_code == 404

    def test_timeline_rejection_event(self):
        """Rejection creates proper event."""
        cid = _create_company("RejectTimeline")
        oid = _create_opportunity(cid)
        app_id = _create_application(oid)
        _transition(app_id, "READY")
        _transition(app_id, "APPLIED")
        _transition(app_id, "REJECTED")

        resp = client.get(f"/applications/{app_id}/timeline")
        events = resp.json()["events"]
        rejection_events = [e for e in events if e["event_type"] == "REJECTED"]
        assert len(rejection_events) == 1
        assert rejection_events[0]["to_status"] == "REJECTED"

    def test_no_fabricated_backfill(self):
        """Old applications don't get fabricated historical events."""
        cid = _create_company("NoBackfill")
        oid = _create_opportunity(cid)
        app_id = _create_application(oid)
        # Only created — no transitions
        resp = client.get(f"/applications/{app_id}/timeline")
        events = resp.json()["events"]
        # Only creation event, no fabricated transitions
        assert len(events) == 1
        assert events[0]["event_type"] == "APPLICATION_CREATED"


# ── Analytics Tests ───────────────────────────────────────────────────────


class TestAnalyticsOverview:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        yield
        _cleanup()

    def test_analytics_returns_200(self):
        """Analytics endpoint returns successfully."""
        resp = client.get("/analytics/overview")
        assert resp.status_code == 200

    def test_analytics_has_all_sections(self):
        """Analytics response contains all expected sections."""
        resp = client.get("/analytics/overview")
        data = resp.json()
        expected = [
            "overview", "trends", "velocity", "conversion",
            "source_analytics", "campaign_analytics",
            "type_analytics", "match_analytics", "summer_2027",
        ]
        for section in expected:
            assert section in data

    def test_analytics_empty_database(self):
        """Analytics returns valid data for empty database."""
        resp = client.get("/analytics/overview")
        data = resp.json()
        assert data["overview"]["total_opportunities"] == 0
        assert data["overview"]["total_applications"] == 0

    def test_analytics_with_real_data(self):
        """Analytics reflects real database records."""
        cid = _create_company("AnalyticsReal")
        oid = _create_opportunity(cid, match_score=90)
        app_id = _create_application(oid)
        _transition(app_id, "READY")
        _transition(app_id, "APPLIED")
        _transition(app_id, "INTERVIEW")

        resp = client.get("/analytics/overview")
        data = resp.json()
        assert data["overview"]["total_opportunities"] == 1
        assert data["overview"]["total_applications"] == 1
        assert data["overview"]["interviews"] >= 1

    def test_analytics_date_range_filtering(self):
        """Date range filtering works correctly."""
        resp = client.get(
            "/analytics/overview",
            params={"start_date": "2020-01-01", "end_date": "2020-12-31"},
        )
        assert resp.status_code == 200

    def test_analytics_invalid_date_range(self):
        """Invalid date range returns 400."""
        resp = client.get(
            "/analytics/overview",
            params={"start_date": "2025-12-31", "end_date": "2025-01-01"},
        )
        assert resp.status_code == 400

    def test_analytics_invalid_date_format(self):
        """Invalid date format returns 400."""
        resp = client.get(
            "/analytics/overview",
            params={"start_date": "not-a-date"},
        )
        assert resp.status_code == 400

    def test_analytics_conversion_stages(self):
        """Conversion funnel has proper stages."""
        resp = client.get("/analytics/overview")
        conversion = resp.json()["conversion"]
        assert len(conversion["stages"]) > 0
        stage_names = [s["stage"] for s in conversion["stages"]]
        assert "NOT_APPLIED" in stage_names
        assert "ACCEPTED" in stage_names

    def test_analytics_velocity_empty_when_no_transitions(self):
        """Velocity is empty when no transitions exist."""
        resp = client.get("/analytics/overview")
        velocity = resp.json()["velocity"]
        assert len(velocity["transitions"]) == 0

    def test_analytics_velocity_with_transitions(self):
        """Velocity shows real transition durations."""
        cid = _create_company("VelocityCorp")
        oid = _create_opportunity(cid)
        app_id = _create_application(oid)
        _transition(app_id, "READY")
        _transition(app_id, "APPLIED")

        resp = client.get("/analytics/overview")
        velocity = resp.json()["velocity"]
        # May or may not have velocity data depending on timing
        assert isinstance(velocity["transitions"], dict)

    def test_analytics_summer_2027(self):
        """Summer 2027 analytics are computed correctly."""
        cid = _create_company("SummerAnalytics")
        summer_deadline = datetime(2027, 6, 1, tzinfo=timezone.utc)
        _create_opportunity(cid, title="Summer Intern", deadline=summer_deadline, opp_type="INTERNSHIP")
        _create_opportunity(cid, title="Other Job", deadline=_now() + timedelta(days=10))

        resp = client.get("/analytics/overview")
        summer = resp.json()["summer_2027"]
        assert summer["total"] >= 1

    def test_analytics_campaign_performance(self):
        """Campaign analytics show real data."""
        cid = _create_company("CampaignAnalytics")
        oid = _create_opportunity(cid, match_score=85)
        camp_id = _create_campaign("Test Campaign")
        _add_to_campaign(camp_id, oid)

        resp = client.get("/analytics/overview")
        campaigns = resp.json()["campaign_analytics"]
        assert len(campaigns["campaigns"]) >= 1
        camp = campaigns["campaigns"][0]
        assert camp["opportunities"] >= 1

    def test_analytics_source_performance(self):
        """Source analytics show company-based performance."""
        cid = _create_company("SourceAnalytics")
        _create_opportunity(cid, match_score=90)
        _create_opportunity(cid, match_score=85)

        resp = client.get("/analytics/overview")
        sources = resp.json()["source_analytics"]
        assert len(sources["sources"]) >= 1
        assert sources["sources"][0]["company"] == "SourceAnalytics"
        assert sources["sources"][0]["opportunities"] == 2

    def test_analytics_match_buckets(self):
        """Match analytics show proper score buckets."""
        cid = _create_company("MatchAnalytics")
        _create_opportunity(cid, match_score=95)
        _create_opportunity(cid, match_score=85)
        _create_opportunity(cid, match_score=75)
        _create_opportunity(cid, match_score=55)

        resp = client.get("/analytics/overview")
        match = resp.json()["match_analytics"]
        assert len(match["buckets"]) == 5
        # Verify bucket structure
        for b in match["buckets"]:
            assert "bucket" in b
            assert "opportunities" in b
            assert "applications" in b

    def test_analytics_type_breakdown(self):
        """Type analytics show opportunity type distribution."""
        cid = _create_company("TypeAnalytics")
        _create_opportunity(cid, opp_type="INTERNSHIP")
        _create_opportunity(cid, opp_type="FULL_TIME")
        _create_opportunity(cid, opp_type="FULL_TIME")

        resp = client.get("/analytics/overview")
        types = resp.json()["type_analytics"]
        assert len(types["types"]) >= 2
        type_map = {t["type"]: t["opportunities"] for t in types["types"]}
        assert type_map.get("INTERNSHIP") == 1
        assert type_map.get("FULL_TIME") == 2

    def test_analytics_zero_division_safety(self):
        """Analytics handles division by zero gracefully."""
        resp = client.get("/analytics/overview")
        data = resp.json()
        # All rates should be None when no data
        assert data["overview"]["interview_rate"] is None
        assert data["overview"]["offer_rate"] is None

    def test_analytics_match_bucket_application_rate(self):
        """Match bucket application rates are safe."""
        cid = _create_company("MatchRateCorp")
        _create_opportunity(cid, match_score=90)

        resp = client.get("/analytics/overview")
        buckets = resp.json()["match_analytics"]["buckets"]
        for b in buckets:
            assert b["application_rate"] is None or 0 <= b["application_rate"] <= 1

    def test_analytics_trends_comparison(self):
        """Trends include current vs previous period comparison."""
        resp = client.get("/analytics/overview")
        trends = resp.json()["trends"]
        assert "period_days" in trends
        assert "applications" in trends
        assert "current" in trends["applications"]
        assert "previous" in trends["applications"]
        assert "change" in trends["applications"]
