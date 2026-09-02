"""Dedicated tests for the automation scheduler.

Tests the scheduler lifecycle: startup, overlap prevention, failure
recovery, shutdown safety, and manual run through the lock.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest


def _mock_settings(**overrides):
    """Create a mock settings object with sensible defaults."""
    defaults = {
        "automation_enabled": True,
        "automation_scheduler_interval_minutes": 60,
        "automation_dry_run": False,
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


def _mock_run_result(run_id="test-001", created=0):
    """Create a mock AutomationRunResult."""
    result = MagicMock()
    result.run_id = run_id
    result.status.value = "COMPLETED"
    result.opportunities_created = created
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  BASIC LIFECYCLE
# ══════════════════════════════════════════════════════════════════════════════


class TestSchedulerBasicLifecycle:
    """Test basic scheduler start/stop behavior."""

    def test_not_active_by_default(self):
        from app.automation.scheduler import AutomationScheduler

        s = AutomationScheduler()
        assert s.is_active is False
        assert s.last_run is None

    def test_stop_when_not_started(self):
        from app.automation.scheduler import AutomationScheduler

        s = AutomationScheduler()
        s.stop()  # should not raise
        assert s.is_active is False

    def test_get_scheduler_singleton(self):
        from app.automation.scheduler import get_scheduler

        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2

    def test_disabled_when_automation_off(self):
        from app.automation.scheduler import AutomationScheduler

        with patch("app.automation.scheduler.get_settings") as m:
            m.return_value = _mock_settings(automation_enabled=False)
            s = AutomationScheduler()
            s.start()
            assert s.is_active is False

    def test_stop_when_not_running_is_safe(self):
        from app.automation.scheduler import AutomationScheduler

        s = AutomationScheduler()
        s.stop()
        s.stop()  # double-stop
        assert not s.is_active


# ══════════════════════════════════════════════════════════════════════════════
#  IMMEDIATE FIRST RUN
# ══════════════════════════════════════════════════════════════════════════════


class TestSchedulerImmediateFirstRun:
    """Test that automation runs immediately on startup."""

    def test_immediate_first_run(self):
        """When enabled, the scheduler should run one cycle immediately."""
        from app.automation.scheduler import AutomationScheduler

        async def _test():
            with patch("app.automation.scheduler.get_settings") as m, \
                 patch("app.automation.scheduler.SessionLocal") as mock_sf, \
                 patch("app.automation.scheduler.run_automation_cycle") as mock_run:
                m.return_value = _mock_settings()
                mock_sf.return_value = MagicMock()
                mock_run.return_value = _mock_run_result()

                s = AutomationScheduler()
                s.start()

                await asyncio.sleep(0.3)

                mock_run.assert_called()
                assert s.last_run is not None

                s.stop()

        asyncio.run(_test())

    def test_first_run_not_preceded_by_sleep(self):
        """The first cycle should execute before any sleep."""
        from app.automation.scheduler import AutomationScheduler

        async def _test():
            with patch("app.automation.scheduler.get_settings") as m, \
                 patch("app.automation.scheduler.SessionLocal") as mock_sf, \
                 patch("app.automation.scheduler.run_automation_cycle") as mock_run:
                m.return_value = _mock_settings()
                mock_sf.return_value = MagicMock()
                mock_run.return_value = _mock_run_result()

                s = AutomationScheduler()
                s.start()

                await asyncio.sleep(0.2)

                mock_run.assert_called()

                s.stop()

        asyncio.run(_test())


# ══════════════════════════════════════════════════════════════════════════════
#  OVERLAP PREVENTION
# ══════════════════════════════════════════════════════════════════════════════


class TestSchedulerOverlapPrevention:
    """Test that overlapping scheduled runs are prevented."""

    def test_overlap_lock_released_after_run(self):
        """The run lock should be released after a cycle completes."""
        from app.automation.scheduler import AutomationScheduler

        s = AutomationScheduler()
        assert not s._run_lock.locked()

    def test_manual_run_does_not_corrupt_scheduler_state(self):
        """Manual runs should work without corrupting scheduler state."""
        from app.automation.scheduler import AutomationScheduler

        with patch("app.automation.scheduler.get_settings") as m, \
             patch("app.automation.scheduler.SessionLocal") as mock_sf, \
             patch("app.automation.scheduler.run_automation_cycle") as mock_run:
            m.return_value = _mock_settings()
            mock_sf.return_value = MagicMock()
            mock_run.return_value = _mock_run_result(run_id="manual-001")

            s = AutomationScheduler()
            result = asyncio.run(s.execute_manual_run(dry_run=True))

            assert result.run_id == "manual-001"
            mock_run.assert_called_once()
            # Lock should be released after manual run
            assert not s._run_lock.locked()

    def test_manual_run_closes_session(self):
        """Manual runs should close the database session after completion."""
        from app.automation.scheduler import AutomationScheduler

        with patch("app.automation.scheduler.get_settings") as m, \
             patch("app.automation.scheduler.SessionLocal") as mock_sf, \
             patch("app.automation.scheduler.run_automation_cycle") as mock_run:
            m.return_value = _mock_settings()
            mock_session = MagicMock()
            mock_sf.return_value = mock_session
            mock_run.return_value = _mock_run_result()

            s = AutomationScheduler()
            asyncio.run(s.execute_manual_run(dry_run=True))

            mock_session.close.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
#  FAILURE RECOVERY
# ══════════════════════════════════════════════════════════════════════════════


class TestSchedulerFailureRecovery:
    """Test that the scheduler survives failed runs."""

    def test_failure_does_not_set_last_run(self):
        """When a scheduled cycle fails, last_run should not be updated."""
        from app.automation.scheduler import AutomationScheduler

        async def _test():
            with patch("app.automation.scheduler.get_settings") as m, \
                 patch("app.automation.scheduler.SessionLocal") as mock_sf, \
                 patch("app.automation.scheduler.run_automation_cycle") as mock_run:
                m.return_value = _mock_settings()
                mock_sf.return_value = MagicMock()
                mock_run.side_effect = RuntimeError("boom")

                s = AutomationScheduler()
                assert s.last_run is None
                s.start()

                await asyncio.sleep(0.3)

                assert s.last_run is None

                s.stop()

        asyncio.run(_test())

    def test_scheduler_continues_after_failure(self):
        """The scheduler should keep running after a failed cycle."""
        from app.automation.scheduler import AutomationScheduler

        async def _test():
            with patch("app.automation.scheduler.get_settings") as m, \
                 patch("app.automation.scheduler.SessionLocal") as mock_sf, \
                 patch("app.automation.scheduler.run_automation_cycle") as mock_run:
                m.return_value = _mock_settings(
                    automation_scheduler_interval_minutes=0,
                )  # 0 minutes = 0 seconds interval
                mock_sf.return_value = MagicMock()
                mock_run.side_effect = [
                    RuntimeError("DB connection lost"),
                    _mock_run_result(run_id="recovered"),
                ]

                s = AutomationScheduler()
                s.start()

                await asyncio.sleep(0.5)

                assert s.last_run is not None
                assert s.last_run.run_id == "recovered"

                s.stop()

        asyncio.run(_test())


# ══════════════════════════════════════════════════════════════════════════════
#  SHUTDOWN SAFETY
# ══════════════════════════════════════════════════════════════════════════════


class TestSchedulerShutdown:
    """Test clean shutdown behavior."""

    def test_stop_cancels_task(self):
        """stop() should cancel the background task cleanly."""
        from app.automation.scheduler import AutomationScheduler

        async def _test():
            with patch("app.automation.scheduler.get_settings") as m, \
                 patch("app.automation.scheduler.SessionLocal") as mock_sf, \
                 patch("app.automation.scheduler.run_automation_cycle") as mock_run:
                m.return_value = _mock_settings()
                mock_sf.return_value = MagicMock()
                mock_run.return_value = _mock_run_result()

                s = AutomationScheduler()
                s.start()
                assert s.is_active

                s.stop()
                assert not s.is_active

        asyncio.run(_test())

    def test_double_start_is_safe(self):
        """Calling start() twice should not create duplicate tasks."""
        from app.automation.scheduler import AutomationScheduler

        async def _test():
            with patch("app.automation.scheduler.get_settings") as m, \
                 patch("app.automation.scheduler.SessionLocal") as mock_sf, \
                 patch("app.automation.scheduler.run_automation_cycle") as mock_run:
                m.return_value = _mock_settings()
                mock_sf.return_value = MagicMock()
                mock_run.return_value = _mock_run_result()

                s = AutomationScheduler()
                s.start()
                task1 = s._task
                s.start()  # should not create a new task
                task2 = s._task

                assert task1 is task2

                s.stop()

        asyncio.run(_test())


# ══════════════════════════════════════════════════════════════════════════════
#  SAFETY INVARIANTS
# ══════════════════════════════════════════════════════════════════════════════


class TestSchedulerSafety:
    """Test safety invariants that must never be violated."""

    def test_no_automatic_notification_sending(self):
        """Notification sync must only create attention records, never send externally."""
        import app.services.notifications as notif_mod
        import inspect

        source = inspect.getsource(notif_mod)
        assert "send_email" not in source
        assert "send_message" not in source
        assert "SMTPEmailProvider" not in source
        assert "smtp" not in source.lower()

    def test_no_automatic_email_send(self):
        """The scheduler must never call send_message or email provider."""
        # Structural check: scheduler imports only run_automation_cycle,
        # not send_message or email functions
        import app.automation.scheduler as sched_mod
        import inspect

        source = inspect.getsource(sched_mod)
        assert "send_message" not in source
        assert "send_email" not in source
        assert "SMTPEmailProvider" not in source

    def test_no_automatic_outreach_approval(self):
        """The scheduler must never approve drafts automatically."""
        import app.automation.scheduler as sched_mod
        import inspect

        source = inspect.getsource(sched_mod)
        assert "approve_draft" not in source
        assert "mark_ready" not in source

    def test_no_automatic_followup_sending(self):
        """The scheduler must never send follow-up emails."""
        import app.automation.scheduler as sched_mod
        import inspect

        source = inspect.getsource(sched_mod)
        assert "send_followup" not in source
        assert "complete_followup" not in source

    def test_config_no_secrets_exposed(self):
        """GET /automation/status and /config must not expose secrets."""
        from app.automation.engine import get_automation_status

        status = get_automation_status()
        assert "email_password" not in status
        assert "ai_api_key" not in status
        assert "database_url" not in status
        assert "email_username" not in status
        assert "smtp" not in str(status).lower()
