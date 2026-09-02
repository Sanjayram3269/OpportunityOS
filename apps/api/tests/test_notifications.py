"""Comprehensive tests for the Notification / Attention system.

Tests cover:
  - Notification model creation
  - Severity/priority
  - Unread/read behavior
  - Unread count
  - List ordering
  - Read one / Read all
  - 404 behavior
  - Notification sync (idempotent)
  - Duplicate prevention
  - Overdue action notification
  - Due follow-up notification
  - Approaching deadline notification
  - Pending approval notification
  - Ready-to-send notification
  - High-priority opportunity notification
  - Missing/deleted source handling
  - No fabricated deadlines
  - Regression for Action Center, FollowUps, Applications, Dashboard
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.application import Action, Application
from app.models.company import Company
from app.models.followup import FollowUp
from app.models.lead import Lead
from app.models.message import Message
from app.models.notification import (
    NOTIFICATION_APPLICATION_UPDATE,
    NOTIFICATION_DEADLINE_APPROACHING,
    NOTIFICATION_FOLLOW_UP_DUE,
    NOTIFICATION_HIGH_PRIORITY_OPPORTUNITY,
    NOTIFICATION_OUTREACH_PENDING_APPROVAL,
    NOTIFICATION_OUTREACH_READY_TO_SEND,
    NOTIFICATION_OVERDUE_ACTION,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    SEVERITY_LOW,
    Notification,
)
from app.models.opportunity import Opportunity
from app.services.notifications import (
    _generate_deadline_approaching_notifications,
    _generate_followup_due_notifications,
    _generate_high_priority_opportunity_notifications,
    _generate_outreach_pending_approval_notifications,
    _generate_outreach_ready_to_send_notifications,
    _generate_overdue_action_notifications,
    get_unread_count,
    list_notifications,
    mark_all_read,
    mark_read,
    sync_notifications,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_company(db, name="NotifCo"):
    company = Company(name=name)
    db.add(company)
    db.flush()
    return company


def _create_lead(db, company):
    lead = Lead(company_id=company.id, name="Test Lead", email="lead@test.com")
    db.add(lead)
    db.flush()
    return lead


def _create_opportunity(db, company, **kwargs):
    defaults = {
        "type": "INTERNSHIP",
        "title": "Test Opp",
        "status": "DISCOVERED",
        "priority": "MEDIUM",
    }
    defaults.update(kwargs)
    opp = Opportunity(company_id=company.id, **defaults)
    db.add(opp)
    db.flush()
    return opp


def _create_action(db, **kwargs):
    now = datetime.now(timezone.utc)
    defaults = {
        "action_type": "APPLY",
        "priority": "P1",
        "entity_type": "opportunity",
        "entity_id": 1,
        "title": "Test Action",
        "status": "OPEN",
    }
    defaults.update(kwargs)
    if "created_at" not in defaults:
        defaults["created_at"] = now
    if "updated_at" not in defaults:
        defaults["updated_at"] = now
    action = Action(**defaults)
    db.add(action)
    db.flush()
    return action


# ══════════════════════════════════════════════════════════════════════════
# 1. MODEL / CRUD
# ══════════════════════════════════════════════════════════════════════════


class TestNotificationModel:
    def test_create_notification(self, db):
        now = datetime.now(timezone.utc)
        n = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Test notification",
            message="Test message",
            severity=SEVERITY_HIGH,
            source_type="action",
            source_id=1,
            created_at=now,
        )
        db.add(n)
        db.flush()
        assert n.id is not None
        assert n.notification_type == NOTIFICATION_OVERDUE_ACTION
        assert n.severity == SEVERITY_HIGH

    def test_notification_defaults(self, db):
        now = datetime.now(timezone.utc)
        n = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Test",
            severity=SEVERITY_MEDIUM,
            source_type="action",
            source_id=1,
            created_at=now,
        )
        db.add(n)
        db.flush()
        assert n.read_at is None
        assert n.dismissed_at is None
        assert n.due_at is None
        assert n.message is None

    def test_notification_all_types_valid(self, db):
        now = datetime.now(timezone.utc)
        for ntype in [
            NOTIFICATION_OVERDUE_ACTION,
            NOTIFICATION_FOLLOW_UP_DUE,
            NOTIFICATION_DEADLINE_APPROACHING,
            NOTIFICATION_OUTREACH_PENDING_APPROVAL,
            NOTIFICATION_OUTREACH_READY_TO_SEND,
            NOTIFICATION_APPLICATION_UPDATE,
            NOTIFICATION_HIGH_PRIORITY_OPPORTUNITY,
        ]:
            n = Notification(
                notification_type=ntype,
                title=f"Test {ntype}",
                severity=SEVERITY_MEDIUM,
                source_type="test",
                source_id=1,
                created_at=now,
            )
            db.add(n)
        db.flush()


# ══════════════════════════════════════════════════════════════════════════
# 2. UNREAD / READ
# ══════════════════════════════════════════════════════════════════════════


class TestUnreadRead:
    def test_unread_count_empty(self, db):
        assert get_unread_count(db) == 0

    def test_unread_count_with_notifications(self, db):
        now = datetime.now(timezone.utc)
        for i in range(3):
            n = Notification(
                notification_type=NOTIFICATION_OVERDUE_ACTION,
                title=f"Test {i}",
                severity=SEVERITY_MEDIUM,
                source_type="action",
                source_id=i + 1,
                created_at=now,
            )
            db.add(n)
        db.flush()
        assert get_unread_count(db) == 3

    def test_read_notification_not_counted(self, db):
        now = datetime.now(timezone.utc)
        n = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Read me",
            severity=SEVERITY_MEDIUM,
            source_type="action",
            source_id=1,
            created_at=now,
        )
        db.add(n)
        db.flush()
        assert get_unread_count(db) == 1
        mark_read(db, n.id)
        assert get_unread_count(db) == 0

    def test_mark_all_read(self, db):
        now = datetime.now(timezone.utc)
        for i in range(5):
            n = Notification(
                notification_type=NOTIFICATION_OVERDUE_ACTION,
                title=f"Test {i}",
                severity=SEVERITY_MEDIUM,
                source_type="action",
                source_id=i + 1,
                created_at=now,
            )
            db.add(n)
        db.flush()
        assert get_unread_count(db) == 5
        count = mark_all_read(db)
        assert count == 5
        assert get_unread_count(db) == 0

    def test_mark_all_read_idempotent(self, db):
        now = datetime.now(timezone.utc)
        n = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Test",
            severity=SEVERITY_MEDIUM,
            source_type="action",
            source_id=1,
            created_at=now,
        )
        db.add(n)
        db.flush()
        mark_all_read(db)
        count = mark_all_read(db)
        assert count == 0  # Already read

    def test_mark_read_not_found(self, db):
        with pytest.raises(ValueError, match="not found"):
            mark_read(db, 99999)


# ══════════════════════════════════════════════════════════════════════════
# 3. LISTING / ORDERING
# ══════════════════════════════════════════════════════════════════════════


class TestListing:
    def test_list_empty(self, db):
        result = list_notifications(db)
        assert result == []

    def test_list_returns_notifications(self, db):
        now = datetime.now(timezone.utc)
        for i in range(3):
            n = Notification(
                notification_type=NOTIFICATION_OVERDUE_ACTION,
                title=f"Test {i}",
                severity=SEVERITY_MEDIUM,
                source_type="action",
                source_id=i + 1,
                created_at=now,
            )
            db.add(n)
        db.flush()
        result = list_notifications(db)
        assert len(result) == 3

    def test_list_unread_only(self, db):
        now = datetime.now(timezone.utc)
        n1 = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Unread",
            severity=SEVERITY_MEDIUM,
            source_type="action",
            source_id=1,
            created_at=now,
        )
        n2 = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Read",
            severity=SEVERITY_MEDIUM,
            source_type="action",
            source_id=2,
            created_at=now,
            read_at=now,
        )
        db.add(n1)
        db.add(n2)
        db.flush()

        unread = list_notifications(db, unread_only=True)
        assert len(unread) == 1
        assert unread[0].title == "Unread"

    def test_list_by_type(self, db):
        now = datetime.now(timezone.utc)
        n1 = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Overdue",
            severity=SEVERITY_MEDIUM,
            source_type="action",
            source_id=1,
            created_at=now,
        )
        n2 = Notification(
            notification_type=NOTIFICATION_FOLLOW_UP_DUE,
            title="Followup",
            severity=SEVERITY_MEDIUM,
            source_type="followup",
            source_id=1,
            created_at=now,
        )
        db.add(n1)
        db.add(n2)
        db.flush()

        result = list_notifications(db, notification_type=NOTIFICATION_OVERDUE_ACTION)
        assert len(result) == 1
        assert result[0].title == "Overdue"

    def test_list_by_severity(self, db):
        now = datetime.now(timezone.utc)
        n1 = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Critical",
            severity=SEVERITY_CRITICAL,
            source_type="action",
            source_id=1,
            created_at=now,
        )
        n2 = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Low",
            severity=SEVERITY_LOW,
            source_type="action",
            source_id=2,
            created_at=now,
        )
        db.add(n1)
        db.add(n2)
        db.flush()

        result = list_notifications(db, severity=SEVERITY_CRITICAL)
        assert len(result) == 1
        assert result[0].severity == SEVERITY_CRITICAL

    def test_list_limit(self, db):
        now = datetime.now(timezone.utc)
        for i in range(10):
            n = Notification(
                notification_type=NOTIFICATION_OVERDUE_ACTION,
                title=f"Test {i}",
                severity=SEVERITY_MEDIUM,
                source_type="action",
                source_id=i + 1,
                created_at=now,
            )
            db.add(n)
        db.flush()

        result = list_notifications(db, limit=3)
        assert len(result) == 3

    def test_list_excludes_dismissed(self, db):
        now = datetime.now(timezone.utc)
        n = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Dismissed",
            severity=SEVERITY_MEDIUM,
            source_type="action",
            source_id=1,
            created_at=now,
            dismissed_at=now,
        )
        db.add(n)
        db.flush()

        result = list_notifications(db)
        assert len(result) == 0

    def test_list_ordering_unread_first(self, db):
        now = datetime.now(timezone.utc)
        n_read = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Read",
            severity=SEVERITY_LOW,
            source_type="action",
            source_id=1,
            created_at=now,
            read_at=now,
        )
        n_unread = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Unread",
            severity=SEVERITY_LOW,
            source_type="action",
            source_id=2,
            created_at=now,
        )
        db.add(n_read)
        db.add(n_unread)
        db.flush()

        result = list_notifications(db)
        assert result[0].title == "Unread"
        assert result[1].title == "Read"


# ══════════════════════════════════════════════════════════════════════════
# 4. SYNC / GENERATION
# ══════════════════════════════════════════════════════════════════════════


class TestSync:
    def test_sync_empty_database(self, db):
        result = sync_notifications(db)
        assert result["created"] == 0

    def test_sync_idempotent(self, db):
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        _create_opportunity(db, company, match_score=95, priority="HIGH")

        result1 = sync_notifications(db, now=now)
        count1 = result1["created"]
        assert count1 >= 1

        result2 = sync_notifications(db, now=now)
        assert result2["created"] == 0  # No duplicates

    def test_sync_read_notification_not_duplicated(self, db):
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        _create_opportunity(db, company, match_score=95, priority="HIGH")

        sync_notifications(db, now=now)
        assert get_unread_count(db) >= 1

        # Read all
        mark_all_read(db)
        assert get_unread_count(db) == 0

        # Sync again — should not recreate the same notification
        sync_notifications(db, now=now)
        assert get_unread_count(db) == 0


# ══════════════════════════════════════════════════════════════════════════
# 5. SPECIFIC NOTIFICATION TYPES
# ══════════════════════════════════════════════════════════════════════════


class TestOverdueActionNotification:
    def test_overdue_action_generates_notification(self, db):
        now = datetime.now(timezone.utc)
        action = _create_action(
            db,
            due_at=now - timedelta(hours=2),
            status="OPEN",
        )
        count = _generate_overdue_action_notifications(db, now)
        assert count == 1

    def test_future_action_no_notification(self, db):
        now = datetime.now(timezone.utc)
        action = _create_action(
            db,
            due_at=now + timedelta(days=5),
            status="OPEN",
        )
        count = _generate_overdue_action_notifications(db, now)
        assert count == 0

    def test_completed_action_no_notification(self, db):
        now = datetime.now(timezone.utc)
        action = _create_action(
            db,
            due_at=now - timedelta(hours=2),
            status="COMPLETED",
        )
        count = _generate_overdue_action_notifications(db, now)
        assert count == 0

    def test_no_due_date_no_notification(self, db):
        now = datetime.now(timezone.utc)
        action = _create_action(db, status="OPEN")
        count = _generate_overdue_action_notifications(db, now)
        assert count == 0


class TestFollowUpDueNotification:
    def test_due_followup_generates_notification(self, db):
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        lead = _create_lead(db, company)
        fu = FollowUp(
            lead_id=lead.id,
            scheduled_for=now - timedelta(hours=1),
            status="DUE",
        )
        db.add(fu)
        db.flush()

        count = _generate_followup_due_notifications(db, now)
        assert count == 1

    def test_pending_followup_no_notification(self, db):
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        lead = _create_lead(db, company)
        fu = FollowUp(
            lead_id=lead.id,
            scheduled_for=now + timedelta(days=1),
            status="PENDING",
        )
        db.add(fu)
        db.flush()

        count = _generate_followup_due_notifications(db, now)
        assert count == 0


class TestDeadlineApproachingNotification:
    def test_deadline_within_7_days(self, db):
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        _create_opportunity(
            db, company,
            title="Deadline Opp",
            deadline=now + timedelta(days=3),
        )
        count = _generate_deadline_approaching_notifications(db, now)
        assert count == 1

    def test_deadline_beyond_7_days(self, db):
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        _create_opportunity(
            db, company,
            deadline=now + timedelta(days=14),
        )
        count = _generate_deadline_approaching_notifications(db, now)
        assert count == 0

    def test_no_deadline_no_notification(self, db):
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        _create_opportunity(db, company)
        count = _generate_deadline_approaching_notifications(db, now)
        assert count == 0

    def test_created_at_not_used_as_deadline(self, db):
        """created_at should NOT be treated as a deadline."""
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        _create_opportunity(db, company)  # No deadline
        count = _generate_deadline_approaching_notifications(db, now)
        assert count == 0

    def test_past_deadline_not_approaching(self, db):
        """Overdue deadlines should not generate 'approaching' notifications."""
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        _create_opportunity(
            db, company,
            deadline=now - timedelta(days=1),
        )
        count = _generate_deadline_approaching_notifications(db, now)
        assert count == 0

    def test_deep_pipeline_skip(self, db):
        """Opportunities already in interview/final_round should skip."""
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        opp = _create_opportunity(
            db, company,
            deadline=now + timedelta(days=3),
        )
        app = Application(
            opportunity_id=opp.id,
            status="INTERVIEW",
        )
        db.add(app)
        db.flush()

        count = _generate_deadline_approaching_notifications(db, now)
        assert count == 0


class TestOutreachNotifications:
    def test_pending_approval_generates_notification(self, db):
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        lead = _create_lead(db, company)
        msg = Message(
            lead_id=lead.id,
            channel="EMAIL",
            direction="OUTBOUND",
            body="Test message",
            status="PENDING_APPROVAL",
        )
        db.add(msg)
        db.flush()

        count = _generate_outreach_pending_approval_notifications(db, now)
        assert count == 1

    def test_ready_to_send_generates_notification(self, db):
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        lead = _create_lead(db, company)
        msg = Message(
            lead_id=lead.id,
            channel="EMAIL",
            direction="OUTBOUND",
            body="Test message",
            status="READY_TO_SEND",
        )
        db.add(msg)
        db.flush()

        count = _generate_outreach_ready_to_send_notifications(db, now)
        assert count == 1

    def test_draft_no_notification(self, db):
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        lead = _create_lead(db, company)
        msg = Message(
            lead_id=lead.id,
            channel="EMAIL",
            direction="OUTBOUND",
            body="Test message",
            status="DRAFT",
        )
        db.add(msg)
        db.flush()

        count1 = _generate_outreach_pending_approval_notifications(db, now)
        count2 = _generate_outreach_ready_to_send_notifications(db, now)
        assert count1 == 0
        assert count2 == 0


class TestHighPriorityOpportunityNotification:
    def test_high_match_high_priority_generates(self, db):
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        _create_opportunity(db, company, match_score=95, priority="HIGH")
        count = _generate_high_priority_opportunity_notifications(db, now)
        assert count == 1

    def test_already_applied_no_notification(self, db):
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        opp = _create_opportunity(db, company, match_score=95, priority="HIGH")
        app = Application(opportunity_id=opp.id, status="APPLIED")
        db.add(app)
        db.flush()

        count = _generate_high_priority_opportunity_notifications(db, now)
        assert count == 0

    def test_low_match_no_notification(self, db):
        now = datetime.now(timezone.utc)
        company = _create_company(db)
        _create_opportunity(db, company, match_score=50, priority="HIGH")
        count = _generate_high_priority_opportunity_notifications(db, now)
        assert count == 0


# ══════════════════════════════════════════════════════════════════════════
# 6. API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════


class TestNotificationAPI:
    def test_list_empty(self, client, db):
        resp = client.get("/notifications")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_unread_count(self, client, db):
        resp = client.get("/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0

    def test_sync(self, client, db):
        resp = client.post("/notifications/sync")
        assert resp.status_code == 200
        assert "created" in resp.json()

    def test_mark_read(self, client, db):
        now = datetime.now(timezone.utc)
        n = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Test",
            severity=SEVERITY_MEDIUM,
            source_type="action",
            source_id=1,
            created_at=now,
        )
        db.add(n)
        db.flush()

        resp = client.post(f"/notifications/{n.id}/read")
        assert resp.status_code == 200
        assert resp.json()["read_at"] is not None

    def test_mark_read_not_found(self, client, db):
        resp = client.post("/notifications/99999/read")
        assert resp.status_code == 404

    def test_mark_all_read(self, client, db):
        now = datetime.now(timezone.utc)
        for i in range(3):
            n = Notification(
                notification_type=NOTIFICATION_OVERDUE_ACTION,
                title=f"Test {i}",
                severity=SEVERITY_MEDIUM,
                source_type="action",
                source_id=i + 1,
                created_at=now,
            )
            db.add(n)
        db.flush()

        resp = client.post("/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["marked_read"] == 3

    def test_list_with_data(self, client, db):
        now = datetime.now(timezone.utc)
        n = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Overdue test",
            severity=SEVERITY_CRITICAL,
            source_type="action",
            source_id=1,
            created_at=now,
        )
        db.add(n)
        db.flush()

        resp = client.get("/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Overdue test"
        assert data[0]["severity"] == "CRITICAL"

    def test_list_unread_only_filter(self, client, db):
        now = datetime.now(timezone.utc)
        n1 = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Unread",
            severity=SEVERITY_MEDIUM,
            source_type="action",
            source_id=1,
            created_at=now,
        )
        n2 = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Read",
            severity=SEVERITY_MEDIUM,
            source_type="action",
            source_id=2,
            created_at=now,
            read_at=now,
        )
        db.add(n1)
        db.add(n2)
        db.flush()

        resp = client.get("/notifications?unread_only=true")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Unread"

    def test_list_type_filter(self, client, db):
        now = datetime.now(timezone.utc)
        n1 = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Overdue",
            severity=SEVERITY_MEDIUM,
            source_type="action",
            source_id=1,
            created_at=now,
        )
        n2 = Notification(
            notification_type=NOTIFICATION_FOLLOW_UP_DUE,
            title="Followup",
            severity=SEVERITY_MEDIUM,
            source_type="followup",
            source_id=1,
            created_at=now,
        )
        db.add(n1)
        db.add(n2)
        db.flush()

        resp = client.get("/notifications?notification_type=OVERDUE_ACTION")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_severity_filter(self, client, db):
        now = datetime.now(timezone.utc)
        n = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Critical",
            severity=SEVERITY_CRITICAL,
            source_type="action",
            source_id=1,
            created_at=now,
        )
        db.add(n)
        db.flush()

        resp = client.get("/notifications?severity=CRITICAL")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = client.get("/notifications?severity=LOW")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_list_limit(self, client, db):
        now = datetime.now(timezone.utc)
        for i in range(10):
            n = Notification(
                notification_type=NOTIFICATION_OVERDUE_ACTION,
                title=f"Test {i}",
                severity=SEVERITY_MEDIUM,
                source_type="action",
                source_id=i + 1,
                created_at=now,
            )
            db.add(n)
        db.flush()

        resp = client.get("/notifications?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_sync_with_real_data(self, client, db):
        """Test that sync generates notifications from real data."""
        company = _create_company(db)
        lead = _create_lead(db, company)
        opp = _create_opportunity(
            db, company, match_score=95, priority="HIGH",
            deadline=datetime.now(timezone.utc) + timedelta(days=3),
        )

        # Create a due follow-up
        fu = FollowUp(
            lead_id=lead.id,
            opportunity_id=opp.id,
            scheduled_for=datetime.now(timezone.utc) - timedelta(hours=1),
            status="DUE",
        )
        db.add(fu)
        db.flush()

        resp = client.post("/notifications/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] >= 2  # At least high-priority opp + followup

        # Verify unread count increased
        resp = client.get("/notifications/unread-count")
        assert resp.json()["unread_count"] >= 2

    def test_missing_source_does_not_crash(self, client, db):
        """Notification with deleted source should still render."""
        now = datetime.now(timezone.utc)
        n = Notification(
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title="Orphan notification",
            severity=SEVERITY_MEDIUM,
            source_type="action",
            source_id=99999,  # Non-existent
            created_at=now,
        )
        db.add(n)
        db.flush()

        resp = client.get("/notifications")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ══════════════════════════════════════════════════════════════════════════
# 7. REGRESSION
# ══════════════════════════════════════════════════════════════════════════


class TestExistingRegression:
    def test_action_center_still_works(self, client, db):
        resp = client.get("/actions")
        assert resp.status_code == 200

    def test_followups_still_work(self, client, db):
        resp = client.get("/follow-ups")
        assert resp.status_code == 200

    def test_applications_still_work(self, client, db):
        resp = client.get("/applications")
        assert resp.status_code == 200

    def test_dashboard_still_works(self, client, db):
        resp = client.get("/dashboard/overview")
        assert resp.status_code == 200

    def test_analytics_still_works(self, client, db):
        resp = client.get("/analytics/overview")
        assert resp.status_code == 200

    def test_export_still_works(self, client, db):
        resp = client.get("/exports/opportunities.xlsx")
        assert resp.status_code == 200

    def test_health_still_works(self, client, db):
        resp = client.get("/health")
        assert resp.status_code == 200
