"""Tests for the Remotive source adapter and source-driven discovery.

All HTTP calls are mocked — no live external requests are made.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.discovery.adapters.remotive import RemotiveAdapter, _JOB_TYPE_MAP
from app.discovery.normalizer import normalize, normalize_all
from app.discovery.registry import create_adapter, get_adapter_class, list_source_names
from app.models.company import Company
from app.models.opportunity import Opportunity
from app.models.opportunity_evidence import OpportunityEvidence


# ── Fixtures ──────────────────────────────────────────────────────────────


def _sample_remotive_job(**overrides) -> dict:
    """Return a realistic Remotive API job record."""
    job_id = overrides.get("id", 12345)
    job = {
        "id": job_id,
        "url": f"https://remotive.com/remote-jobs/product/lead-developer-{job_id}",
        "title": "Lead Developer",
        "company_name": "Acme Corp",
        "company_logo": f"https://remotive.com/job/{job_id}/logo",
        "category": "Software Development",
        "job_type": "full_time",
        "publication_date": "2025-06-15T10:23:26",
        "candidate_required_location": "Worldwide",
        "salary": "$120,000 - $150,000",
        "description": "<p>We are looking for a lead developer...</p>",
    }
    job.update(overrides)
    return job


def _remotive_api_response(jobs: list[dict]) -> dict:
    """Wrap a list of jobs in the Remotive API response envelope."""
    return {
        "0-legal-notice": "Remotive API Legal Notice",
        "job-count": len(jobs),
        "jobs": jobs,
    }


def _mock_httpx_get(response_data: dict, status_code: int = 200):
    """Return a context manager that patches httpx.get for Remotive calls."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = response_data
    mock_response.raise_for_status.return_value = None

    if status_code >= 400:
        from httpx import HTTPStatusError, Request, Response

        mock_request = MagicMock(spec=Request)
        mock_response2 = MagicMock(spec=Response)
        mock_response2.status_code = status_code
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            message=f"HTTP {status_code}",
            request=mock_request,
            response=mock_response2,
        )

    return patch("httpx.get", return_value=mock_response)


# ── Adapter contract tests ────────────────────────────────────────────────


class TestRemotiveAdapterContract:
    """Verify the adapter satisfies the SourceAdapter interface."""

    def test_source_name(self):
        adapter = RemotiveAdapter()
        assert adapter.source_name == "remotive"

    def test_discover_raises_on_failure(self):
        """discover() raises on network/server errors."""
        adapter = RemotiveAdapter()
        with _mock_httpx_get({}, status_code=500):
            with pytest.raises(Exception):
                adapter.discover()

    def test_discover_returns_raw_opportunities(self):
        """Successful fetch returns RawOpportunity instances."""
        from app.discovery.models import RawOpportunity

        adapter = RemotiveAdapter()
        response = _remotive_api_response([_sample_remotive_job()])
        with _mock_httpx_get(response):
            result = adapter.discover()

        assert len(result) == 1
        assert isinstance(result[0], RawOpportunity)
        assert result[0].source_name == "remotive"
        assert result[0].external_id == "12345"
        assert result[0].title == "Lead Developer"
        assert result[0].company_name == "Acme Corp"


# ── Successful parsing tests ──────────────────────────────────────────────


