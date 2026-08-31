"""Comprehensive tests for Email Delivery + Interaction Recording.

Tests cover:
  1. Email provider abstraction
  2. SMTP provider (mocked)
  3. DeliveryResult model
  4. Send authorization (READY_TO_SEND gate)
  5. Invalid state rejection (DRAFT, PENDING, APPROVED, REJECTED)
  6. Missing recipient email
  7. Missing provider configuration
  8. Provider timeout / failure
  9. Successful send → SENT + Interaction
  10. Failed send → stays READY_TO_SEND
  11. No secrets exposed
  12. API endpoint
  13. Existing outreach regression
  14. Existing matching/AI/discovery/API regression
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.email_provider.base import DeliveryResult, EmailProvider, EmailProviderError
from app.email_provider.smtp_provider import SMTPEmailProvider
from app.models.company import Company
from app.models.interaction import Interaction
from app.models.lead import Lead
from app.models.message import Message
from app.models.opportunity import Opportunity
from app.models.profile import Profile
from app.models.project import Project
from app.models.skill import Skill
from app.services.outreach import (
    APPROVED,
    DRAFT,
    PENDING_APPROVAL,
    READY_TO_SEND,
    REJECTED,
    SENT,
    DraftStateError,
    _get_email_provider,
    approve_draft,
    can_transition,
    generate_draft,
    mark_ready,
    send_message,
    transition_draft,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_test_data(db):
    """Create standard test fixtures."""
    profile = Profile(name="Sanjay", email="sanjay@test.com", headline="Python Engineer")
    db.add(profile)
    db.flush()

    skill = Skill(profile_id=profile.id, name="Python")
    db.add(skill)
    db.flush()

    project = Project(
        profile_id=profile.id,
        name="Django App",
        description="Web app with Django and PostgreSQL",
        technologies="Django, PostgreSQL",
    )
    db.add(project)
    db.flush()

    company = Company(name="TestCorp")
    db.add(company)
    db.flush()

    lead = Lead(
        company_id=company.id,
        name="Jane Smith",
        title="Engineering Manager",
        email="jane@testcorp.com",
        location="Bengaluru",
    )
    db.add(lead)
    db.flush()

    opp = Opportunity(
        company_id=company.id,
        type="FULL_TIME",
        title="Senior Python Developer",
        description="We need Python, Django, and PostgreSQL experience.",
    )
    db.add(opp)
    db.flush()

    return profile, lead, opp, company


def _create_draft_with_status(db, status, lead_email="jane@testcorp.com"):
    """Create a draft and transition it to the given status."""
    profile, lead, opp, _ = _create_test_data(db)

    if lead_email is not None:
        lead.email = lead_email
        db.commit()

    import asyncio
    message = asyncio.run(generate_draft(
        db, profile_id=profile.id, lead_id=lead.id, opportunity_id=opp.id,
    ))

    # Transition to desired status
    transitions = {
        PENDING_APPROVAL: [PENDING_APPROVAL],
        APPROVED: [PENDING_APPROVAL, APPROVED],
        READY_TO_SEND: [PENDING_APPROVAL, APPROVED, READY_TO_SEND],
        SENT: [PENDING_APPROVAL, APPROVED, READY_TO_SEND],
        REJECTED: [REJECTED],
    }

    for target in transitions.get(status, []):
        if status == SENT:
            # For SENT, we only transition to READY_TO_SEND, then send handles the rest
            transition_draft(db, message, target)
        else:
            transition_draft(db, message, target)

    return message, profile, lead, opp


def _mock_email_provider(success=True, error=None, message_id="msg-123"):
    """Create a mock EmailProvider."""
    provider = MagicMock(spec=EmailProvider)
    provider.provider_name = "mock_smtp"

    if success:
        provider.send_email.return_value = DeliveryResult.ok(
            provider="mock_smtp",
            message_id=message_id,
        )
    else:
        provider.send_email.return_value = DeliveryResult.fail(
            provider="mock_smtp",
            error=error or "Connection refused",
        )

    return provider


# ══════════════════════════════════════════════════════════════════════════
# 1. DELIVERY RESULT MODEL
# ══════════════════════════════════════════════════════════════════════════


class TestDeliveryResult:
    def test_ok_result(self):
        result = DeliveryResult.ok(provider="smtp", message_id="abc-123")
        assert result.success is True
        assert result.provider == "smtp"
        assert result.message_id == "abc-123"
        assert result.error is None

    def test_fail_result(self):
        result = DeliveryResult.fail(provider="smtp", error="Connection refused")
        assert result.success is False
        assert result.provider == "smtp"
        assert result.error == "Connection refused"
        assert result.message_id is None

    def test_default_result(self):
        result = DeliveryResult()
        assert result.success is False
        assert result.metadata == {}


# ══════════════════════════════════════════════════════════════════════════
# 2. EMAIL PROVIDER ABSTRACTION
# ══════════════════════════════════════════════════════════════════════════


class TestEmailProviderAbstraction:
    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError):
            EmailProvider()  # type: ignore

    def test_mock_provider_conforms(self):
        provider = _mock_email_provider()
        result = provider.send_email(
            to_address="test@test.com",
            subject="Test",
            body="Hello",
        )
        assert isinstance(result, DeliveryResult)
        assert result.success is True

    def test_provider_name_property(self):
        provider = _mock_email_provider()
        assert provider.provider_name == "mock_smtp"


# ══════════════════════════════════════════════════════════════════════════
# 3. SMTP PROVIDER (MOCKED)
# ══════════════════════════════════════════════════════════════════════════


class TestSMTPProvider:
    def test_provider_name(self):
        provider = SMTPEmailProvider(
            smtp_host="smtp.test.com",
            from_address="sender@test.com",
        )
        assert provider.provider_name == "smtp"

    def test_missing_sender_returns_fail(self):
        provider = SMTPEmailProvider(smtp_host="smtp.test.com")
        result = provider.send_email(
            to_address="recipient@test.com",
            subject="Test",
            body="Hello",
        )
        assert result.success is False
        assert "sender" in result.error.lower()

    def test_missing_recipient_returns_fail(self):
        provider = SMTPEmailProvider(
            smtp_host="smtp.test.com",
            from_address="sender@test.com",
        )
        result = provider.send_email(
            to_address="",
            subject="Test",
            body="Hello",
        )
        assert result.success is False
        assert "recipient" in result.error.lower()

    @patch("app.email_provider.smtp_provider.smtplib.SMTP")
    def test_successful_send(self, MockSMTP):
        mock_server = MagicMock()
        MockSMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
        MockSMTP.return_value.__exit__ = MagicMock(return_value=False)

        provider = SMTPEmailProvider(
            smtp_host="smtp.test.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="pass",
            from_address="sender@test.com",
            from_name="Test Sender",
        )

        result = provider.send_email(
            to_address="recipient@test.com",
            subject="Test Subject",
            body="Hello World",
        )

        assert result.success is True
        assert result.provider == "smtp"
        assert result.message_id is not None
        mock_server.sendmail.assert_called_once()

    @patch("app.email_provider.smtp_provider.smtplib.SMTP")
    def test_smtp_auth_failure(self, MockSMTP):
        import smtplib
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
        MockSMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
        MockSMTP.return_value.__exit__ = MagicMock(return_value=False)

        provider = SMTPEmailProvider(
            smtp_host="smtp.test.com",
            smtp_username="user",
            smtp_password="wrong",
            from_address="sender@test.com",
        )

        result = provider.send_email(
            to_address="recipient@test.com",
            subject="Test",
            body="Hello",
        )

        assert result.success is False
        assert "authentication" in result.error.lower()

    @patch("app.email_provider.smtp_provider.smtplib.SMTP")
    def test_smtp_recipient_refused(self, MockSMTP):
        import smtplib
        mock_server = MagicMock()
        mock_server.sendmail.side_effect = smtplib.SMTPRecipientsRefused(
            {"bad@test.com": (550, b"User unknown")}
        )
        MockSMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
        MockSMTP.return_value.__exit__ = MagicMock(return_value=False)

        provider = SMTPEmailProvider(
            smtp_host="smtp.test.com",
            from_address="sender@test.com",
        )

        result = provider.send_email(
            to_address="bad@test.com",
            subject="Test",
            body="Hello",
        )

        assert result.success is False
        assert "refused" in result.error.lower()

    @patch("app.email_provider.smtp_provider.smtplib.SMTP")
    def test_smtp_timeout(self, MockSMTP):
        MockSMTP.return_value.__enter__ = MagicMock(side_effect=TimeoutError("timed out"))
        MockSMTP.return_value.__exit__ = MagicMock(return_value=False)

        provider = SMTPEmailProvider(
            smtp_host="smtp.test.com",
            from_address="sender@test.com",
            timeout=5,
        )

        result = provider.send_email(
            to_address="recipient@test.com",
            subject="Test",
            body="Hello",
        )

        assert result.success is False
        assert "timed out" in result.error.lower()

    @patch("app.email_provider.smtp_provider.smtplib.SMTP")
    def test_smtp_connection_error(self, MockSMTP):
        MockSMTP.return_value.__enter__ = MagicMock(
            side_effect=ConnectionError("Connection refused")
        )
        MockSMTP.return_value.__exit__ = MagicMock(return_value=False)

        provider = SMTPEmailProvider(
            smtp_host="smtp.test.com",
            from_address="sender@test.com",
        )

        result = provider.send_email(
            to_address="recipient@test.com",
            subject="Test",
            body="Hello",
        )

        assert result.success is False


# ══════════════════════════════════════════════════════════════════════════
# 4. SEND AUTHORIZATION GATE
# ══════════════════════════════════════════════════════════════════════════


class TestSendAuthorization:
    def test_ready_to_send_can_be_sent(self):
        assert can_transition(READY_TO_SEND, SENT) is True

    def test_draft_cannot_be_sent(self):
        assert can_transition(DRAFT, SENT) is False

    def test_pending_cannot_be_sent(self):
        assert can_transition(PENDING_APPROVAL, SENT) is False

    def test_approved_cannot_be_sent(self):
        assert can_transition(APPROVED, SENT) is False

    def test_rejected_cannot_be_sent(self):
        assert can_transition(REJECTED, SENT) is False

    def test_sent_is_terminal(self):
        assert can_transition(SENT, DRAFT) is False
        assert can_transition(SENT, READY_TO_SEND) is False


# ══════════════════════════════════════════════════════════════════════════
# 5. SEND MESSAGE SERVICE
# ══════════════════════════════════════════════════════════════════════════


class TestSendMessageService:
    def test_successful_send(self, db):
        message, _, _, _ = _create_draft_with_status(db, READY_TO_SEND)
        provider = _mock_email_provider(success=True)

        import asyncio
        result = asyncio.run(send_message(db, message, email_provider=provider))

        assert result.success is True
        assert message.status == SENT
        assert message.sent_at is not None

    def test_successful_send_creates_interaction(self, db):
        message, _, lead, _ = _create_draft_with_status(db, READY_TO_SEND)
        provider = _mock_email_provider(success=True, message_id="test-msg-42")

        import asyncio
        asyncio.run(send_message(db, message, email_provider=provider))

        interaction = db.query(Interaction).filter(
            Interaction.message_id == message.id
        ).first()
        assert interaction is not None
        assert interaction.type == "EMAIL_SENT"
        assert interaction.lead_id == lead.id
        assert "jane@testcorp.com" in interaction.content
        meta = interaction.metadata_
        assert meta["provider"] == "mock_smtp"
        assert meta["message_id"] == "test-msg-42"

    def test_failed_send_stays_ready(self, db):
        message, _, _, _ = _create_draft_with_status(db, READY_TO_SEND)
        provider = _mock_email_provider(success=False, error="Connection refused")

        import asyncio
        result = asyncio.run(send_message(db, message, email_provider=provider))

        assert result.success is False
        assert message.status == READY_TO_SEND
        assert message.sent_at is None

    def test_failed_send_no_interaction(self, db):
        message, _, _, _ = _create_draft_with_status(db, READY_TO_SEND)
        provider = _mock_email_provider(success=False)

        import asyncio
        asyncio.run(send_message(db, message, email_provider=provider))

        interaction = db.query(Interaction).filter(
            Interaction.message_id == message.id
        ).first()
        assert interaction is None

    def test_draft_cannot_be_sent(self, db):
        message, _, _, _ = _create_draft_with_status(db, DRAFT)
        provider = _mock_email_provider()

        import asyncio
        with pytest.raises(DraftStateError, match="READY_TO_SEND"):
            asyncio.run(send_message(db, message, email_provider=provider))

    def test_pending_cannot_be_sent(self, db):
        message, _, _, _ = _create_draft_with_status(db, PENDING_APPROVAL)
        provider = _mock_email_provider()

        import asyncio
        with pytest.raises(DraftStateError, match="READY_TO_SEND"):
            asyncio.run(send_message(db, message, email_provider=provider))

    def test_approved_cannot_be_sent(self, db):
        message, _, _, _ = _create_draft_with_status(db, APPROVED)
        provider = _mock_email_provider()

        import asyncio
        with pytest.raises(DraftStateError, match="READY_TO_SEND"):
            asyncio.run(send_message(db, message, email_provider=provider))

    def test_rejected_cannot_be_sent(self, db):
        message, _, _, _ = _create_draft_with_status(db, REJECTED)
        provider = _mock_email_provider()

        import asyncio
        with pytest.raises(DraftStateError, match="READY_TO_SEND"):
            asyncio.run(send_message(db, message, email_provider=provider))

    def test_missing_lead_email(self, db):
        message, _, lead, _ = _create_draft_with_status(db, READY_TO_SEND, lead_email=None)
        lead.email = None
        db.commit()
        provider = _mock_email_provider()

        import asyncio
        result = asyncio.run(send_message(db, message, email_provider=provider))

        assert result.success is False
        assert "email" in result.error.lower()
        assert message.status == READY_TO_SEND

    def test_no_provider_configured(self, db):
        message, _, _, _ = _create_draft_with_status(db, READY_TO_SEND)

        import asyncio
        with patch("app.services.outreach._get_email_provider", return_value=None):
            result = asyncio.run(send_message(db, message))

        assert result.success is False
        assert "not configured" in result.error.lower()
        assert message.status == READY_TO_SEND

    def test_provider_timeout(self, db):
        message, _, _, _ = _create_draft_with_status(db, READY_TO_SEND)
        provider = MagicMock(spec=EmailProvider)
        provider.provider_name = "mock"
        provider.send_email.return_value = DeliveryResult.fail(
            provider="mock", error="Connection timed out (30s)"
        )

        import asyncio
        result = asyncio.run(send_message(db, message, email_provider=provider))

        assert result.success is False
        assert message.status == READY_TO_SEND

    def test_provider_generic_failure(self, db):
        message, _, _, _ = _create_draft_with_status(db, READY_TO_SEND)
        provider = MagicMock(spec=EmailProvider)
        provider.provider_name = "mock"
        provider.send_email.return_value = DeliveryResult.fail(
            provider="mock", error="SMTP error: 421 Service unavailable"
        )

        import asyncio
        result = asyncio.run(send_message(db, message, email_provider=provider))

        assert result.success is False
        assert message.status == READY_TO_SEND

    def test_no_secrets_in_result(self, db):
        """DeliveryResult should never contain credentials."""
        result = DeliveryResult.ok(provider="smtp", message_id="abc")
        result_str = json.dumps({
            "success": result.success,
            "provider": result.provider,
            "message_id": result.message_id,
            "error": result.error,
        })
        assert "password" not in result_str.lower()
        assert "secret" not in result_str.lower()
        assert "token" not in result_str.lower()


# ══════════════════════════════════════════════════════════════════════════
# 6. EMAIL PROVIDER CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════


class TestEmailProviderConfig:
    def test_no_host_returns_none(self):
        with patch("app.services.outreach.get_settings") as mock_settings:
            mock_settings.return_value.email_host = ""
            provider = _get_email_provider()
            assert provider is None

    def test_with_host_returns_provider(self):
        with patch("app.services.outreach.get_settings") as mock_settings:
            mock_settings.return_value.email_host = "smtp.test.com"
            mock_settings.return_value.email_port = 587
            mock_settings.return_value.email_username = "user"
            mock_settings.return_value.email_password = "pass"
            mock_settings.return_value.email_use_tls = True
            mock_settings.return_value.email_from_address = "test@test.com"
            mock_settings.return_value.email_from_name = "Test"
            mock_settings.return_value.email_timeout = 30
            provider = _get_email_provider()
            assert provider is not None
            assert provider.provider_name == "smtp"


# ══════════════════════════════════════════════════════════════════════════
# 7. API ENDPOINT
# ══════════════════════════════════════════════════════════════════════════


class TestSendAPI:
    def _create_ready_draft(self, client, db):
        """Helper to create a draft and transition it to READY_TO_SEND."""
        profile, lead, opp, _ = _create_test_data(db)

        create_resp = client.post("/outreach/drafts", json={
            "profile_id": profile.id,
            "lead_id": lead.id,
            "opportunity_id": opp.id,
        })
        draft_id = create_resp.json()["id"]

        client.post(f"/outreach/drafts/{draft_id}/submit")
        client.post(f"/outreach/drafts/{draft_id}/approve")
        client.post(f"/outreach/drafts/{draft_id}/ready")

        return draft_id

    def test_send_success(self, client, db):
        draft_id = self._create_ready_draft(client, db)

        mock_provider = _mock_email_provider(success=True, message_id="api-msg-1")
        with patch("app.api.routes.outreach.send_message") as mock_send:
            from app.email_provider.base import DeliveryResult
            mock_send.return_value = DeliveryResult.ok(provider="mock", message_id="api-msg-1")
            # Also need to update the message status for the response
            def side_effect(db, msg, email_provider=None):
                msg.status = SENT
                from datetime import datetime, timezone
                msg.sent_at = datetime.now(timezone.utc)
                return DeliveryResult.ok(provider="mock", message_id="api-msg-1")
            mock_send.side_effect = side_effect

            response = client.post(f"/outreach/drafts/{draft_id}/send")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["provider"] == "mock"
        assert data["message_id"] == "api-msg-1"
        assert data["new_status"] == SENT

    def test_send_draft_rejected(self, client, db):
        profile, lead, opp, _ = _create_test_data(db)

        create_resp = client.post("/outreach/drafts", json={
            "profile_id": profile.id,
            "lead_id": lead.id,
            "opportunity_id": opp.id,
        })
        draft_id = create_resp.json()["id"]

        response = client.post(f"/outreach/drafts/{draft_id}/send")
        assert response.status_code == 409

    def test_send_pending_rejected(self, client, db):
        profile, lead, opp, _ = _create_test_data(db)

        create_resp = client.post("/outreach/drafts", json={
            "profile_id": profile.id,
            "lead_id": lead.id,
            "opportunity_id": opp.id,
        })
        draft_id = create_resp.json()["id"]

        client.post(f"/outreach/drafts/{draft_id}/submit")
        response = client.post(f"/outreach/drafts/{draft_id}/send")
        assert response.status_code == 409

    def test_send_approved_rejected(self, client, db):
        profile, lead, opp, _ = _create_test_data(db)

        create_resp = client.post("/outreach/drafts", json={
            "profile_id": profile.id,
            "lead_id": lead.id,
            "opportunity_id": opp.id,
        })
        draft_id = create_resp.json()["id"]

        client.post(f"/outreach/drafts/{draft_id}/submit")
        client.post(f"/outreach/drafts/{draft_id}/approve")
        response = client.post(f"/outreach/drafts/{draft_id}/send")
        assert response.status_code == 409

    def test_send_rejected_draft_rejected(self, client, db):
        profile, lead, opp, _ = _create_test_data(db)

        create_resp = client.post("/outreach/drafts", json={
            "profile_id": profile.id,
            "lead_id": lead.id,
            "opportunity_id": opp.id,
        })
        draft_id = create_resp.json()["id"]

        client.post(f"/outreach/drafts/{draft_id}/reject")
        response = client.post(f"/outreach/drafts/{draft_id}/send")
        assert response.status_code == 409

    def test_send_not_found(self, client, db):
        response = client.post("/outreach/drafts/99999/send")
        assert response.status_code == 404

    def test_send_provider_failure(self, client, db):
        draft_id = self._create_ready_draft(client, db)

        with patch("app.api.routes.outreach.send_message") as mock_send:
            from app.email_provider.base import DeliveryResult
            mock_send.return_value = DeliveryResult.fail(
                provider="mock", error="Connection refused"
            )

            response = client.post(f"/outreach/drafts/{draft_id}/send")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Connection refused"


# ══════════════════════════════════════════════════════════════════════════
# 8. EXISTING OUTREACH REGRESSION
# ══════════════════════════════════════════════════════════════════════════


class TestOutreachRegression:
    def test_draft_lifecycle_still_works(self, client, db):
        """Full lifecycle DRAFT → PENDING → APPROVED → READY still works."""
        profile, lead, opp, _ = _create_test_data(db)

        create_resp = client.post("/outreach/drafts", json={
            "profile_id": profile.id,
            "lead_id": lead.id,
            "opportunity_id": opp.id,
        })
        draft_id = create_resp.json()["id"]
        assert create_resp.json()["status"] == DRAFT

        resp = client.post(f"/outreach/drafts/{draft_id}/submit")
        assert resp.json()["new_status"] == PENDING_APPROVAL

        resp = client.post(f"/outreach/drafts/{draft_id}/approve")
        assert resp.json()["new_status"] == APPROVED

        resp = client.post(f"/outreach/drafts/{draft_id}/ready")
        assert resp.json()["new_status"] == READY_TO_SEND

    def test_reject_from_any_state(self, client, db):
        profile, lead, opp, _ = _create_test_data(db)

        create_resp = client.post("/outreach/drafts", json={
            "profile_id": profile.id,
            "lead_id": lead.id,
            "opportunity_id": opp.id,
        })
        draft_id = create_resp.json()["id"]

        resp = client.post(f"/outreach/drafts/{draft_id}/reject")
        assert resp.json()["new_status"] == REJECTED


# ══════════════════════════════════════════════════════════════════════════
# 9. EXISTING API PRESERVATION
# ══════════════════════════════════════════════════════════════════════════


class TestExistingAPIPreservation:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_opportunity_crud(self, client, db):
        company_resp = client.post("/companies", json={"name": "Delivery Test Co"})
        company_id = company_resp.json()["id"]

        opp_resp = client.post("/opportunities", json={
            "company_id": company_id,
            "type": "FULL_TIME",
            "title": "Delivery CRUD Test",
        })
        assert opp_resp.status_code == 201

    def test_matching_endpoint(self, client, db):
        profile, lead, opp, _ = _create_test_data(db)

        response = client.get(
            f"/matching/profiles/{profile.id}/opportunities/{opp.id}"
        )
        assert response.status_code == 200

    def test_discovery_endpoint(self, client, db):
        raw_item = {
            "source_name": "manual",
            "title": "Manual Entry",
            "company_name": "Manual Co",
        }
        response = client.post("/discovery/run", json=[raw_item])
        assert response.status_code == 200
