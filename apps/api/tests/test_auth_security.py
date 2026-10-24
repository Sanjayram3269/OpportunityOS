"""Security regression tests for single-owner bearer-token authentication.

Verifies that:
  - Requests without credentials are rejected (401) on every sensitive route.
  - Invalid / malformed credentials are rejected (401).
  - Valid credentials can access permitted endpoints (200).
  - Sensitive mutations cannot be triggered without authentication.
  - With no token configured, the API fails closed (503), never open.
  - Health/readiness stay public and leak no sensitive data.
"""

from __future__ import annotations

import os
import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app

# Must match the token set by tests/conftest.py before app import.
TEST_AUTH_TOKEN = os.environ["API_AUTH_TOKEN"]

# Endpoints that must remain reachable without credentials.
PUBLIC_PATHS = {"/health", "/health/ready"}

HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")


def mounted_route_pairs() -> set[tuple[str, str]]:
    """Enumerate the REAL mounted route table (method, path).

    Deliberately walks ``app.routes`` — including included routers — instead
    of trusting the OpenAPI document, because the schema is disabled in
    production (``openapi_url=None``) and could silently drift from what is
    actually served. Starlette-level routes (docs/redoc/schema) are excluded:
    only APIRoute instances form the protected business API surface.
    """
    pairs: set[tuple[str, str]] = set()

    def walk(routes) -> None:
        for route in routes:
            if isinstance(route, APIRoute):
                for method in route.methods or set():
                    if method in HTTP_METHODS:
                        pairs.add((method, route.path))
            # Included routers wrap the original APIRouter. Duck-typed via
            # `original_router` so a private-class rename cannot silently
            # reduce sweep coverage.
            original = getattr(route, "original_router", None)
            if original is not None and hasattr(original, "routes"):
                prefix = getattr(getattr(route, "include_context", None), "prefix", "") or ""
                for sub in original.routes:
                    if isinstance(sub, APIRoute):
                        full = (
                            sub.path
                            if not prefix or sub.path.startswith(prefix)
                            else prefix.rstrip("/") + sub.path
                        )
                        for method in sub.methods or set():
                            if method in HTTP_METHODS:
                                pairs.add((method, full))

    walk(app.routes)
    return pairs


@pytest.fixture()
def anon_client(db):
    """TestClient with NO Authorization header, wired to the test db session."""
    from app.api.deps import get_db

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def valid_client(client):
    """The standard conftest client, which carries the valid bearer token."""
    return client


# ── No credentials ────────────────────────────────────────────────────────


class TestMissingCredentials:
    @pytest.mark.parametrize(
        "path",
        [
            "/profiles",
            "/profiles/1",
            "/opportunities",
            "/companies",
            "/leads",
            "/applications",
            "/outreach/drafts",
            "/follow-ups",
            "/campaigns",
            "/notifications",
            "/dashboard/overview",
            "/matching/profiles/1/ranked",
            "/exports/opportunities.xlsx",
            "/automation/status",
            "/discovery/sources",
        ],
    )
    def test_get_rejected_without_credentials(self, anon_client, path):
        resp = anon_client.get(path)
        assert resp.status_code == 401, f"{path} must require auth, got {resp.status_code}"
        assert "WWW-Authenticate" in resp.headers

    def test_401_response_does_not_leak_details(self, anon_client):
        resp = anon_client.get("/profiles")
        assert resp.status_code == 401
        body = resp.json()
        assert "traceback" not in body["detail"].lower()
        assert "token" not in body["detail"].lower().replace("bearer <token>", "")


# ── Invalid credentials ───────────────────────────────────────────────────