class TestRemotiveAdapterParsing:
    """Test parsing of various Remotive job records."""

    def test_full_job_record(self):
        adapter = RemotiveAdapter()
        response = _remotive_api_response([_sample_remotive_job()])
        with _mock_httpx_get(response):
            result = adapter.discover()

        opp = result[0]
        assert opp.external_id == "12345"
        assert opp.source_url == "https://remotive.com/remote-jobs/product/lead-developer-12345"
        assert opp.title == "Lead Developer"
        assert opp.company_name == "Acme Corp"
        assert opp.opportunity_type == "FULL_TIME"
        assert opp.location == "Worldwide"
        assert opp.description == "<p>We are looking for a lead developer...</p>"
        assert opp.metadata["category"] == "Software Development"
        assert opp.metadata["salary_text"] == "$120,000 - $150,000"
        assert opp.deadline == datetime(2025, 6, 15, 10, 23, 26, tzinfo=timezone.utc)

    def test_job_type_mapping(self):
        """All Remotive job_type values map correctly."""
        for raw_type, expected in _JOB_TYPE_MAP.items():
            adapter = RemotiveAdapter()
            job = _sample_remotive_job(job_type=raw_type)
            response = _remotive_api_response([job])
            with _mock_httpx_get(response):
                result = adapter.discover()
            assert result[0].opportunity_type == expected, f"{raw_type} should map to {expected}"

    def test_missing_optional_fields(self):
        """Job with only required fields (id, title, company_name) parses cleanly."""
        adapter = RemotiveAdapter()
        job = {
            "id": 99,
            "title": "Simple Role",
            "company_name": "Simple Co",
        }
        response = _remotive_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()

        opp = result[0]
        assert opp.external_id == "99"
        assert opp.source_url is None
        assert opp.description is None
        assert opp.opportunity_type == "OTHER"  # no job_type → infer from title → OTHER
        assert opp.location is None
        assert opp.deadline is None
        assert opp.metadata == {}

    def test_empty_string_fields_treated_as_none(self):
        """Empty strings in optional fields are normalized to None."""
        adapter = RemotiveAdapter()
        job = _sample_remotive_job(
            url="",
            description="  ",
            candidate_required_location="",
            salary="",
            category="",
        )
        response = _remotive_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()

        opp = result[0]
        assert opp.source_url is None
        assert opp.description is None
        assert opp.location is None
        assert opp.metadata == {}

    def test_type_inference_from_title(self):
        """When job_type is missing, title keywords are used for inference."""
        test_cases = [
            ("Software Engineering Intern", "INTERNSHIP"),
            ("Senior Full-Stack Developer", "FULL_TIME"),
            ("Part-Time Data Analyst", "PART_TIME"),
            ("Freelance Designer", "FREELANCE"),
            ("Contract Backend Engineer", "CONTRACT"),
            ("Startup Founder Role", "STARTUP"),
            ("Research Assistant", "RESEARCH"),
            ("Hackathon Participant", "HACKATHON"),
            ("General Manager", "OTHER"),
        ]
        for title, expected_type in test_cases:
            adapter = RemotiveAdapter()
            job = {"id": 1, "title": title, "company_name": "Test Co"}
            # No job_type field
            response = _remotive_api_response([job])
            with _mock_httpx_get(response):
                result = adapter.discover()
            assert result[0].opportunity_type == expected_type, (
                f"Title '{title}' should infer as {expected_type}"
            )

    def test_multiple_jobs_in_batch(self):
        adapter = RemotiveAdapter()
        jobs = [
            _sample_remotive_job(id=1, title="Job A", company_name="Co A"),
            _sample_remotive_job(id=2, title="Job B", company_name="Co B"),
            _sample_remotive_job(id=3, title="Job C", company_name="Co C"),
        ]
        response = _remotive_api_response(jobs)
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert len(result) == 3
        titles = {r.title for r in result}
        assert titles == {"Job A", "Job B", "Job C"}

    def test_datetime_with_timezone(self):
        adapter = RemotiveAdapter()
        job = _sample_remotive_job(publication_date="2025-06-15T10:23:26+05:30")
        response = _remotive_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].deadline is not None
        assert result[0].deadline.tzinfo is not None

    def test_malformed_datetime_ignored(self):
        adapter = RemotiveAdapter()
        job = _sample_remotive_job(publication_date="not-a-date")
        response = _remotive_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].deadline is None


# ── Failure behavior tests ────────────────────────────────────────────────


