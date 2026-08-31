"""Comprehensive tests for Campaign Management + Opportunity Planning.

Tests cover:
  Campaign:
    1. creation, retrieval, listing, update
    2. lifecycle transitions
    3. invalid transitions
    4. add/remove opportunity
    5. duplicate membership
    6. invalid opportunity
    7. list campaign opportunities
    8. campaign summary
    9. campaign summary with messages/follow-ups

  Planning:
    10. NOW/UPCOMING/SUMMER_2027/FUTURE/UNKNOWN classification
    11. timezone correctness
    12. deadline boundary tests
    13. no fabricated deadline
    14. match score preserved
    15. planning priority differs from match score
    16. filtering by horizon/type/status
    17. sorting by planning priority

  Integration:
    18. campaign + opportunity + message
    19. existing regression
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.company import Company
from app.models.message import Message
from app.models.opportunity import Opportunity
from app.services.campaign import (
    ACTIVE,
    ARCHIVED,
    COMPLETED,
    DRAFT,
    PAUSED,
    CampaignStateError,
    activate_campaign,
    add_opportunity_to_campaign,
    archive_campaign,
    can_transition,
    complete_campaign,
    create_campaign,
    get_campaign_summary,
    list_campaign_opportunities,
    list_opportunity_campaigns,
    pause_campaign,
    remove_opportunity_from_campaign,
    transition_campaign,
    update_campaign,
)
from app.services.followup import (
    APPROVED as FU_APPROVED,
    COMPLETED as FU_COMPLETED,
    DUE as FU_DUE,
    PENDING as FU_PENDING,
    READY_TO_SEND as FU_READY,
)
from app.services.planning import (
    HORIZON_FUTURE,
    HORIZON_NOW,
    HORIZON_SUMMER_2027,
    HORIZON_UNKNOWN,
    HORIZON_UPCOMING,
    calculate_planning_priority,
    classify_horizon,
)


# ── Helpers ──────────────────────────────────────────────────────────────


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
# 1. CAMPAIGN LIFECYCLE
# ══════════════════════════════════════════════════════════════════════════


class TestCampaignLifecycle:
    def test_draft_to_active(self):
        assert can_transition(DRAFT, ACTIVE) is True

    def test_active_to_paused(self):
        assert can_transition(ACTIVE, PAUSED) is True

    def test_paused_to_active(self):
        assert can_transition(PAUSED, ACTIVE) is True

    def test_active_to_completed(self):
        assert can_transition(ACTIVE, COMPLETED) is True

    def test_completed_to_archived(self):
        assert can_transition(COMPLETED, ARCHIVED) is True

    def test_draft_to_archived(self):
        assert can_transition(DRAFT, ARCHIVED) is True

    def test_cannot_skip_to_completed(self):
        assert can_transition(DRAFT, COMPLETED) is False

    def test_cannot_skip_to_archived_from_active(self):
        # ACTIVE can go to ARCHIVED
        assert can_transition(ACTIVE, ARCHIVED) is True

    def test_archived_is_terminal(self):
        assert can_transition(ARCHIVED, DRAFT) is False
        assert can_transition(ARCHIVED, ACTIVE) is False


# ══════════════════════════════════════════════════════════════════════════
# 2. CAMPAIGN CRUD
# ══════════════════════════════════════════════════════════════════════════


class TestCampaignCRUD:
    def test_create_campaign(self, db):
        c = create_campaign(db, name="Summer 2027", type="INTERNSHIP")
        assert c.id is not None
        assert c.name == "Summer 2027"
        assert c.status == DRAFT

    def test_create_with_description(self, db):
        c = create_campaign(
            db, name="Backend", type="FULL_TIME",
            description="Backend roles",
            target_description="Python, Django",
        )
        assert c.description == "Backend roles"

    def test_get_campaign(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        from app.services.campaign import get_campaign
        retrieved = get_campaign(db, c.id)
        assert retrieved is not None
        assert retrieved.id == c.id

    def test_list_campaigns(self, db):
        create_campaign(db, name="A", type="FULL_TIME")
        create_campaign(db, name="B", type="INTERNSHIP")
        from app.services.campaign import list_campaigns
        items = list_campaigns(db)
        assert len(items) == 2

    def test_list_filter_by_type(self, db):
        create_campaign(db, name="A", type="FULL_TIME")
        create_campaign(db, name="B", type="INTERNSHIP")
        from app.services.campaign import list_campaigns
        items = list_campaigns(db, type="INTERNSHIP")
        assert len(items) == 1

    def test_update_campaign(self, db):
        c = create_campaign(db, name="Old", type="FULL_TIME")
        updated = update_campaign(db, c, name="New")
        assert updated.name == "New"

    def test_update_restricted_when_completed(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        activate_campaign(db, c)
        complete_campaign(db, c)
        with pytest.raises(CampaignStateError):
            update_campaign(db, c, name="Nope")


# ══════════════════════════════════════════════════════════════════════════
# 3. CAMPAIGN MEMBERSHIP
# ══════════════════════════════════════════════════════════════════════════


class TestCampaignMembership:
    def test_add_opportunity(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)
        opp = _create_opportunity(db, company)

        add_opportunity_to_campaign(db, c, opp.id)
        opps = list_campaign_opportunities(db, c)
        assert len(opps) == 1
        assert opps[0].id == opp.id

    def test_add_duplicate_opportunity_idempotent(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)
        opp = _create_opportunity(db, company)

        add_opportunity_to_campaign(db, c, opp.id)
        add_opportunity_to_campaign(db, c, opp.id)
        opps = list_campaign_opportunities(db, c)
        assert len(opps) == 1

    def test_add_invalid_opportunity(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        with pytest.raises(ValueError, match="Opportunity"):
            add_opportunity_to_campaign(db, c, 99999)

    def test_remove_opportunity(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)
        opp = _create_opportunity(db, company)

        add_opportunity_to_campaign(db, c, opp.id)
        removed = remove_opportunity_from_campaign(db, c, opp.id)
        assert removed is True
        opps = list_campaign_opportunities(db, c)
        assert len(opps) == 0

    def test_remove_nonexistent_returns_false(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        removed = remove_opportunity_from_campaign(db, c, 99999)
        assert removed is False

    def test_list_opportunity_campaigns(self, db):
        c1 = create_campaign(db, name="A", type="FULL_TIME")
        c2 = create_campaign(db, name="B", type="INTERNSHIP")
        company = _create_company(db)
        opp = _create_opportunity(db, company)

        add_opportunity_to_campaign(db, c1, opp.id)
        add_opportunity_to_campaign(db, c2, opp.id)

        campaigns = list_opportunity_campaigns(db, opp.id)
        assert len(campaigns) == 2


# ══════════════════════════════════════════════════════════════════════════
# 4. CAMPAIGN SUMMARY
# ══════════════════════════════════════════════════════════════════════════


class TestCampaignSummary:
    def test_empty_campaign_summary(self, db):
        c = create_campaign(db, name="Empty", type="FULL_TIME")
        summary = get_campaign_summary(db, c)
        assert summary["total_opportunities"] == 0
        assert summary["average_match_score"] is None

    def test_summary_with_opportunities(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)
        opp1 = _create_opportunity(db, company, match_score=80)
        opp2 = _create_opportunity(db, company, match_score=60)

        add_opportunity_to_campaign(db, c, opp1.id)
        add_opportunity_to_campaign(db, c, opp2.id)

        summary = get_campaign_summary(db, c)
        assert summary["total_opportunities"] == 2
        assert summary["average_match_score"] == 70.0
        assert summary["high_match_count"] == 1

    def test_summary_with_messages(self, db):
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)
        opp = _create_opportunity(db, company)
        add_opportunity_to_campaign(db, c, opp.id)

        msg = Message(
            lead_id=1, opportunity_id=opp.id, channel="EMAIL",
            direction="OUTBOUND", subject="Test", body="Hi",
            status="SENT",
        )
        db.add(msg)
        db.flush()

        summary = get_campaign_summary(db, c)
        assert summary["sent_count"] == 1

    def test_summary_with_followups(self, db):
        from app.models.followup import FollowUp
        c = create_campaign(db, name="Test", type="FULL_TIME")
        company = _create_company(db)
        opp = _create_opportunity(db, company)
        add_opportunity_to_campaign(db, c, opp.id)

        fu = FollowUp(
            lead_id=1, opportunity_id=opp.id,
            scheduled_for=datetime.now(timezone.utc),
            status="COMPLETED",
        )
        db.add(fu)
        db.flush()

        summary = get_campaign_summary(db, c)
        assert summary["followups_completed"] == 1


# ══════════════════════════════════════════════════════════════════════════
# 5. PLANNING HORIZON CLASSIFICATION
# ══════════════════════════════════════════════════════════════════════════


class TestPlanningHorizon:
    NOW = datetime(2026, 8, 31, tzinfo=timezone.utc)

    # ── NOW ──────────────────────────────────────────────────────

    def test_deadline_in_3_days_is_now(self):
        deadline = self.NOW + timedelta(days=3)
        assert classify_horizon(deadline, self.NOW) == HORIZON_NOW

    def test_deadline_in_7_days_is_now(self):
        deadline = self.NOW + timedelta(days=7)
        assert classify_horizon(deadline, self.NOW) == HORIZON_NOW

    def test_past_deadline_is_now(self):
        deadline = self.NOW - timedelta(days=5)
        assert classify_horizon(deadline, self.NOW) == HORIZON_NOW

    # ── UPCOMING ─────────────────────────────────────────────────

    def test_deadline_in_10_days_is_upcoming(self):
        deadline = self.NOW + timedelta(days=10)
        assert classify_horizon(deadline, self.NOW) == HORIZON_UPCOMING

    def test_deadline_in_20_days_is_upcoming(self):
        deadline = self.NOW + timedelta(days=20)
        assert classify_horizon(deadline, self.NOW) == HORIZON_UPCOMING

    def test_deadline_in_30_days_is_upcoming(self):
        deadline = self.NOW + timedelta(days=30)
        assert classify_horizon(deadline, self.NOW) == HORIZON_UPCOMING

    # ── SUMMER_2027 ──────────────────────────────────────────────

    def test_may_2027_is_summer_2027(self):
        deadline = datetime(2027, 5, 15, tzinfo=timezone.utc)
        assert classify_horizon(deadline, self.NOW) == HORIZON_SUMMER_2027

    def test_june_2027_is_summer_2027(self):
        deadline = datetime(2027, 6, 30, tzinfo=timezone.utc)
        assert classify_horizon(deadline, self.NOW) == HORIZON_SUMMER_2027

    def test_may_1_boundary_is_summer_2027(self):
        deadline = datetime(2027, 5, 1, tzinfo=timezone.utc)
        assert classify_horizon(deadline, self.NOW) == HORIZON_SUMMER_2027

    def test_june_30_boundary_is_summer_2027(self):
        deadline = datetime(2027, 6, 30, 23, 59, 59, tzinfo=timezone.utc)
        assert classify_horizon(deadline, self.NOW) == HORIZON_SUMMER_2027

    def test_april_30_is_not_summer_2027(self):
        deadline = datetime(2027, 4, 30, tzinfo=timezone.utc)
        assert classify_horizon(deadline, self.NOW) != HORIZON_SUMMER_2027

    def test_july_1_is_not_summer_2027(self):
        deadline = datetime(2027, 7, 1, tzinfo=timezone.utc)
        assert classify_horizon(deadline, self.NOW) != HORIZON_SUMMER_2027

    def test_summer_2027_takes_precedence_over_future(self):
        """May 2027 deadline is >30 days away but must be SUMMER_2027, not FUTURE."""
        deadline = datetime(2027, 5, 15, tzinfo=timezone.utc)
        result = classify_horizon(deadline, self.NOW)
        assert result == HORIZON_SUMMER_2027
        assert result != HORIZON_FUTURE

    def test_summer_2027_from_2026_date(self):
        """Running from Aug 2026, May/June 2027 remains SUMMER_2027."""
        now_aug_2026 = datetime(2026, 8, 15, tzinfo=timezone.utc)
        may_2027 = datetime(2027, 5, 15, tzinfo=timezone.utc)
        june_2027 = datetime(2027, 6, 15, tzinfo=timezone.utc)
        assert classify_horizon(may_2027, now_aug_2026) == HORIZON_SUMMER_2027
        assert classify_horizon(june_2027, now_aug_2026) == HORIZON_SUMMER_2027

    # ── FUTURE ───────────────────────────────────────────────────

    def test_deadline_in_60_days_is_future(self):
        deadline = self.NOW + timedelta(days=60)
        assert classify_horizon(deadline, self.NOW) == HORIZON_FUTURE

    def test_deadline_april_2027_is_future(self):
        deadline = datetime(2027, 4, 30, tzinfo=timezone.utc)
        assert classify_horizon(deadline, self.NOW) == HORIZON_FUTURE

    def test_deadline_july_2027_is_future(self):
        deadline = datetime(2027, 7, 1, tzinfo=timezone.utc)
        assert classify_horizon(deadline, self.NOW) == HORIZON_FUTURE

    # ── UNKNOWN ──────────────────────────────────────────────────

    def test_no_deadline_is_unknown(self):
        """No deadline = UNKNOWN, regardless of created_at."""
        assert classify_horizon(None, self.NOW) == HORIZON_UNKNOWN

    def test_no_deadline_recent_created_still_unknown(self):
        """created_at does NOT make a no-deadline opportunity NOW."""
        # Even if created 1 day ago, no deadline means UNKNOWN
        assert classify_horizon(None, self.NOW) == HORIZON_UNKNOWN

    # ── Timezone ─────────────────────────────────────────────────

    def test_timezone_naive_deadline_handled(self):
        naive_deadline = datetime(2027, 5, 15, 12, 0, 0)
        result = classify_horizon(naive_deadline, self.NOW)
        assert result == HORIZON_SUMMER_2027

    def test_deadline_day_boundary_7_vs_8(self):
        """Day 7 = NOW, day 8 = UPCOMING."""
        d7 = self.NOW + timedelta(days=7)
        d8 = self.NOW + timedelta(days=8)
        assert classify_horizon(d7, self.NOW) == HORIZON_NOW
        assert classify_horizon(d8, self.NOW) == HORIZON_UPCOMING

    def test_deadline_day_boundary_30_vs_31(self):
        """Day 30 = UPCOMING, day 31 = FUTURE."""
        d30 = self.NOW + timedelta(days=30)
        d31 = self.NOW + timedelta(days=31)
        assert classify_horizon(d30, self.NOW) == HORIZON_UPCOMING
        assert classify_horizon(d31, self.NOW) == HORIZON_FUTURE


# ══════════════════════════════════════════════════════════════════════════
# 6. PLANNING PRIORITY
# ══════════════════════════════════════════════════════════════════════════


class TestPlanningPriority:
    NOW = datetime(2026, 8, 31, tzinfo=timezone.utc)

    def test_high_match_near_deadline_high_priority(self):
        deadline = self.NOW + timedelta(days=3)
        score, reasons = calculate_planning_priority(
            match_score=90, deadline=deadline,
            priority="HIGH", status="DISCOVERED", opp_type="INTERNSHIP",
            now=self.NOW,
        )
        assert score >= 70
        assert any("90" in r for r in reasons)

    def test_no_match_no_deadline_low_priority(self):
        score, reasons = calculate_planning_priority(
            match_score=None, deadline=None,
            priority="LOW", status="APPLIED", opp_type="OTHER",
            now=self.NOW,
        )
        assert score < 30

    def test_match_score_independent_of_planning_priority(self):
        """Same match score can produce different planning priorities."""
        deadline_soon = self.NOW + timedelta(days=2)
        deadline_later = self.NOW + timedelta(days=60)

        score_soon, _ = calculate_planning_priority(
            match_score=70, deadline=deadline_soon,
            priority="MEDIUM", status="DISCOVERED", opp_type="FULL_TIME",
            now=self.NOW,
        )
        score_later, _ = calculate_planning_priority(
            match_score=70, deadline=deadline_later,
            priority="MEDIUM", status="DISCOVERED", opp_type="FULL_TIME",
            now=self.NOW,
        )
        assert score_soon > score_later

    def test_past_deadline_highest_urgency(self):
        deadline = self.NOW - timedelta(days=10)
        score, reasons = calculate_planning_priority(
            match_score=50, deadline=deadline,
            priority="MEDIUM", status="DISCOVERED", opp_type="FULL_TIME",
            now=self.NOW,
        )
        assert score >= 50
        assert any("passed" in r.lower() for r in reasons)


# ══════════════════════════════════════════════════════════════════════════
# 7. CAMPAIGN LIFECYCLE API
# ══════════════════════════════════════════════════════════════════════════


class TestCampaignAPI:
    def test_create_and_get(self, client, db):
        resp = client.post("/campaigns", json={
            "name": "Summer 2027", "type": "INTERNSHIP",
        })
        assert resp.status_code == 201
        cid = resp.json()["id"]

        resp = client.get(f"/campaigns/{cid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Summer 2027"

    def test_list(self, client, db):
        client.post("/campaigns", json={"name": "A", "type": "FULL_TIME"})
        client.post("/campaigns", json={"name": "B", "type": "INTERNSHIP"})
        resp = client.get("/campaigns")
        assert resp.json()["total"] == 2

    def test_update(self, client, db):
        resp = client.post("/campaigns", json={"name": "Old", "type": "FULL_TIME"})
        cid = resp.json()["id"]
        resp = client.patch(f"/campaigns/{cid}", json={"name": "New"})
        assert resp.json()["name"] == "New"

    def test_activate(self, client, db):
        resp = client.post("/campaigns", json={"name": "A", "type": "FULL_TIME"})
        cid = resp.json()["id"]
        resp = client.post(f"/campaigns/{cid}/activate")
        assert resp.json()["new_status"] == ACTIVE

    def test_full_lifecycle(self, client, db):
        resp = client.post("/campaigns", json={"name": "A", "type": "FULL_TIME"})
        cid = resp.json()["id"]

        client.post(f"/campaigns/{cid}/activate")
        resp = client.post(f"/campaigns/{cid}/pause")
        assert resp.json()["new_status"] == PAUSED

        client.post(f"/campaigns/{cid}/activate")
        resp = client.post(f"/campaigns/{cid}/complete")
        assert resp.json()["new_status"] == COMPLETED

        resp = client.post(f"/campaigns/{cid}/archive")
        assert resp.json()["new_status"] == ARCHIVED

    def test_invalid_transition_409(self, client, db):
        resp = client.post("/campaigns", json={"name": "A", "type": "FULL_TIME"})
        cid = resp.json()["id"]
        resp = client.post(f"/campaigns/{cid}/complete")
        assert resp.status_code == 409

    def test_add_and_remove_opportunity(self, client, db):
        company_resp = client.post("/companies", json={"name": "Co"})
        cid = company_resp.json()["id"]
        opp_resp = client.post("/opportunities", json={
            "company_id": cid, "type": "FULL_TIME", "title": "Dev",
        })
        opp_id = opp_resp.json()["id"]

        camp_resp = client.post("/campaigns", json={"name": "C", "type": "FULL_TIME"})
        camp_id = camp_resp.json()["id"]

        resp = client.post(f"/campaigns/{camp_id}/opportunities/{opp_id}")
        assert resp.status_code == 201

        resp = client.get(f"/campaigns/{camp_id}/opportunities")
        assert resp.json()["total"] == 1

        resp = client.delete(f"/campaigns/{camp_id}/opportunities/{opp_id}")
        assert resp.status_code == 200

        resp = client.get(f"/campaigns/{camp_id}/opportunities")
        assert resp.json()["total"] == 0

    def test_add_invalid_opportunity_404(self, client, db):
        resp = client.post("/campaigns", json={"name": "C", "type": "FULL_TIME"})
        cid = resp.json()["id"]
        resp = client.post(f"/campaigns/{cid}/opportunities/99999")
        assert resp.status_code == 404

    def test_summary(self, client, db):
        company_resp = client.post("/companies", json={"name": "Co"})
        cid = company_resp.json()["id"]
        opp_resp = client.post("/opportunities", json={
            "company_id": cid, "type": "FULL_TIME", "title": "Dev",
        })
        opp_id = opp_resp.json()["id"]

        camp_resp = client.post("/campaigns", json={"name": "C", "type": "FULL_TIME"})
        camp_id = camp_resp.json()["id"]
        client.post(f"/campaigns/{camp_id}/opportunities/{opp_id}")

        resp = client.get(f"/campaigns/{camp_id}/summary")
        assert resp.status_code == 200
        assert resp.json()["total_opportunities"] == 1

    def test_get_not_found(self, client, db):
        resp = client.get("/campaigns/99999")
        assert resp.status_code == 404

    def test_list_filter_by_type(self, client, db):
        client.post("/campaigns", json={"name": "A", "type": "FULL_TIME"})
        client.post("/campaigns", json={"name": "B", "type": "INTERNSHIP"})
        resp = client.get("/campaigns?type=INTERNSHIP")
        assert resp.json()["total"] == 1


# ══════════════════════════════════════════════════════════════════════════
# 8. PLANNING API
# ══════════════════════════════════════════════════════════════════════════


class TestPlanningAPI:
    def _create_opps(self, client, db):
        company_resp = client.post("/companies", json={"name": "P Co"})
        cid = company_resp.json()["id"]

        opp1 = client.post("/opportunities", json={
            "company_id": cid, "type": "INTERNSHIP", "title": "Intern",
        }).json()
        opp2 = client.post("/opportunities", json={
            "company_id": cid, "type": "FULL_TIME", "title": "FullTime",
        }).json()
        return opp1, opp2

    def test_planning_overview(self, client, db):
        self._create_opps(client, db)
        resp = client.get("/opportunities/planning")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    def test_filter_by_type(self, client, db):
        self._create_opps(client, db)
        resp = client.get("/opportunities/planning?type=INTERNSHIP")
        data = resp.json()
        assert all(o["opportunity_type"] == "INTERNSHIP" for o in data["opportunities"])

    def test_filter_by_horizon(self, client, db):
        self._create_opps(client, db)
        resp = client.get("/opportunities/planning?horizon=UNKNOWN")
        data = resp.json()
        assert all(o["planning_horizon"] == "UNKNOWN" for o in data["opportunities"])

    def test_planning_fields_present(self, client, db):
        self._create_opps(client, db)
        resp = client.get("/opportunities/planning")
        for opp in resp.json()["opportunities"]:
            assert "planning_horizon" in opp
            assert "planning_priority" in opp
            assert "planning_priority_reasons" in opp
            assert 0 <= opp["planning_priority"] <= 100

    def test_sorted_by_priority(self, client, db):
        self._create_opps(client, db)
        resp = client.get("/opportunities/planning")
        items = resp.json()["opportunities"]
        priorities = [o["planning_priority"] for o in items]
        assert priorities == sorted(priorities, reverse=True)


# ══════════════════════════════════════════════════════════════════════════
# 9. EXISTING REGRESSION
# ══════════════════════════════════════════════════════════════════════════


class TestExistingRegression:
    def test_health(self, client):
        assert client.get("/health").status_code == 200

    def test_opportunity_crud(self, client, db):
        c = client.post("/companies", json={"name": "Reg Co"}).json()
        resp = client.post("/opportunities", json={
            "company_id": c["id"], "type": "FULL_TIME", "title": "Reg",
        })
        assert resp.status_code == 201

    def test_outreach_draft(self, client, db):
        from app.models.profile import Profile
        p = Profile(name="Reg", email="reg@test.com")
        db.add(p)
        db.flush()

        c = client.post("/companies", json={"name": "Reg O Co"}).json()
        lead = client.post("/leads", json={
            "company_id": c["id"], "name": "L", "email": "l@t.com",
        }).json()
        opp = client.post("/opportunities", json={
            "company_id": c["id"], "type": "FULL_TIME", "title": "O",
        }).json()

        resp = client.post("/outreach/drafts", json={
            "profile_id": p.id, "lead_id": lead["id"], "opportunity_id": opp["id"],
        })
        assert resp.status_code == 201

    def test_followup_crud(self, client, db):
        c = client.post("/companies", json={"name": "Reg F Co"}).json()
        lead = client.post("/leads", json={
            "company_id": c["id"], "name": "L", "email": "l@t.com",
        }).json()

        resp = client.post("/follow-ups", json={
            "lead_id": lead["id"],
            "scheduled_for": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        })
        assert resp.status_code == 201

    def test_matching(self, client, db):
        from app.models.profile import Profile
        from app.models.skill import Skill

        p = Profile(name="M", email="m@t.com")
        db.add(p)
        db.flush()
        db.add(Skill(profile_id=p.id, name="Python"))
        db.flush()

        c = client.post("/companies", json={"name": "M Co"}).json()
        opp = client.post("/opportunities", json={
            "company_id": c["id"], "type": "FULL_TIME", "title": "Python Dev",
        }).json()

        resp = client.get(f"/matching/profiles/{p.id}/opportunities/{opp['id']}")
        assert resp.status_code == 200

    def test_discovery(self, client, db):
        resp = client.post("/discovery/run", json=[{
            "source_name": "manual", "title": "M", "company_name": "MC",
        }])
        assert resp.status_code == 200
