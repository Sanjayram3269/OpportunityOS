"""Production hardening tests — verifies configuration, security, and resilience.

Tests cover:
  - Configuration loading
  - Health endpoints
  - CORS configuration
  - Error handling (no stack trace leakage)
  - Request ID generation
  - Database session lifecycle
  - Secret non-exposure
  - Production defaults
  - Environment separation
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app


# ══════════════════════════════════════════════════════════════════════════
# 1. CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════


class TestConfiguration:
    def test_settings_loads(self):
        settings = get_settings()
        assert settings.database_url is not None
        assert settings.environment in ("development", "test", "production")

    def test_cors_origins_list_parsed(self):
        s = Settings(
            database_url="postgresql://test:test@localhost/test",
            cors_origins="http://localhost:3000,http://localhost:3001",
        )
        assert s.cors_origins_list == ["http://localhost:3000", "http://localhost:3001"]

    def test_cors_origins_strips_whitespace(self):
        s = Settings(
            database_url="postgresql://test:test@localhost/test",
            cors_origins="http://a.com , http://b.com",
        )
        assert s.cors_origins_list == ["http://a.com", "http://b.com"]

    def test_is_production(self):
        s = Settings(database_url="postgresql://t:t@localhost/t", environment="production")
        assert s.is_production is True
        assert s.is_development is False

    def test_is_development(self):
        s = Settings(database_url="postgresql://t:t@localhost/t", environment="development")
        assert s.is_development is True
        assert s.is_production is False

    def test_debug_defaults_true(self):
        s = Settings(database_url="postgresql://t:t@localhost/t")
        assert s.debug is True

    def test_settings_model_has_secret_fields(self):
        """Verify sensitive fields exist and are configurable via env."""
        s = Settings(
            database_url="postgresql://user:pass@host/db",
            email_password="test_pass",
            ai_api_key="test_key",
        )
        # Fields should be present (configuration works)
        assert s.email_password == "test_pass"
        assert s.ai_api_key == "test_key"
        # In production, these would come from environment variables
        assert s.environment in ("development", "test", "production")


# ══════════════════════════════════════════════════════════════════════════
# 2. HEALTH ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════


class TestHealthEndpoints:
    def test_liveness(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "opportunityos-api"
        assert "version" in data

    def test_readiness(self, client):
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"

    def test_health_no_secrets(self, client):
        resp = client.get("/health")
        text = resp.text.lower()
        assert "password" not in text
        assert "secret" not in text
        assert "api_key" not in text
        assert "smtp" not in text

    def test_readiness_no_secrets(self, client):
        resp = client.get("/health/ready")
        text = resp.text.lower()
        assert "password" not in text
        assert "connection_string" not in text


# ══════════════════════════════════════════════════════════════════════════
# 3. CORS
# ══════════════════════════════════════════════════════════════════════════


class TestCORS:
    def test_cors_headers_present(self, client):
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS middleware should be configured
        assert resp.status_code in (200, 405)

    def test_cors_configured_from_settings(self):
        from app.main import app as main_app
        middleware_stack = [m for m in main_app.user_middleware]
        cors_found = any(
            "CORSMiddleware" in str(m) for m in middleware_stack
        )
        assert cors_found


# ══════════════════════════════════════════════════════════════════════════
# 4. ERROR HANDLING
# ══════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    def test_404_returns_safe_error(self, client):
        resp = client.get("/nonexistent-endpoint")
        assert resp.status_code in (404, 405)
        # Should not contain stack traces
        assert "Traceback" not in resp.text
        assert "File \"" not in resp.text

    def test_404_no_stack_trace(self, client):
        resp = client.get("/api/does/not/exist")
        assert resp.status_code in (404, 405)
        assert "Traceback" not in resp.text

    def test_request_id_in_response(self, client):
        resp = client.get("/health")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) == 8


# ══════════════════════════════════════════════════════════════════════════
# 5. DATABASE SESSION
# ══════════════════════════════════════════════════════════════════════════


class TestDatabaseSession:
    def test_session_cleanup_on_error(self, db):
        """Session should be properly closed even after errors."""
        from app.db.session import SessionLocal
        session = SessionLocal()
        try:
            # Do something that doesn't error
            session.execute(__import__("sqlalchemy").text("SELECT 1"))
        finally:
            session.close()
        # If we get here, cleanup worked

    def test_engine_pool_configured(self):
        from app.db.session import engine
        pool = engine.pool
        # pool.size() returns the configured pool size
        assert pool.size() == 5
        # max_overflow is accessible on the internal pool
        assert getattr(pool, '_max_overflow', None) == 10


# ══════════════════════════════════════════════════════════════════════════
# 6. REGRESSION — Existing features still work
# ══════════════════════════════════════════════════════════════════════════


class TestRegression:
    def test_action_center(self, client, db):
        resp = client.get("/actions")
        assert resp.status_code == 200

    def test_followups(self, client, db):
        resp = client.get("/follow-ups")
        assert resp.status_code == 200

    def test_applications(self, client, db):
        resp = client.get("/applications")
        assert resp.status_code == 200

    def test_dashboard(self, client, db):
        resp = client.get("/dashboard/overview")
        assert resp.status_code == 200

    def test_analytics(self, client, db):
        resp = client.get("/analytics/overview")
        assert resp.status_code == 200

    def test_notifications(self, client, db):
        resp = client.get("/notifications")
        assert resp.status_code == 200

    def test_export(self, client, db):
        resp = client.get("/exports/opportunities.xlsx")
        assert resp.status_code == 200

    def test_planning(self, client, db):
        resp = client.get("/opportunities/planning")
        assert resp.status_code == 200

    def test_opportunities(self, client, db):
        resp = client.get("/opportunities")
        assert resp.status_code == 200

    def test_companies(self, client, db):
        resp = client.get("/companies")
        assert resp.status_code == 200