class TestInvalidCredentials:
    @pytest.mark.parametrize(
        "header",
        [
            "Bearer wrong-token",
            "Bearer ",
            "Bearer",
            "Basic dXNlcjpwYXNz",
            "Token something",
            "opportunityos-test-token",  # raw token without scheme
        ],
    )
    def test_bad_authorization_header_rejected(self, anon_client, header):
        resp = anon_client.get("/profiles", headers={"Authorization": header})
        assert resp.status_code == 401

    def test_case_variations_of_valid_token_rejected(self, anon_client):
        # Scheme is case-insensitive; the token itself is not.
        resp = anon_client.get(
            "/profiles",
            headers={"Authorization": f"bearer {TEST_AUTH_TOKEN.upper()}"},
        )
        assert resp.status_code == 401


# ── Valid credentials ─────────────────────────────────────────────────────


class TestValidCredentials:
    @pytest.mark.parametrize(
        "path",
        ["/profiles", "/opportunities", "/companies", "/notifications", "/leads"],
    )
    def test_valid_token_allows_reads(self, valid_client, path):
        resp = valid_client.get(path)
        assert resp.status_code == 200

    def test_valid_token_allows_profile_create_read_delete_cycle(self, valid_client):
        created = valid_client.post(
            "/profiles",
            json={"name": "Auth Cycle Test", "email": "auth-cycle-test@example.com"},
        )
        assert created.status_code == 201
        profile_id = created.json()["id"]

        fetched = valid_client.get(f"/profiles/{profile_id}")
        assert fetched.status_code == 200

        deleted = valid_client.delete(f"/profiles/{profile_id}")
        assert deleted.status_code == 204

        gone = valid_client.get(f"/profiles/{profile_id}")
        assert gone.status_code == 404


# ── Mutations without authentication ──────────────────────────────────────


class TestMutationsRequireAuth:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("POST", "/profiles"),
            ("PATCH", "/profiles/1"),
            ("DELETE", "/profiles/1"),
            ("POST", "/opportunities"),
            ("POST", "/applications"),
            ("POST", "/outreach/drafts/1/approve"),
            ("POST", "/outreach/drafts/1/send"),
            ("POST", "/follow-ups/1/approve"),
            ("POST", "/follow-ups/1/submit"),
            ("POST", "/automation/run"),
            ("POST", "/discovery/run"),
            ("POST", "/notifications/read-all"),
        ],
    )
    def test_mutation_rejected_without_auth(self, anon_client, method, path):
        resp = anon_client.request(method, path, json={})
        assert resp.status_code == 401, f"{method} {path} must require auth"

    def test_export_download_requires_auth(self, anon_client):
        # The export is a GET download (not a mutation) but exposes all data,
        # so it must still require credentials.
        resp = anon_client.get("/exports/opportunities.xlsx")
        assert resp.status_code == 401

    def test_unauthenticated_profile_create_persists_nothing(self, anon_client, db):
        from app.models.profile import Profile

        before = db.query(Profile).count()
        resp = anon_client.post(
            "/profiles",
            json={"name": "Evil", "email": "evil@example.com"},
        )
        assert resp.status_code == 401
        db.expire_all()
        after = db.query(Profile).count()
        assert after == before


# ── Every mounted business operation requires auth ────────────────────────


