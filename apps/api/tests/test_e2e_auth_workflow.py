"""End-to-end authenticated workflow tests.

Walks the real HTTP surface the way the frontend does, with the single-owner
bearer token: create a profile, read it back, seed isolated synthetic
opportunity data, rank matches, and update a preference — then verify the
same workflow is rejected without credentials.

All data is synthetic and rolls back with the transactional db fixture.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.company import Company
from app.models.opportunity import Opportunity
from app.models.skill import Skill


class TestAuthenticatedWorkflow:
    def test_full_workflow_profile_to_ranked_matches(self, client, db):
        """Create → read → seed → rank → update, all authenticated."""
        # 1. Create the owner profile (synthetic identity only).
        created = client.post(
            "/profiles",
            json={
                "name": "E2E Backend Tester",
                "email": "e2e-backend@example.com",
                "headline": "Python Engineer",
                "current_city": "Chennai",
            },
        )
        assert created.status_code == 201
        profile_id = created.json()["id"]

        # 2. Read it back.
        fetched = client.get(f"/profiles/{profile_id}")
        assert fetched.status_code == 200
        assert fetched.json()["email"] == "e2e-backend@example.com"

        # 3. Seed isolated opportunity data + skills for matching.
        skill = Skill(profile_id=profile_id, name="Python")
        company = Company(name="Synthetic E2E Co")
        db.add_all([skill, company])
        db.flush()
        db.add_all(
            [
                Opportunity(
                    company_id=company.id,
                    type="FULL_TIME",
                    title="Python Developer",
                    description="Python, Django, PostgreSQL required.",
                ),
                Opportunity(
                    company_id=company.id,
                    type="FULL_TIME",
                    title="Marketing Manager",
                    description="Marketing, SEO, social media.",
                ),
            ]
        )
        db.flush()

        # 4. Rank matches — the profile's skill must beat the irrelevant role.
        ranked = client.get(f"/matching/profiles/{profile_id}/ranked")
        assert ranked.status_code == 200
        body = ranked.json()
        assert body["profile_id"] == profile_id
        assert body["total_opportunities"] == 2
        matches = body["matches"]
        assert len(matches) == 2
        assert matches[0]["title"] == "Python Developer"
        assert matches[0]["score"] >= matches[1]["score"]
        assert "python" in [s.lower() for s in matches[0]["matched_skills"]]

        # 5. Update a preference and verify persistence.
        patched = client.patch(
            f"/profiles/{profile_id}",
            json={"geographic_preference": "Remote", "preferred_role_types": "FULL_TIME"},
        )
        assert patched.status_code == 200
        assert patched.json()["geographic_preference"] == "Remote"

        refetched = client.get(f"/profiles/{profile_id}")
        assert refetched.json()["preferred_role_types"] == "FULL_TIME"

    def test_workflow_rejected_without_credentials(self, db):
        """Every step of the same workflow must 401 without the token."""
        anon = TestClient(app, raise_server_exceptions=False)

        steps = [
            ("POST", "/profiles", {"name": "X", "email": "x@example.com"}),
            ("GET", "/profiles", None),
            ("GET", "/profiles/1", None),
            ("PATCH", "/profiles/1", {"geographic_preference": "Remote"}),
            ("GET", "/matching/profiles/1/ranked", None),
            ("GET", "/matching/profiles/1/opportunities/1", None),
        ]
        for method, path, body in steps:
            resp = anon.request(method, path, json=body)
            assert resp.status_code == 401, f"{method} {path} answered {resp.status_code}"

    def test_fail_closed_blocks_workflow_even_with_valid_token(self, client, monkeypatch):
        """With API_AUTH_TOKEN unset server-side, the whole workflow 503s."""
        from app.api import deps

        class _NoTokenSettings:
            api_auth_token = ""

        monkeypatch.setattr(deps, "get_settings", lambda: _NoTokenSettings())
        resp = client.get("/profiles")
        assert resp.status_code == 503
