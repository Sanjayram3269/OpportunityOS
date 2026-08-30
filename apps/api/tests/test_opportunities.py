"""Tests for the Opportunity API domain."""

# ---------------------------------------------------------------------------
# Helpers – create prerequisite entities
# ---------------------------------------------------------------------------

def _create_company(client, name="TestCo"):
    resp = client.post("/companies", json={"name": name})
    assert resp.status_code == 201
    return resp.json()


def _create_lead(client, company_id, name="Jane Doe"):
    resp = client.post("/leads", json={"name": name, "company_id": company_id})
    assert resp.status_code == 201
    return resp.json()


def _create_opportunity(client, company_id, **overrides):
    payload = {
        "company_id": company_id,
        "type": "INTERNSHIP",
        "title": "Software Engineering Intern",
    }
    payload.update(overrides)
    resp = client.post("/opportunities", json=payload)
    return resp


# ---------------------------------------------------------------------------
# POST /opportunities
# ---------------------------------------------------------------------------

class TestCreateOpportunity:
    def test_create_minimal(self, client):
        company = _create_company(client)
        resp = _create_opportunity(client, company["id"])
        assert resp.status_code == 201
        data = resp.json()
        assert data["company_id"] == company["id"]
        assert data["lead_id"] is None
        assert data["type"] == "INTERNSHIP"
        assert data["title"] == "Software Engineering Intern"
        assert data["status"] == "DISCOVERED"
        assert data["priority"] == "MEDIUM"
        assert data["match_score"] is None
        assert data["potential_value"] is None
        assert data["deadline"] is None

    def test_create_with_lead(self, client):
        company = _create_company(client)
        lead = _create_lead(client, company["id"])
        resp = _create_opportunity(client, company["id"], lead_id=lead["id"])
        assert resp.status_code == 201
        assert resp.json()["lead_id"] == lead["id"]

    def test_create_with_all_optional_fields(self, client):
        company = _create_company(client)
        lead = _create_lead(client, company["id"])
        resp = _create_opportunity(
            client,
            company["id"],
            lead_id=lead["id"],
            title="Full-Stack Developer Role",
            type="FULL_TIME",
            description="A great role",
            source_url="https://example.com/job/123",
            status="QUALIFIED",
            priority="HIGH",
            match_score=85,
            potential_value=75000.00,
            deadline="2026-12-31T23:59:59Z",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["lead_id"] == lead["id"]
        assert data["type"] == "FULL_TIME"
        assert data["description"] == "A great role"
        assert data["source_url"] == "https://example.com/job/123"
        assert data["status"] == "QUALIFIED"
        assert data["priority"] == "HIGH"
        assert data["match_score"] == 85

    def test_create_missing_company_id_fails(self, client):
        resp = client.post(
            "/opportunities",
            json={"type": "INTERNSHIP", "title": "No Company"},
        )
        assert resp.status_code == 422

    def test_create_missing_type_fails(self, client):
        company = _create_company(client)
        resp = client.post(
            "/opportunities",
            json={"company_id": company["id"], "title": "No Type"},
        )
        assert resp.status_code == 422

    def test_create_missing_title_fails(self, client):
        company = _create_company(client)
        resp = client.post(
            "/opportunities",
            json={"company_id": company["id"], "type": "INTERNSHIP"},
        )
        assert resp.status_code == 422

    def test_create_empty_title_fails(self, client):
        company = _create_company(client)
        resp = client.post(
            "/opportunities",
            json={"company_id": company["id"], "type": "INTERNSHIP", "title": ""},
        )
        assert resp.status_code == 422

    def test_create_match_score_out_of_range_fails(self, client):
        company = _create_company(client)
        resp = client.post(
            "/opportunities",
            json={
                "company_id": company["id"],
                "type": "INTERNSHIP",
                "title": "Bad Score",
                "match_score": 150,
            },
        )
        assert resp.status_code == 422

    def test_create_negative_match_score_fails(self, client):
        company = _create_company(client)
        resp = client.post(
            "/opportunities",
            json={
                "company_id": company["id"],
                "type": "INTERNSHIP",
                "title": "Neg Score",
                "match_score": -5,
            },
        )
        assert resp.status_code == 422

    def test_create_invalid_company_fk_fails(self, client):
        resp = client.post(
            "/opportunities",
            json={"company_id": 99999, "type": "INTERNSHIP", "title": "Ghost Co"},
        )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /opportunities
# ---------------------------------------------------------------------------

class TestListOpportunities:
    def test_list_empty(self, client):
        resp = client.get("/opportunities")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_created(self, client):
        company = _create_company(client)
        _create_opportunity(client, company["id"], title="First")
        _create_opportunity(client, company["id"], title="Second")
        resp = client.get("/opportunities")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2


# ---------------------------------------------------------------------------
# GET /opportunities/{id}
# ---------------------------------------------------------------------------

class TestGetOpportunity:
    def test_get_existing(self, client):
        company = _create_company(client)
        created = _create_opportunity(client, company["id"]).json()
        resp = client.get(f"/opportunities/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_nonexistent_returns_404(self, client):
        resp = client.get("/opportunities/99999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /opportunities/{id}
# ---------------------------------------------------------------------------

class TestUpdateOpportunity:
    def test_partial_update(self, client):
        company = _create_company(client)
        opp = _create_opportunity(client, company["id"]).json()
        resp = client.patch(
            f"/opportunities/{opp['id']}",
            json={"priority": "HIGH", "match_score": 90},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["priority"] == "HIGH"
        assert data["match_score"] == 90
        # unchanged fields stay the same
        assert data["title"] == "Software Engineering Intern"
        assert data["type"] == "INTERNSHIP"

    def test_update_nonexistent_returns_404(self, client):
        resp = client.patch("/opportunities/99999", json={"title": "Nope"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /opportunities/{id}
# ---------------------------------------------------------------------------

class TestDeleteOpportunity:
    def test_delete_existing(self, client):
        company = _create_company(client)
        opp = _create_opportunity(client, company["id"]).json()
        resp = client.delete(f"/opportunities/{opp['id']}")
        assert resp.status_code == 204
        # confirm gone
        resp = client.get(f"/opportunities/{opp['id']}")
        assert resp.status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete("/opportunities/99999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /companies/{id}/opportunities
# ---------------------------------------------------------------------------

class TestCompanyOpportunities:
    def test_list_company_opportunities(self, client):
        co1 = _create_company(client, name="Co1")
        co2 = _create_company(client, name="Co2")
        _create_opportunity(client, co1["id"], title="Opp A")
        _create_opportunity(client, co1["id"], title="Opp B")
        _create_opportunity(client, co2["id"], title="Opp C")

        resp = client.get(f"/companies/{co1['id']}/opportunities")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        titles = {o["title"] for o in data}
        assert titles == {"Opp A", "Opp B"}

    def test_company_not_found_returns_404(self, client):
        resp = client.get("/companies/99999/opportunities")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /leads/{id}/opportunities
# ---------------------------------------------------------------------------

class TestLeadOpportunities:
    def test_list_lead_opportunities(self, client):
        company = _create_company(client)
        lead = _create_lead(client, company["id"])
        _create_opportunity(client, company["id"], lead_id=lead["id"], title="For Lead")
        _create_opportunity(client, company["id"], title="No Lead")

        resp = client.get(f"/leads/{lead['id']}/opportunities")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "For Lead"

    def test_lead_not_found_returns_404(self, client):
        resp = client.get("/leads/99999/opportunities")
        assert resp.status_code == 404

    def test_lead_with_no_opportunities(self, client):
        company = _create_company(client)
        lead = _create_lead(client, company["id"])
        resp = client.get(f"/leads/{lead['id']}/opportunities")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Existing API preservation
# ---------------------------------------------------------------------------

class TestExistingApisPreserved:
    def test_profiles_still_work(self, client):
        resp = client.post(
            "/profiles",
            json={"name": "Test User", "email": "test@example.com"},
        )
        assert resp.status_code == 201

    def test_companies_still_work(self, client):
        resp = client.post("/companies", json={"name": "Preserved Co"})
        assert resp.status_code == 201

    def test_leads_still_work(self, client):
        company = _create_company(client)
        resp = client.post(
            "/leads",
            json={"name": "Preserved Lead", "company_id": company["id"]},
        )
        assert resp.status_code == 201

    def test_company_leads_still_work(self, client):
        company = _create_company(client)
        _create_lead(client, company["id"])
        resp = client.get(f"/companies/{company['id']}/leads")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