class TestAllRoutesProtected:
    def test_sweep_covers_every_mounted_route(self, anon_client):
        """Every mounted business operation must answer 401 without credentials.

        Driven by the real route table, not the OpenAPI document."""
        pairs = mounted_route_pairs()
        # Sanity guard: the sweep must actually see the whole API.
        assert len(pairs) >= 100, f"route walk only found {len(pairs)} operations"

        violations = []
        for method, path in sorted(pairs):
            if path in PUBLIC_PATHS:
                continue
            concrete = re.sub(r"\{[^}]+\}", "1", path)
            resp = anon_client.request(method, concrete, json={})
            if resp.status_code != 401:
                violations.append(f"{method} {concrete} → {resp.status_code}")
        assert not violations, "Routes reachable without credentials:\n" + "\n".join(violations)

    def test_openapi_document_matches_mounted_routes(self, anon_client):
        """The dev schema must not invent or hide business routes."""
        spec = app.openapi()
        documented = {
            (method.upper(), path)
            for path, operations in spec["paths"].items()
            for method in operations
            if method in (m.lower() for m in HTTP_METHODS)
        }
        mounted = mounted_route_pairs()
        # Everything documented must actually be mounted (docs routes are
        # starlette-level and excluded from both sides' business surface).
        undocumented = documented - mounted
        assert not undocumented, f"documented but not mounted: {sorted(undocumented)}"
        # Every mounted business route must appear in the dev schema too.
        missing = {p for p in mounted if p[1] not in PUBLIC_PATHS} - documented
        assert not missing, f"mounted but undocumented: {sorted(missing)}"

    def test_unauthenticated_mutations_write_nothing(self, anon_client, db):
        """Firing every mutating operation without credentials must not change
        any database table (no writes, no pipeline runs, no state flips)."""
        from app.models.application import Application
        from app.models.automation_run import AutomationRun
        from app.models.campaign import Campaign
        from app.models.followup import FollowUp
        from app.models.notification import Notification
        from app.models.opportunity import Opportunity
        from app.models.profile import Profile

        def snapshot() -> dict[str, int]:
            return {
                "profiles": db.query(Profile).count(),
                "opportunities": db.query(Opportunity).count(),
                "applications": db.query(Application).count(),
                "campaigns": db.query(Campaign).count(),
                "followups": db.query(FollowUp).count(),
                "notifications": db.query(Notification).count(),
                "automation_runs": db.query(AutomationRun).count(),
            }

        before = snapshot()
        mutating = [
            (m, p) for m, p in mounted_route_pairs() if m != "GET" and p not in PUBLIC_PATHS
        ]
        assert len(mutating) >= 40, "mutation sweep looks too small"
        for method, path in mutating:
            concrete = re.sub(r"\{[^}]+\}", "1", path)
            resp = anon_client.request(method, concrete, json={})
            assert resp.status_code == 401, f"{method} {concrete} answered {resp.status_code}"
        db.expire_all()
        assert snapshot() == before, "unauthenticated mutations modified the database"

    def test_production_surface_hides_docs_and_schema(self):
        """With ENVIRONMENT=production the API must not serve /docs, /redoc or
        /openapi.json (information disclosure), while health stays public."""
        import subprocess
        import sys

        code = (
            "from app.main import app; "
            "paths = {getattr(r, 'path', '') for r in app.routes}; "
            "print(sorted(p for p in paths if p in "
            "{'/docs', '/redoc', '/openapi.json', '/health', '/health/ready'}))"
        )
        env = {**os.environ, "ENVIRONMENT": "production", "DEBUG": "false"}
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr[-500:]
        paths = eval(result.stdout.strip().splitlines()[-1])  # noqa: S307
        assert "/docs" not in paths
        assert "/redoc" not in paths
        assert "/openapi.json" not in paths
        assert "/health" in paths and "/health/ready" in paths


# ── Fail-closed behavior ──────────────────────────────────────────────────


class TestFailClosed:
    def test_missing_server_token_returns_503_not_open_access(self, anon_client, monkeypatch):
        from app.api import deps

        class _NoTokenSettings:
            api_auth_token = ""

        monkeypatch.setattr(deps, "get_settings", lambda: _NoTokenSettings())
        resp = anon_client.get("/profiles")
        assert resp.status_code == 503
        # Fail closed even with a valid-looking token when unconfigured.
        resp = anon_client.get(
            "/profiles", headers={"Authorization": f"Bearer {TEST_AUTH_TOKEN}"}
        )
        assert resp.status_code == 503


# ── Public health endpoints ───────────────────────────────────────────────


class TestHealthRemainsPublic:
    @pytest.mark.parametrize("path", sorted(PUBLIC_PATHS))
    def test_health_public_but_harmless(self, anon_client, path):
        resp = anon_client.get(path)
        assert resp.status_code == 200
        text = resp.text.lower()
        for secret_word in ("token", "password", "secret", "api_auth"):
            assert secret_word not in text, f"{path} must not expose {secret_word}"
