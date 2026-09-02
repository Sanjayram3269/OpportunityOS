"""Comprehensive tests for enhanced campaign intelligence and planning.

Tests cover:
- Enhanced campaign summary with application/action breakdowns
- Campaign planning data with horizon classification
- Campaign action summary
- Enhanced planning data with application/outreach/campaign context
- Planning overview summary
- Campaign context in action center
- API endpoints for all new functionality
- Existing regression
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.application import Action, Application
from app.models.company import Company
from app.models.followup import FollowUp
from app.models.lead import Lead
from app.models.message import Message
from app.models.opportunity import Opportunity
from app.services.campaign import (
    ACTIVE,
    DRAFT,
    add_opportunity_to_campaign,
    create_campaign,
)
from app.services.campaign_enhanced import (
    get_campaign_action_summary,
    get_campaign_planning_data,
    get_enhanced_campaign_summary,
)
from app.services.planning_enhanced import (
    get_enhanced_planning_data,
    get_planning_overview_summary,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_lead(db, company, name="Test Lead"):
    lead = Lead(company_id=company.id, name=name, email="lead@test.com", status="ACTIVE")
    db.add(lead)
    db.flush()
    return lead


def _create_company(db, name="CampCo"):
    company = Company(name=name)
    db.add(company)
    db.flush()
    return company


def _create_opportunity(db, company, *, title="Python Dev", match_score=70,
                        deadline=None, status="DISCOVERED", priority="MEDIUM",
                        opp_type="FULL_TIME"):
    opp = Opportunity(
        company_id=company.id,
        type=opp_type,
        title=title,
        description="Test",
        match_score=match_score,
        deadline=deadline,
        status=status,
        priority=priority,
    )
    db.add(opp)
    db.flush()
    return opp


# ══════════════════════════════════════════════════════════════════════════
# 1. ENHANCED CAMPAIGN SUMMARY
# ══════════════════════════════════════════════════════════════════════════


class TestEnhancedCampaignSummary:
    def test_empty_campaign_summary(self, db):
        c = create_campaign(db, name="Empty", type="FULL_TIME")
        summary = get_enhanced_campaign_summary(db, c)
        assert summary["total_opportunities"] == 0
        assert summary["applications_started"] == 0
        assert summary["not_applied"] == 0

    def test_summary_with_opportunities(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)
        opp1 = _create_opportunity(db, company, match_score=80)
        opp2 = _create_opportunity(db, company, match_score=60)

        add_opportunity_to_campaign(db, c, opp1.id)
        add_opportunity_to_campaign(db, c, opp2.id)

        summary = get_enhanced_campaign_summary(db, c)
        assert summary["total_opportunities"] == 2
        assert summary["average_match_score"] == 70.0
        assert summary["high_match_count"] == 1
        assert summary["not_applied"] == 2

    def test_summary_with_application(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)
        opp = _create_opportunity(db, company, match_score=80)
        add_opportunity_to_campaign(db, c, opp.id)

        app = Application(opportunity_id=opp.id, status="APPLIED")
        db.add(app)
        db.flush()

        summary = get_enhanced_campaign_summary(db, c)
        assert summary["applications_started"] == 1
        assert summary["applications_submitted"] == 1
        assert summary["not_applied"] == 0
        assert summary["application_status_breakdown"]["APPLIED"] == 1

    def test_summary_with_messages(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)
        opp = _create_opportunity(db, company)
        lead = _create_lead(db, company)
        add_opportunity_to_campaign(db, c, opp.id)

        msg = Message(
            lead_id=lead.id, opportunity_id=opp.id, channel="EMAIL",
            direction="OUTBOUND", subject="Test", body="Hi",
            status="SENT",
        )
        db.add(msg)
        db.flush()

        summary = get_enhanced_campaign_summary(db, c)
        assert summary["sent_count"] == 1

    def test_summary_with_followups(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)
        opp = _create_opportunity(db, company)
        lead = _create_lead(db, company)
        add_opportunity_to_campaign(db, c, opp.id)

        fu = FollowUp(
            lead_id=lead.id, opportunity_id=opp.id,
            scheduled_for=datetime.now(timezone.utc),
            status="COMPLETED",
        )
        db.add(fu)
        db.flush()

        summary = get_enhanced_campaign_summary(db, c)
        assert summary["followups_completed"] == 1

    def test_summary_planning_horizon_distribution(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)

        # Create opportunities with different deadlines
        opp1 = _create_opportunity(
            db, company, title="Now", match_score=80,
            deadline=datetime.now(timezone.utc) + timedelta(days=3),
        )
        opp2 = _create_opportunity(
            db, company, title="Summer", match_score=90,
            deadline=datetime(2027, 5, 15, tzinfo=timezone.utc),
        )
        opp3 = _create_opportunity(
            db, company, title="Unknown", match_score=60,
            deadline=None,
        )

        add_opportunity_to_campaign(db, c, opp1.id)
        add_opportunity_to_campaign(db, c, opp2.id)
        add_opportunity_to_campaign(db, c, opp3.id)

        summary = get_enhanced_campaign_summary(db, c)
        dist = summary["planning_horizon_distribution"]
        assert "NOW" in dist
        assert "SUMMER_2027" in dist
        assert "UNKNOWN" in dist


# ══════════════════════════════════════════════════════════════════════════
# 2. CAMPAIGN PLANNING DATA
# ══════════════════════════════════════════════════════════════════════════


class TestCampaignPlanningData:
    def test_campaign_planning_returns_horizons(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)

        opp = _create_opportunity(
            db, company, title="Summer", match_score=85,
            deadline=datetime(2027, 6, 1, tzinfo=timezone.utc),
        )
        add_opportunity_to_campaign(db, c, opp.id)

        results = get_campaign_planning_data(db, c)
        assert len(results) == 1
        assert results[0]["planning_horizon"] == "SUMMER_2027"
        assert results[0]["application_status"] == "NOT_APPLIED"

    def test_campaign_planning_filters_by_horizon(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)

        opp1 = _create_opportunity(
            db, company, title="Now", match_score=80,
            deadline=datetime.now(timezone.utc) + timedelta(days=3),
        )
        opp2 = _create_opportunity(
            db, company, title="Summer", match_score=90,
            deadline=datetime(2027, 5, 15, tzinfo=timezone.utc),
        )
        add_opportunity_to_campaign(db, c, opp1.id)
        add_opportunity_to_campaign(db, c, opp2.id)

        results = get_campaign_planning_data(db, c, horizon="NOW")
        assert len(results) == 1
        assert results[0]["planning_horizon"] == "NOW"

    def test_campaign_planning_shows_other_campaigns(self, db):
        c1 = create_campaign(db, name="Campaign A", type="FULL_TIME")
        c2 = create_campaign(db, name="Campaign B", type="INTERNSHIP")
        company = _create_company(db)
        opp = _create_opportunity(db, company)

        add_opportunity_to_campaign(db, c1, opp.id)
        add_opportunity_to_campaign(db, c2, opp.id)

        results = get_campaign_planning_data(db, c1)
        assert len(results) == 1
        assert "Campaign B" in results[0]["other_campaigns"]


# ══════════════════════════════════════════════════════════════════════════
# 3. CAMPAIGN ACTION SUMMARY
# ══════════════════════════════════════════════════════════════════════════


class TestCampaignActionSummary:
    def test_empty_campaign_actions(self, db):
        c = create_campaign(db, name="Empty", type="FULL_TIME")
        result = get_campaign_action_summary(db, c)
        assert result["total_actions"] == 0

    def test_campaign_with_actions(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)
        opp = _create_opportunity(db, company, match_score=85)
        add_opportunity_to_campaign(db, c, opp.id)

        action = Action(
            action_type="APPLY",
            priority="P0",
            entity_type="opportunity",
            entity_id=opp.id,
            title="Apply",
            status="OPEN",
        )
        db.add(action)
        db.flush()

        result = get_campaign_action_summary(db, c)
        assert result["total_actions"] == 1
        assert result["by_priority"]["P0"] == 1
        assert result["by_type"]["APPLY"] == 1


# ══════════════════════════════════════════════════════════════════════════
# 4. ENHANCED PLANNING DATA
# ══════════════════════════════════════════════════════════════════════════


class TestEnhancedPlanningData:
    def test_enriched_planning_basic(self, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company, match_score=75)

        results = get_enhanced_planning_data(db, limit=10)
        assert len(results) >= 1

        enriched = next(r for r in results if r["opportunity_id"] == opp.id)
        assert enriched["planning_horizon"] == "UNKNOWN"  # no deadline
        assert enriched["application_status"] == "NOT_APPLIED"
        assert enriched["outreach_status"] == "NO_OUTREACH"

    def test_enriched_planning_with_campaign(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)
        opp = _create_opportunity(db, company, match_score=80)
        add_opportunity_to_campaign(db, c, opp.id)

        results = get_enhanced_planning_data(db, campaign_id=c.id)
        assert len(results) == 1
        assert "Test" in results[0]["campaigns"]

    def test_enriched_planning_with_application(self, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company, match_score=80)

        app = Application(opportunity_id=opp.id, status="INTERVIEW")
        db.add(app)
        db.flush()

        results = get_enhanced_planning_data(db, limit=10)
        enriched = next(r for r in results if r["opportunity_id"] == opp.id)
        assert enriched["application_status"] == "INTERVIEW"

    def test_enriched_planning_with_outreach(self, db):
        company = _create_company(db)
        opp = _create_opportunity(db, company, match_score=80)
        lead = _create_lead(db, company)

        msg = Message(
            lead_id=lead.id, opportunity_id=opp.id, channel="EMAIL",
            direction="OUTBOUND", subject="Test", body="Hi",
            status="PENDING_APPROVAL",
        )
        db.add(msg)
        db.flush()

        results = get_enhanced_planning_data(db, limit=10)
        enriched = next(r for r in results if r["opportunity_id"] == opp.id)
        assert enriched["outreach_status"] == "PENDING_APPROVAL"

    def test_enriched_planning_explanation(self, db):
        company = _create_company(db)
        opp = _create_opportunity(
            db, company, match_score=85,
            deadline=datetime(2027, 5, 15, tzinfo=timezone.utc),
        )

        results = get_enhanced_planning_data(db, limit=10)
        enriched = next(r for r in results if r["opportunity_id"] == opp.id)
        assert "High match" in enriched["planning_explanation"]
        assert "Summer 2027" in enriched["planning_explanation"]


# ══════════════════════════════════════════════════════════════════════════
# 5. PLANNING OVERVIEW
# ══════════════════════════════════════════════════════════════════════════


class TestPlanningOverview:
    def test_overview_empty(self, db):
        result = get_planning_overview_summary(db)
        assert result["total_opportunities"] == 0
        assert result["total_applications"] == 0

    def test_overview_with_data(self, db):
        company = _create_company(db)
        opp1 = _create_opportunity(db, company, match_score=80)
        opp2 = _create_opportunity(db, company, match_score=60, opp_type="INTERNSHIP")

        app = Application(opportunity_id=opp1.id, status="APPLIED")
        db.add(app)
        db.flush()

        result = get_planning_overview_summary(db)
        assert result["total_opportunities"] == 2
        assert result["total_applications"] == 1
        assert result["not_applied"] == 1
        assert result["average_match_score"] == 70.0
        assert "UNKNOWN" in result["horizon_distribution"]
        assert result["type_distribution"]["FULL_TIME"] == 1
        assert result["type_distribution"]["INTERNSHIP"] == 1


# ══════════════════════════════════════════════════════════════════════════
# 6. API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════


class TestEnhancedCampaignAPI:
    def test_enhanced_summary(self, client, db):
        company_resp = client.post("/companies", json={"name": "Co"})
        cid = company_resp.json()["id"]
        opp_resp = client.post("/opportunities", json={
            "company_id": cid, "type": "FULL_TIME", "title": "Dev",
        })
        opp_id = opp_resp.json()["id"]

        camp_resp = client.post("/campaigns", json={"name": "C", "type": "FULL_TIME"})
        camp_id = camp_resp.json()["id"]
        client.post(f"/campaigns/{camp_id}/opportunities/{opp_id}")

        resp = client.get(f"/campaigns/{camp_id}/enhanced-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_opportunities"] == 1
        assert "application_status_breakdown" in data
        assert "planning_horizon_distribution" in data

    def test_enhanced_summary_404(self, client, db):
        resp = client.get("/campaigns/99999/enhanced-summary")
        assert resp.status_code == 404

    def test_campaign_planning(self, client, db):
        company_resp = client.post("/companies", json={"name": "Co"})
        cid = company_resp.json()["id"]
        opp_resp = client.post("/opportunities", json={
            "company_id": cid, "type": "FULL_TIME", "title": "Dev",
        })
        opp_id = opp_resp.json()["id"]

        camp_resp = client.post("/campaigns", json={"name": "C", "type": "FULL_TIME"})
        camp_id = camp_resp.json()["id"]
        client.post(f"/campaigns/{camp_id}/opportunities/{opp_id}")

        resp = client.get(f"/campaigns/{camp_id}/planning")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert "planning_horizon" in data["opportunities"][0]
        assert "application_status" in data["opportunities"][0]

    def test_campaign_planning_404(self, client, db):
        resp = client.get("/campaigns/99999/planning")
        assert resp.status_code == 404

    def test_campaign_action_summary(self, client, db):
        company_resp = client.post("/companies", json={"name": "Co"})
        cid = company_resp.json()["id"]
        opp_resp = client.post("/opportunities", json={
            "company_id": cid, "type": "FULL_TIME", "title": "Dev",
        })
        opp_id = opp_resp.json()["id"]

        camp_resp = client.post("/campaigns", json={"name": "C", "type": "FULL_TIME"})
        camp_id = camp_resp.json()["id"]
        client.post(f"/campaigns/{camp_id}/opportunities/{opp_id}")

        resp = client.get(f"/campaigns/{camp_id}/action-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_actions" in data
        assert "by_priority" in data

    def test_campaign_action_summary_404(self, client, db):
        resp = client.get("/campaigns/99999/action-summary")
        assert resp.status_code == 404


class TestEnhancedPlanningAPI:
    def test_planning_overview(self, client, db):
        company_resp = client.post("/companies", json={"name": "Co"})
        cid = company_resp.json()["id"]
        client.post("/opportunities", json={
            "company_id": cid, "type": "FULL_TIME", "title": "Dev",
        })

        resp = client.get("/opportunities/planning/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_opportunities"] >= 1
        assert "horizon_distribution" in data

    def test_enriched_planning(self, client, db):
        company_resp = client.post("/companies", json={"name": "Co"})
        cid = company_resp.json()["id"]
        client.post("/opportunities", json={
            "company_id": cid, "type": "FULL_TIME", "title": "Dev",
        })

        resp = client.get("/opportunities/planning/enriched")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

        opp = data["opportunities"][0]
        assert "planning_horizon" in opp
        assert "application_status" in opp
        assert "outreach_status" in opp
        assert "campaigns" in opp

    def test_enriched_planning_filter_by_horizon(self, client, db):
        company_resp = client.post("/companies", json={"name": "Co"})
        cid = company_resp.json()["id"]
        client.post("/opportunities", json={
            "company_id": cid, "type": "FULL_TIME", "title": "Dev",
        })

        resp = client.get("/opportunities/planning/enriched?horizon=UNKNOWN")
        assert resp.status_code == 200
        data = resp.json()
        for opp in data["opportunities"]:
            assert opp["planning_horizon"] == "UNKNOWN"

    def test_enriched_planning_filter_by_campaign(self, client, db):
        company_resp = client.post("/companies", json={"name": "Co"})
        cid = company_resp.json()["id"]
        opp_resp = client.post("/opportunities", json={
            "company_id": cid, "type": "FULL_TIME", "title": "Dev",
        })
        opp_id = opp_resp.json()["id"]

        camp_resp = client.post("/campaigns", json={"name": "C", "type": "FULL_TIME"})
        camp_id = camp_resp.json()["id"]
        client.post(f"/campaigns/{camp_id}/opportunities/{opp_id}")

        resp = client.get(f"/opportunities/planning/enriched?campaign_id={camp_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1


# ══════════════════════════════════════════════════════════════════════════
# 7. REGRESSION
# ══════════════════════════════════════════════════════════════════════════


class TestRegression:
    def test_health(self, client):
        assert client.get("/health").status_code == 200

    def test_original_planning_still_works(self, client, db):
        company_resp = client.post("/companies", json={"name": "Co"})
        cid = company_resp.json()["id"]
        client.post("/opportunities", json={
            "company_id": cid, "type": "FULL_TIME", "title": "Dev",
        })

        resp = client.get("/opportunities/planning")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_original_campaign_endpoints_still_work(self, client, db):
        resp = client.post("/campaigns", json={"name": "Test", "type": "FULL_TIME"})
        assert resp.status_code == 201
        cid = resp.json()["id"]

        resp = client.get(f"/campaigns/{cid}")
        assert resp.status_code == 200

        resp = client.get(f"/campaigns/{cid}/summary")
        assert resp.status_code == 200
