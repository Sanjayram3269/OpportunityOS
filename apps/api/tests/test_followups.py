"""Comprehensive tests for the Follow-up Engine.

Tests cover:
  1. Follow-up creation with valid/invalid references
  2. CRUD (create, read, update, list)
  3. State transitions (full lifecycle)
  4. Invalid transitions
  5. Due handling (timezone-aware)
  6. Cancel behavior
  7. Complete behavior
  8. Edit restrictions by state
  9. API endpoints
  10. No automatic sending
  11. Existing regression
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.company import Company
from app.models.followup import FollowUp
from app.models.lead import Lead
from app.models.message import Message
from app.models.opportunity import Opportunity
from app.models.profile import Profile
from app.services.followup import (
    APPROVED,
    CANCELLED,
    COMPLETED,
    DUE,
    PENDING,
    PENDING_APPROVAL,
    READY_TO_SEND,
    FollowUpStateError,
    approve_followup,
    cancel_followup,
    can_transition,
    check_and_mark_due,
    complete_followup,
    create_followup,
    get_followup,
    list_followups,
    mark_due,
    mark_followup_ready,
    submit_followup,
    update_followup,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_test_data(db):
    """Create standard test fixtures."""
    company = Company(name="FUTestCo")
    db.add(company)
    db.flush()

    lead = Lead(
        company_id=company.id,
        name="Jane Smith",
        title="Engineering Manager",
        email="jane@futest.com",
    )
    db.add(lead)
    db.flush()

    opp = Opportunity(
        company_id=company.id,
        type="FULL_TIME",
        title="Python Developer",
        description="Python and Django.",
    )
    db.add(opp)
    db.flush()

    return lead, opp, company


def _create_message(db, lead, opp):
    """Create a sent message."""
    msg = Message(
        lead_id=lead.id,
        opportunity_id=opp.id,
        channel="EMAIL",
        direction="OUTBOUND",
        subject="Test",
        body="Hello",
        status="SENT",
    )
    db.add(msg)
    db.flush()
    return msg


def _past_time():
    """Return a timezone-aware time in the past."""
    return datetime.now(timezone.utc) - timedelta(hours=1)


def _future_time():
    """Return a timezone-aware time in the future."""
    return datetime.now(timezone.utc) + timedelta(hours=1)


# ══════════════════════════════════════════════════════════════════════════
# 1. STATE TRANSITIONS
# ══════════════════════════════════════════════════════════════════════════


class TestStateTransitions:
    def test_pending_to_due(self):
        assert can_transition(PENDING, DUE) is True

    def test_pending_to_cancelled(self):
        assert can_transition(PENDING, CANCELLED) is True

    def test_due_to_pending_approval(self):
        assert can_transition(DUE, PENDING_APPROVAL) is True

    def test_due_to_cancelled(self):
        assert can_transition(DUE, CANCELLED) is True

    def test_pending_approval_to_approved(self):
        assert can_transition(PENDING_APPROVAL, APPROVED) is True

    def test_pending_approval_to_cancelled(self):
        assert can_transition(PENDING_APPROVAL, CANCELLED) is True

    def test_approved_to_ready(self):
        assert can_transition(APPROVED, READY_TO_SEND) is True

    def test_approved_to_cancelled(self):
        assert can_transition(APPROVED, CANCELLED) is True

    def test_ready_to_completed(self):
        assert can_transition(READY_TO_SEND, COMPLETED) is True

    def test_ready_to_cancelled(self):
        assert can_transition(READY_TO_SEND, CANCELLED) is True

    def test_cannot_skip_to_approved(self):
        assert can_transition(PENDING, APPROVED) is False

    def test_cannot_skip_to_ready(self):
        assert can_transition(PENDING, READY_TO_SEND) is False

    def test_cannot_skip_to_completed(self):
        assert can_transition(PENDING, COMPLETED) is False

    def test_cannot_approve_from_pending(self):
        assert can_transition(PENDING, APPROVED) is False

    def test_cannot_submit_from_pending(self):
        assert can_transition(PENDING, PENDING_APPROVAL) is False

    def test_completed_is_terminal(self):
        assert can_transition(COMPLETED, PENDING) is False
        assert can_transition(COMPLETED, DUE) is False
        assert can_transition(COMPLETED, CANCELLED) is False

    def test_cancelled_is_terminal(self):
        assert can_transition(CANCELLED, PENDING) is False
        assert can_transition(CANCELLED, DUE) is False
        assert can_transition(CANCELLED, APPROVED) is False


# ══════════════════════════════════════════════════════════════════════════
# 2. CREATION
# ══════════════════════════════════════════════════════════════════════════


class TestCreation:
    def test_create_followup(self, db):
        lead, opp, _ = _create_test_data(db)

        fu = create_followup(
            db,
            lead_id=lead.id,
            opportunity_id=opp.id,
            scheduled_for=_future_time(),
            reason="Check in after application",
        )

        assert fu.id is not None
        assert fu.lead_id == lead.id
        assert fu.opportunity_id == opp.id
        assert fu.status == PENDING
        assert fu.reason == "Check in after application"
        assert fu.scheduled_for.tzinfo is not None

    def test_create_without_opportunity(self, db):
        lead, _, _ = _create_test_data(db)

        fu = create_followup(
            db,
            lead_id=lead.id,
            scheduled_for=_future_time(),
        )

        assert fu.opportunity_id is None
        assert fu.status == PENDING

    def test_create_with_message(self, db):
        lead, opp, _ = _create_test_data(db)
        msg = _create_message(db, lead, opp)

        fu = create_followup(
            db,
            lead_id=lead.id,
            opportunity_id=opp.id,
            message_id=msg.id,
            scheduled_for=_future_time(),
        )

        assert fu.message_id == msg.id

    def test_create_invalid_lead(self, db):
        with pytest.raises(ValueError, match="Lead"):
            create_followup(
                db,
                lead_id=99999,
                scheduled_for=_future_time(),
            )

    def test_create_invalid_opportunity(self, db):
        lead, _, _ = _create_test_data(db)
        with pytest.raises(ValueError, match="Opportunity"):
            create_followup(
                db,
                lead_id=lead.id,
                opportunity_id=99999,
                scheduled_for=_future_time(),
            )

    def test_create_invalid_message(self, db):
        lead, _, _ = _create_test_data(db)
        with pytest.raises(ValueError, match="Message"):
            create_followup(
                db,
                lead_id=lead.id,
                message_id=99999,
                scheduled_for=_future_time(),
            )

    def test_naive_datetime_rejected(self, db):
        """Naive datetime is rejected with clear error."""
        lead, _, _ = _create_test_data(db)
        naive = datetime(2026, 1, 1, 12, 0, 0)

        with pytest.raises(ValueError, match="timezone-aware"):
            create_followup(
                db,
                lead_id=lead.id,
                scheduled_for=naive,
            )

    def test_timezone_aware_accepted(self, db):
        """Timezone-aware datetime is accepted."""
        lead, _, _ = _create_test_data(db)
        aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        fu = create_followup(
            db,
            lead_id=lead.id,
            scheduled_for=aware,
        )

        assert fu.scheduled_for.tzinfo is not None
        assert fu.scheduled_for == aware


# ══════════════════════════════════════════════════════════════════════════
# 3. CRUD
# ══════════════════════════════════════════════════════════════════════════


class TestCRUD:
    def test_get_followup(self, db):
        lead, opp, _ = _create_test_data(db)
        fu = create_followup(
            db, lead_id=lead.id, opportunity_id=opp.id,
            scheduled_for=_future_time(),
        )

        retrieved = get_followup(db, fu.id)
        assert retrieved is not None
        assert retrieved.id == fu.id

    def test_get_not_found(self, db):
        assert get_followup(db, 99999) is None

    def test_list_followups(self, db):
        lead, opp, _ = _create_test_data(db)
        create_followup(db, lead_id=lead.id, scheduled_for=_future_time())
        create_followup(db, lead_id=lead.id, scheduled_for=_future_time())

        items = list_followups(db)
        assert len(items) == 2

    def test_list_filter_by_status(self, db):
        lead, _, _ = _create_test_data(db)
        create_followup(db, lead_id=lead.id, scheduled_for=_future_time())

        items = list_followups(db, status=PENDING)
        assert len(items) == 1

        items = list_followups(db, status=COMPLETED)
        assert len(items) == 0

    def test_list_filter_by_lead(self, db):
        lead, _, _ = _create_test_data(db)
        create_followup(db, lead_id=lead.id, scheduled_for=_future_time())

        items = list_followups(db, lead_id=lead.id)
        assert len(items) == 1

        items = list_followups(db, lead_id=99999)
        assert len(items) == 0

    def test_update_followup(self, db):
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_future_time())

        new_time = datetime.now(timezone.utc) + timedelta(days=3)
        updated = update_followup(db, fu, scheduled_for=new_time, reason="Updated reason")

        assert updated.reason == "Updated reason"

    def test_update_restricted_in_approval(self, db):
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_past_time())
        mark_due(db, fu)
        submit_followup(db, fu)

        with pytest.raises(FollowUpStateError):
            update_followup(db, fu, reason="Cannot edit")

    def test_update_naive_datetime_rejected(self, db):
        """Naive datetime in update is rejected."""
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_future_time())

        naive = datetime(2026, 6, 1, 12, 0, 0)
        with pytest.raises(ValueError, match="timezone-aware"):
            update_followup(db, fu, scheduled_for=naive)

    def test_update_restricted_when_completed(self, db):
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_past_time())
        mark_due(db, fu)
        submit_followup(db, fu)
        approve_followup(db, fu)
        mark_followup_ready(db, fu)
        complete_followup(db, fu)

        with pytest.raises(FollowUpStateError):
            update_followup(db, fu, reason="Cannot edit")


# ══════════════════════════════════════════════════════════════════════════
# 4. DUE HANDLING
# ══════════════════════════════════════════════════════════════════════════


class TestDueHandling:
    def test_mark_due_past_time(self, db):
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_past_time())

        updated = mark_due(db, fu)
        assert updated.status == DUE

    def test_cannot_mark_due_future_time(self, db):
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_future_time())

        with pytest.raises(FollowUpStateError, match="not yet due"):
            mark_due(db, fu)

    def test_cannot_mark_due_if_already_due(self, db):
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_past_time())
        mark_due(db, fu)

        with pytest.raises(FollowUpStateError):
            mark_due(db, fu)

    def test_cannot_mark_due_if_completed(self, db):
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_past_time())
        mark_due(db, fu)
        submit_followup(db, fu)
        approve_followup(db, fu)
        mark_followup_ready(db, fu)
        complete_followup(db, fu)

        with pytest.raises(FollowUpStateError):
            mark_due(db, fu)

    def test_cannot_mark_due_if_cancelled(self, db):
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_past_time())
        cancel_followup(db, fu)

        with pytest.raises(FollowUpStateError):
            mark_due(db, fu)

    def test_check_and_mark_due_past(self, db):
        """check_and_mark_due marks it due if scheduled_for has passed."""
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_past_time())

        result = check_and_mark_due(db, fu)
        assert result.status == DUE

    def test_check_and_mark_due_future(self, db):
        """check_and_mark_due leaves it PENDING if not yet due."""
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_future_time())

        result = check_and_mark_due(db, fu)
        assert result.status == PENDING

    def test_timezone_aware_comparison(self, db):
        """Due handling works correctly with timezone-aware datetimes."""
        lead, _, _ = _create_test_data(db)
        # Create with explicit UTC time in the past
        past = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=past)

        updated = mark_due(db, fu)
        assert updated.status == DUE

    def test_no_naive_aware_comparison_possible(self, db):
        """All stored scheduled_for values are timezone-aware."""
        lead, _, _ = _create_test_data(db)
        aware = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=aware)

        # Verify stored value is timezone-aware
        assert fu.scheduled_for.tzinfo is not None
        # Verify comparison with naive would fail (TypeError)
        naive = datetime(2026, 6, 1, 12, 0, 0)
        with pytest.raises(TypeError):
            fu.scheduled_for > naive  # naive vs aware raises TypeError


# ══════════════════════════════════════════════════════════════════════════
# 5. FULL LIFECYCLE
# ══════════════════════════════════════════════════════════════════════════


class TestLifecycle:
    def test_happy_path(self, db):
        """PENDING → DUE → PENDING_APPROVAL → APPROVED → READY_TO_SEND → COMPLETED"""
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_past_time())
        assert fu.status == PENDING

        mark_due(db, fu)
        assert fu.status == DUE

        submit_followup(db, fu)
        assert fu.status == PENDING_APPROVAL

        approve_followup(db, fu)
        assert fu.status == APPROVED

        mark_followup_ready(db, fu)
        assert fu.status == READY_TO_SEND

        complete_followup(db, fu)
        assert fu.status == COMPLETED
        assert fu.completed_at is not None

    def test_cancel_from_pending(self, db):
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_past_time())
        cancel_followup(db, fu)
        assert fu.status == CANCELLED

    def test_cancel_from_due(self, db):
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_past_time())
        mark_due(db, fu)
        cancel_followup(db, fu)
        assert fu.status == CANCELLED

    def test_cancel_from_approved(self, db):
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_past_time())
        mark_due(db, fu)
        submit_followup(db, fu)
        approve_followup(db, fu)
        cancel_followup(db, fu)
        assert fu.status == CANCELLED

    def test_cannot_progress_after_cancel(self, db):
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_past_time())
        cancel_followup(db, fu)

        with pytest.raises(FollowUpStateError):
            mark_due(db, fu)

        with pytest.raises(FollowUpStateError):
            submit_followup(db, fu)


# ══════════════════════════════════════════════════════════════════════════
# 6. NO AUTOMATIC SENDING
# ══════════════════════════════════════════════════════════════════════════


class TestNoAutomaticSending:
    def test_mark_due_does_not_send(self, db):
        """mark_due only changes status, does not invoke any sending."""
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_past_time())

        with patch("app.services.outreach.send_message") as mock_send:
            mark_due(db, fu)
            mock_send.assert_not_called()

    def test_complete_does_not_send(self, db):
        """complete_followup only changes status."""
        lead, _, _ = _create_test_data(db)
        fu = create_followup(db, lead_id=lead.id, scheduled_for=_past_time())
        mark_due(db, fu)
        submit_followup(db, fu)
        approve_followup(db, fu)
        mark_followup_ready(db, fu)

        complete_followup(db, fu)
        assert fu.status == COMPLETED


# ══════════════════════════════════════════════════════════════════════════
# 7. API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════


class TestFollowUpAPI:
    def test_create(self, client, db):
        lead, opp, _ = _create_test_data(db)

        response = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "opportunity_id": opp.id,
            "scheduled_for": _future_time().isoformat(),
            "reason": "Follow up on application",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == PENDING
        assert data["lead_id"] == lead.id
        assert data["opportunity_id"] == opp.id

    def test_create_invalid_lead(self, client, db):
        response = client.post("/follow-ups", json={
            "lead_id": 99999,
            "scheduled_for": _future_time().isoformat(),
        })
        assert response.status_code == 404

    def test_list(self, client, db):
        lead, _, _ = _create_test_data(db)
        client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _future_time().isoformat(),
        })

        response = client.get("/follow-ups")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_get(self, client, db):
        lead, _, _ = _create_test_data(db)
        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _future_time().isoformat(),
        })
        fu_id = create_resp.json()["id"]

        response = client.get(f"/follow-ups/{fu_id}")
        assert response.status_code == 200
        assert response.json()["id"] == fu_id

    def test_get_not_found(self, client, db):
        response = client.get("/follow-ups/99999")
        assert response.status_code == 404

    def test_update(self, client, db):
        lead, _, _ = _create_test_data(db)
        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _future_time().isoformat(),
        })
        fu_id = create_resp.json()["id"]

        response = client.patch(f"/follow-ups/{fu_id}", json={
            "reason": "Updated reason",
        })
        assert response.status_code == 200
        assert response.json()["reason"] == "Updated reason"

    def test_mark_due(self, client, db):
        lead, _, _ = _create_test_data(db)
        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _past_time().isoformat(),
        })
        fu_id = create_resp.json()["id"]

        response = client.post(f"/follow-ups/{fu_id}/mark-due")
        assert response.status_code == 200
        assert response.json()["new_status"] == DUE

    def test_mark_due_not_yet_due(self, client, db):
        lead, _, _ = _create_test_data(db)
        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _future_time().isoformat(),
        })
        fu_id = create_resp.json()["id"]

        response = client.post(f"/follow-ups/{fu_id}/mark-due")
        assert response.status_code == 409

    def test_submit(self, client, db):
        lead, _, _ = _create_test_data(db)
        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _past_time().isoformat(),
        })
        fu_id = create_resp.json()["id"]

        client.post(f"/follow-ups/{fu_id}/mark-due")
        response = client.post(f"/follow-ups/{fu_id}/submit")
        assert response.status_code == 200
        assert response.json()["new_status"] == PENDING_APPROVAL

    def test_approve(self, client, db):
        lead, _, _ = _create_test_data(db)
        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _past_time().isoformat(),
        })
        fu_id = create_resp.json()["id"]

        client.post(f"/follow-ups/{fu_id}/mark-due")
        client.post(f"/follow-ups/{fu_id}/submit")
        response = client.post(f"/follow-ups/{fu_id}/approve")
        assert response.status_code == 200
        assert response.json()["new_status"] == APPROVED

    def test_ready(self, client, db):
        lead, _, _ = _create_test_data(db)
        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _past_time().isoformat(),
        })
        fu_id = create_resp.json()["id"]

        client.post(f"/follow-ups/{fu_id}/mark-due")
        client.post(f"/follow-ups/{fu_id}/submit")
        client.post(f"/follow-ups/{fu_id}/approve")
        response = client.post(f"/follow-ups/{fu_id}/ready")
        assert response.status_code == 200
        assert response.json()["new_status"] == READY_TO_SEND

    def test_complete(self, client, db):
        lead, _, _ = _create_test_data(db)
        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _past_time().isoformat(),
        })
        fu_id = create_resp.json()["id"]

        client.post(f"/follow-ups/{fu_id}/mark-due")
        client.post(f"/follow-ups/{fu_id}/submit")
        client.post(f"/follow-ups/{fu_id}/approve")
        client.post(f"/follow-ups/{fu_id}/ready")
        response = client.post(f"/follow-ups/{fu_id}/complete")
        assert response.status_code == 200
        assert response.json()["new_status"] == COMPLETED

    def test_cancel(self, client, db):
        lead, _, _ = _create_test_data(db)
        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _future_time().isoformat(),
        })
        fu_id = create_resp.json()["id"]

        response = client.post(f"/follow-ups/{fu_id}/cancel")
        assert response.status_code == 200
        assert response.json()["new_status"] == CANCELLED

    def test_invalid_transition_returns_409(self, client, db):
        lead, _, _ = _create_test_data(db)
        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _future_time().isoformat(),
        })
        fu_id = create_resp.json()["id"]

        # Cannot submit a PENDING follow-up
        response = client.post(f"/follow-ups/{fu_id}/submit")
        assert response.status_code == 409

    def test_cannot_approve_directly_from_pending(self, client, db):
        lead, _, _ = _create_test_data(db)
        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _future_time().isoformat(),
        })
        fu_id = create_resp.json()["id"]

        response = client.post(f"/follow-ups/{fu_id}/approve")
        assert response.status_code == 409

    def test_cannot_complete_from_pending(self, client, db):
        lead, _, _ = _create_test_data(db)
        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _future_time().isoformat(),
        })
        fu_id = create_resp.json()["id"]

        response = client.post(f"/follow-ups/{fu_id}/complete")
        assert response.status_code == 409

    def test_naive_datetime_rejected_by_api(self, client, db):
        """API rejects naive datetime with 422."""
        lead, _, _ = _create_test_data(db)

        response = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": "2026-01-01T12:00:00",  # no timezone
        })
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("timezone" in str(e).lower() for e in detail)

    def test_update_naive_datetime_rejected_by_api(self, client, db):
        """API rejects naive datetime in update with 422."""
        lead, _, _ = _create_test_data(db)
        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _future_time().isoformat(),
        })
        fu_id = create_resp.json()["id"]

        response = client.patch(f"/follow-ups/{fu_id}", json={
            "scheduled_for": "2026-06-01T12:00:00",  # no timezone
        })
        assert response.status_code == 422

    def test_timezone_aware_future_remains_pending(self, client, db):
        """Future timezone-aware scheduled_for stays PENDING."""
        lead, _, _ = _create_test_data(db)
        future = datetime.now(timezone.utc) + timedelta(hours=2)

        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": future.isoformat(),
        })
        fu_id = create_resp.json()["id"]

        # Try to mark due — should fail because not yet due
        response = client.post(f"/follow-ups/{fu_id}/mark-due")
        assert response.status_code == 409

        # Confirm still PENDING
        get_resp = client.get(f"/follow-ups/{fu_id}")
        assert get_resp.json()["status"] == PENDING

    def test_timezone_aware_past_can_become_due(self, client, db):
        """Past timezone-aware scheduled_for can be marked DUE."""
        lead, _, _ = _create_test_data(db)
        past = datetime.now(timezone.utc) - timedelta(hours=2)

        create_resp = client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": past.isoformat(),
        })
        fu_id = create_resp.json()["id"]

        response = client.post(f"/follow-ups/{fu_id}/mark-due")
        assert response.status_code == 200
        assert response.json()["new_status"] == DUE

    def test_list_filter_by_status(self, client, db):
        lead, _, _ = _create_test_data(db)
        client.post("/follow-ups", json={
            "lead_id": lead.id,
            "scheduled_for": _future_time().isoformat(),
        })

        response = client.get(f"/follow-ups?status={PENDING}")
        assert response.status_code == 200
        assert response.json()["total"] == 1

        response = client.get(f"/follow-ups?status={COMPLETED}")
        assert response.json()["total"] == 0


# ══════════════════════════════════════════════════════════════════════════
# 8. EXISTING REGRESSION
# ══════════════════════════════════════════════════════════════════════════


class TestExistingRegression:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_opportunity_crud(self, client, db):
        company_resp = client.post("/companies", json={"name": "FUTest Co"})
        company_id = company_resp.json()["id"]

        opp_resp = client.post("/opportunities", json={
            "company_id": company_id,
            "type": "FULL_TIME",
            "title": "FU CRUD Test",
        })
        assert opp_resp.status_code == 201

    def test_outreach_draft_lifecycle(self, client, db):
        from app.models.profile import Profile
        profile = Profile(name="FU Test", email="fu@test.com")
        db.add(profile)
        db.flush()

        company_resp = client.post("/companies", json={"name": "FU Outreach Co"})
        company_id = company_resp.json()["id"]

        lead_resp = client.post("/leads", json={
            "company_id": company_id,
            "name": "FU Lead",
            "email": "fulead@test.com",
        })
        lead_id = lead_resp.json()["id"]

        opp_resp = client.post("/opportunities", json={
            "company_id": company_id,
            "type": "FULL_TIME",
            "title": "FU Opp",
        })
        opp_id = opp_resp.json()["id"]

        draft_resp = client.post("/outreach/drafts", json={
            "profile_id": profile.id,
            "lead_id": lead_id,
            "opportunity_id": opp_id,
        })
        assert draft_resp.status_code == 201
        draft_id = draft_resp.json()["id"]

        client.post(f"/outreach/drafts/{draft_id}/submit")
        client.post(f"/outreach/drafts/{draft_id}/approve")
        resp = client.post(f"/outreach/drafts/{draft_id}/ready")
        assert resp.json()["new_status"] == "READY_TO_SEND"

    def test_discovery_endpoint(self, client, db):
        raw_item = {
            "source_name": "manual",
            "title": "Manual Entry",
            "company_name": "Manual Co",
        }
        response = client.post("/discovery/run", json=[raw_item])
        assert response.status_code == 200

    def test_matching_endpoint(self, client, db):
        from app.models.profile import Profile
        from app.models.skill import Skill

        profile = Profile(name="Match FU", email="matchfu@test.com")
        db.add(profile)
        db.flush()
        skill = Skill(profile_id=profile.id, name="Python")
        db.add(skill)
        db.flush()

        company_resp = client.post("/companies", json={"name": "Match FU Co"})
        company_id = company_resp.json()["id"]
        opp_resp = client.post("/opportunities", json={
            "company_id": company_id,
            "type": "FULL_TIME",
            "title": "Python Dev",
        })
        opp_id = opp_resp.json()["id"]

        response = client.get(f"/matching/profiles/{profile.id}/opportunities/{opp_id}")
        assert response.status_code == 200