class TestRemotiveAdapterFailures:
    """Verify the adapter raises on errors (caller is responsible for handling)."""

    def test_network_timeout_raises(self):
        import httpx

        adapter = RemotiveAdapter()
        with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(httpx.TimeoutException):
                adapter.discover()

    def test_connection_error_raises(self):
        import httpx

        adapter = RemotiveAdapter()
        with patch("httpx.get", side_effect=httpx.ConnectError("connection refused")):
            with pytest.raises(httpx.ConnectError):
                adapter.discover()

    def test_http_error_raises(self):
        import httpx

        adapter = RemotiveAdapter()
        with _mock_httpx_get({}, status_code=429):
            with pytest.raises(httpx.HTTPStatusError):
                adapter.discover()

    def test_malformed_json_raises(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("no JSON")
        mock_response.raise_for_status.return_value = None

        adapter = RemotiveAdapter()
        with patch("httpx.get", return_value=mock_response):
            with pytest.raises(ValueError, match="no JSON"):
                adapter.discover()

    def test_missing_jobs_key_raises(self):
        adapter = RemotiveAdapter()
        with _mock_httpx_get({"unexpected": "structure"}):
            with pytest.raises(ValueError, match="Expected 'jobs' list"):
                adapter.discover()

    def test_jobs_not_a_list_raises(self):
        adapter = RemotiveAdapter()
        with _mock_httpx_get({"jobs": "not a list"}):
            with pytest.raises(ValueError, match="Expected 'jobs' list"):
                adapter.discover()

    def test_response_not_a_dict_raises(self):
        adapter = RemotiveAdapter()
        with _mock_httpx_get([1, 2, 3]):
            with pytest.raises(ValueError, match="Expected JSON object"):
                adapter.discover()

    def test_missing_title_skips_job(self):
        adapter = RemotiveAdapter()
        job = {"id": 1, "company_name": "Co"}  # no title
        response = _remotive_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert len(result) == 0

    def test_missing_company_skips_job(self):
        adapter = RemotiveAdapter()
        job = {"id": 1, "title": "Role"}  # no company_name
        response = _remotive_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert len(result) == 0

    def test_mixed_valid_and_invalid_jobs(self):
        """Valid jobs are returned, invalid ones are skipped."""
        adapter = RemotiveAdapter()
        jobs = [
            _sample_remotive_job(id=1, title="Good Job", company_name="Good Co"),
            {"id": 2},  # missing title and company
            _sample_remotive_job(id=3, title="Another Good Job", company_name="Good Co 2"),
        ]
        response = _remotive_api_response(jobs)
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert len(result) == 2
        assert result[0].external_id == "1"
        assert result[1].external_id == "3"


# ── Adapter registry tests ────────────────────────────────────────────────


class TestAdapterRegistry:
    def test_list_source_names(self):
        names = list_source_names()
        assert "remotive" in names

    def test_get_adapter_class(self):
        cls = get_adapter_class("remotive")
        assert cls is not None
        assert issubclass(cls, RemotiveAdapter)

    def test_get_unknown_adapter_returns_none(self):
        assert get_adapter_class("nonexistent") is None

    def test_create_adapter(self):
        adapter = create_adapter("remotive")
        assert isinstance(adapter, RemotiveAdapter)
        assert adapter.source_name == "remotive"

    def test_create_unknown_adapter_raises(self):
        with pytest.raises(ValueError, match="Unknown source"):
            create_adapter("nonexistent")

    def test_case_insensitive_lookup(self):
        adapter = create_adapter("Remotive")
        assert isinstance(adapter, RemotiveAdapter)


# ── Normalization + Remotive integration tests ────────────────────────────


class TestRemotiveNormalization:
    """Test that Remotive raw output normalizes correctly."""

    def test_normalize_remotive_raw(self):
        adapter = RemotiveAdapter()
        response = _remotive_api_response([_sample_remotive_job()])
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        assert len(normalized) == 1

        opp = normalized[0]
        assert opp.source_name == "remotive"
        assert opp.external_id == "12345"
        assert opp.normalized_title == "Lead Developer"
        assert opp.normalized_company_name == "Acme Corp"
        assert opp.opportunity_type == "FULL_TIME"
        assert opp.normalized_location == "Worldwide"

    def test_normalize_all_batch(self):
        adapter = RemotiveAdapter()
        jobs = [
            _sample_remotive_job(id=i, title=f"  Job {i}  ", company_name=f"  Co {i}  ")
            for i in range(5)
        ]
        response = _remotive_api_response(jobs)
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        assert len(normalized) == 5
        for opp in normalized:
            # Whitespace should be stripped
            assert opp.normalized_title == opp.normalized_title.strip()
            assert opp.normalized_company_name == opp.normalized_company_name.strip()


# ── Deduplication integration tests ───────────────────────────────────────


class TestRemotiveDeduplication:
    """Test that Remotive-sourced opportunities deduplicate correctly."""

    def test_deduplicate_by_external_id(self):
        """Same external_id from same source is deduped."""
        from app.discovery.deduplicator import deduplicate

        adapter = RemotiveAdapter()
        job = _sample_remotive_job()
        response = _remotive_api_response([job, job])  # duplicate job
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        assert len(deduped) == 1

    def test_deduplicate_by_url(self):
        """Same URL from same source is deduped."""
        from app.discovery.deduplicator import deduplicate

        job1 = _sample_remotive_job(id=1, title="Job A")
        job2 = _sample_remotive_job(id=2, title="Job B")
        # Same URL
        job2["url"] = job1["url"]

        adapter = RemotiveAdapter()
        response = _remotive_api_response([job1, job2])
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        assert len(deduped) == 1


# ── Full pipeline integration (adapter → normalize → dedup → ingest) ──────


class TestRemotiveIngestionPipeline:
    """End-to-end: adapter → normalize → dedup → ingest into the database."""

    def test_full_pipeline_single_job(self, db):
        from app.discovery.deduplicator import deduplicate
        from app.discovery.normalizer import normalize_all
        from app.services.discovery import ingest

        adapter = RemotiveAdapter()
        job = _sample_remotive_job()
        response = _remotive_api_response([job])
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        result = ingest(db, deduped)

        assert result.raw_count == 1
        assert result.ingested == 1
        assert result.duplicates_skipped == 0
        assert result.companies_created == 1
        assert result.errors == []

        # Verify DB state
        opp = db.query(Opportunity).filter(Opportunity.title == "Lead Developer").first()
        assert opp is not None
        assert opp.type == "FULL_TIME"
        assert opp.status == "DISCOVERED"
        assert opp.priority == "MEDIUM"
        assert opp.source_url == "https://remotive.com/remote-jobs/product/lead-developer-12345"

        company = db.query(Company).filter(Company.name == "Acme Corp").first()
        assert company is not None
        assert opp.company_id == company.id

        # Evidence records
        evidence = db.query(OpportunityEvidence).filter(
            OpportunityEvidence.opportunity_id == opp.id
        ).all()
        evidence_types = {e.evidence_type for e in evidence}
        assert "external_id" in evidence_types
        assert "source_url" in evidence_types

    def test_full_pipeline_multiple_jobs(self, db):
        from app.discovery.deduplicator import deduplicate
        from app.discovery.normalizer import normalize_all
        from app.services.discovery import ingest

        adapter = RemotiveAdapter()
        jobs = [
            _sample_remotive_job(id=101, title="Frontend Dev", company_name="Co A"),
            _sample_remotive_job(id=102, title="Backend Dev", company_name="Co B"),
            _sample_remotive_job(id=103, title="DevOps Eng", company_name="Co A"),
        ]
        response = _remotive_api_response(jobs)
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        result = ingest(db, deduped)

        assert result.ingested == 3
        assert result.companies_created == 2  # Co A shared

        # Verify all companies and opportunities exist
        companies = db.query(Company).filter(
            Company.name.in_(["Co A", "Co B"])
        ).all()
        assert len(companies) == 2

        opps = db.query(Opportunity).all()
        assert len(opps) == 3

    def test_full_pipeline_dedup_on_second_run(self, db):
        """Running the same source twice doesn't create duplicates."""
        from app.discovery.deduplicator import deduplicate
        from app.discovery.normalizer import normalize_all
        from app.services.discovery import ingest

        adapter = RemotiveAdapter()
        job = _sample_remotive_job(id=200, title="Dedup Test", company_name="Dedup Co")
        response = _remotive_api_response([job])

        # First run — ingest
        with _mock_httpx_get(response):
            raw_items = adapter.discover()
        normalized = normalize_all(raw_items)
        result1 = ingest(db, normalized)
        assert result1.ingested == 1

        # Second run — same job should be skipped at DB level
        with _mock_httpx_get(response):
            raw_items = adapter.discover()
        normalized = normalize_all(raw_items)
        result2 = ingest(db, normalized)
        assert result2.duplicates_skipped == 1
        assert result2.ingested == 0

        # Only one opportunity in DB
        opps = db.query(Opportunity).filter(
            Opportunity.title == "Dedup Test"
        ).all()
        assert len(opps) == 1


# ── API endpoint tests ────────────────────────────────────────────────────


class TestDiscoverySourceEndpoint:
    """Test the new API endpoints."""

    def test_list_sources(self, client):
        response = client.get("/discovery/sources")
        assert response.status_code == 200
        data = response.json()
        assert "remotive" in data["sources"]

    def test_run_source_remotive_success(self, client, db):
        """POST /discovery/run/remotive with mocked HTTP."""
        job = _sample_remotive_job(id=300, title="API Test Job", company_name="API Co")
        response_data = _remotive_api_response([job])

        with _mock_httpx_get(response_data):
            response = client.post("/discovery/run/remotive")

        assert response.status_code == 200
        data = response.json()
        assert data["source_name"] == "remotive"
        assert data["raw_count"] >= 1
        assert data["ingested"] >= 1
        assert data["errors"] == []

        # Verify in DB
        opp = db.query(Opportunity).filter(
            Opportunity.title == "API Test Job"
        ).first()
        assert opp is not None

    def test_run_source_unknown_returns_error(self, client):
        response = client.post("/discovery/run/nonexistent_source")
        assert response.status_code == 200  # IngestionResult, not an HTTP error
        data = response.json()
        assert data["ingested"] == 0
        assert len(data["errors"]) > 0
        assert "Unknown source" in data["errors"][0]

    def test_run_source_network_failure_returns_error(self, client):
        import httpx

        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            response = client.post("/discovery/run/remotive")

        assert response.status_code == 200
        data = response.json()
        assert data["ingested"] == 0
        assert data["raw_count"] == 0
        assert len(data["errors"]) > 0

    def test_existing_raw_ingestion_endpoint_still_works(self, client, db):
        """POST /discovery/run (raw) still works for backward compatibility."""
        raw_item = {
            "source_name": "manual",
            "title": "Manual Entry",
            "company_name": "Manual Co",
        }
        response = client.post("/discovery/run", json=[raw_item])
        assert response.status_code == 200
        data = response.json()
        assert data["ingested"] == 1


# ── Existing API preservation tests ───────────────────────────────────────


class TestExistingAPIPreservation:
    """Verify existing Profile/Company/Lead/Opportunity APIs still work."""

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_opportunity_crud(self, client, db):
        """Full CRUD on opportunities still works."""
        # Create company first
        company_resp = client.post("/companies", json={"name": "CRUD Co"})
        company_id = company_resp.json()["id"]

        # Create opportunity
        opp_resp = client.post("/opportunities", json={
            "company_id": company_id,
            "type": "FULL_TIME",
            "title": "CRUD Test Role",
        })
        assert opp_resp.status_code == 201
        opp_id = opp_resp.json()["id"]

        # Read
        get_resp = client.get(f"/opportunities/{opp_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "CRUD Test Role"

        # Update
        patch_resp = client.patch(f"/opportunities/{opp_id}", json={
            "title": "Updated Role",
        })
        assert patch_resp.status_code == 200
        assert patch_resp.json()["title"] == "Updated Role"

        # Delete
        del_resp = client.delete(f"/opportunities/{opp_id}")
        assert del_resp.status_code == 204

        # Verify gone
        get_resp = client.get(f"/opportunities/{opp_id}")
        assert get_resp.status_code == 404
