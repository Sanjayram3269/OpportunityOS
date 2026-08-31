"""Tests for the Arbeitnow source adapter and source-driven discovery.

All HTTP calls are mocked — no live external requests are made.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.discovery.adapters.arbeitnow import ArbeitnowAdapter, _JOB_TYPE_MAP
from app.discovery.normalizer import normalize_all
from app.discovery.registry import create_adapter, get_adapter_class, list_source_names
from app.models.company import Company
from app.models.opportunity import Opportunity
from app.models.opportunity_evidence import OpportunityEvidence


# ── Fixtures ──────────────────────────────────────────────────────────────


def _sample_arbeitnow_job(**overrides) -> dict:
    """Return a realistic Arbeitnow API job record."""
    slug = overrides.get("slug", "senior-python-developer-berlin-12345")
    job = {
        "slug": slug,
        "company_name": "TechCo GmbH",
        "title": "Senior Python Developer",
        "description": "<p>We are looking for a senior Python developer...</p>",
        "remote": False,
        "url": f"https://www.arbeitnow.com/jobs/companies/techco/{slug}",
        "tags": ["Python", "Django", "Backend"],
        "job_types": ["full_time"],
        "location": "Berlin",
        "created_at": 1700000000,
    }
    job.update(overrides)
    return job


def _arbeitnow_api_response(jobs: list[dict]) -> dict:
    """Wrap a list of jobs in the Arbeitnow API response envelope."""
    return {
        "data": jobs,
        "links": {"self": "https://www.arbeitnow.com/api/job-board-api"},
    }


def _mock_httpx_get(response_data: dict, status_code: int = 200):
    """Return a context manager that patches httpx.get for Arbeitnow calls."""
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


class TestArbeitnowAdapterContract:
    """Verify the adapter satisfies the SourceAdapter interface."""

    def test_source_name(self):
        adapter = ArbeitnowAdapter()
        assert adapter.source_name == "arbeitnow"

    def test_discover_raises_on_failure(self):
        """discover() raises on network/server errors."""
        adapter = ArbeitnowAdapter()
        with _mock_httpx_get({}, status_code=500):
            with pytest.raises(Exception):
                adapter.discover()

    def test_discover_returns_raw_opportunities(self):
        """Successful fetch returns RawOpportunity instances."""
        from app.discovery.models import RawOpportunity

        adapter = ArbeitnowAdapter()
        response = _arbeitnow_api_response([_sample_arbeitnow_job()])
        with _mock_httpx_get(response):
            result = adapter.discover()

        assert len(result) == 1
        assert isinstance(result[0], RawOpportunity)
        assert result[0].source_name == "arbeitnow"
        assert result[0].external_id == "senior-python-developer-berlin-12345"
        assert result[0].title == "Senior Python Developer"
        assert result[0].company_name == "TechCo GmbH"


# ── Successful parsing tests ──────────────────────────────────────────────


class TestArbeitnowAdapterParsing:
    """Test parsing of various Arbeitnow job records."""

    def test_full_job_record(self):
        adapter = ArbeitnowAdapter()
        response = _arbeitnow_api_response([_sample_arbeitnow_job()])
        with _mock_httpx_get(response):
            result = adapter.discover()

        opp = result[0]
        assert opp.external_id == "senior-python-developer-berlin-12345"
        assert opp.source_url == "https://www.arbeitnow.com/jobs/companies/techco/senior-python-developer-berlin-12345"
        assert opp.title == "Senior Python Developer"
        assert opp.company_name == "TechCo GmbH"
        assert opp.opportunity_type == "FULL_TIME"
        assert opp.location == "Berlin"
        assert opp.description == "<p>We are looking for a senior Python developer...</p>"
        assert opp.metadata["tags"] == "Python, Django, Backend"
        assert opp.metadata["created_at"] == 1700000000
        assert opp.deadline is None  # Arbeitnow does not provide deadlines
        assert opp.salary_or_value is None

    def test_job_type_mapping(self):
        """Arbeitnow job_types map correctly."""
        for raw_type, expected in _JOB_TYPE_MAP.items():
            adapter = ArbeitnowAdapter()
            job = _sample_arbeitnow_job(job_types=[raw_type])
            response = _arbeitnow_api_response([job])
            with _mock_httpx_get(response):
                result = adapter.discover()
            assert result[0].opportunity_type == expected, f"{raw_type} should map to {expected}"

    def test_remote_flag_sets_location(self):
        """Remote flag is appended to location."""
        adapter = ArbeitnowAdapter()
        job = _sample_arbeitnow_job(remote=True, location="Berlin")
        response = _arbeitnow_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].location == "Berlin (Remote)"

    def test_remote_flag_no_location(self):
        """Remote flag with no location results in 'Remote'."""
        adapter = ArbeitnowAdapter()
        job = _sample_arbeitnow_job(remote=True, location="")
        response = _arbeitnow_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].location == "Remote"

    def test_not_remote(self):
        """Non-remote job keeps location as-is."""
        adapter = ArbeitnowAdapter()
        job = _sample_arbeitnow_job(remote=False, location="Munich")
        response = _arbeitnow_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].location == "Munich"

    def test_missing_optional_fields(self):
        """Job with only required fields (slug, title, company_name) parses cleanly."""
        adapter = ArbeitnowAdapter()
        job = {
            "slug": "minimal-job",
            "title": "Simple Role",
            "company_name": "Simple Co",
        }
        response = _arbeitnow_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()

        opp = result[0]
        assert opp.external_id == "minimal-job"
        assert opp.source_url is None
        assert opp.description is None
        assert opp.opportunity_type == "OTHER"  # no job_types → infer from title → OTHER
        assert opp.location is None
        assert opp.deadline is None
        assert opp.metadata == {}

    def test_empty_string_fields_treated_as_none(self):
        """Empty strings in optional fields are normalized to None."""
        adapter = ArbeitnowAdapter()
        job = _sample_arbeitnow_job(
            url="",
            description="  ",
            location="",
            tags=[],
            job_types=[],
        )
        response = _arbeitnow_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()

        opp = result[0]
        assert opp.source_url is None
        assert opp.description is None
        assert opp.location is None
        assert "tags" not in opp.metadata
        assert opp.metadata.get("created_at") is not None  # always present from API

    def test_type_inference_from_title(self):
        """When job_types is empty, title keywords are used for inference."""
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
            adapter = ArbeitnowAdapter()
            job = {"slug": "test", "title": title, "company_name": "Test Co"}
            response = _arbeitnow_api_response([job])
            with _mock_httpx_get(response):
                result = adapter.discover()
            assert result[0].opportunity_type == expected_type, (
                f"Title '{title}' should infer as {expected_type}"
            )

    def test_multiple_jobs_in_batch(self):
        adapter = ArbeitnowAdapter()
        jobs = [
            _sample_arbeitnow_job(slug="job-a", title="Job A", company_name="Co A"),
            _sample_arbeitnow_job(slug="job-b", title="Job B", company_name="Co B"),
            _sample_arbeitnow_job(slug="job-c", title="Job C", company_name="Co C"),
        ]
        response = _arbeitnow_api_response(jobs)
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert len(result) == 3
        titles = {r.title for r in result}
        assert titles == {"Job A", "Job B", "Job C"}

    def test_multiple_job_types_uses_first_recognized(self):
        """When multiple job_types are provided, the first recognized one is used."""
        adapter = ArbeitnowAdapter()
        job = _sample_arbeitnow_job(job_types=["unknown_type", "full_time", "contract"])
        response = _arbeitnow_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].opportunity_type == "FULL_TIME"

    def test_all_unrecognized_job_types_falls_to_other(self):
        adapter = ArbeitnowAdapter()
        job = _sample_arbeitnow_job(job_types=["unknown", "random"])
        response = _arbeitnow_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].opportunity_type == "OTHER"


# ── Failure behavior tests ────────────────────────────────────────────────


class TestArbeitnowAdapterFailures:
    """Verify the adapter raises on errors (caller is responsible for handling)."""

    def test_network_timeout_raises(self):
        import httpx

        adapter = ArbeitnowAdapter()
        with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(httpx.TimeoutException):
                adapter.discover()

    def test_connection_error_raises(self):
        import httpx

        adapter = ArbeitnowAdapter()
        with patch("httpx.get", side_effect=httpx.ConnectError("connection refused")):
            with pytest.raises(httpx.ConnectError):
                adapter.discover()

    def test_http_error_raises(self):
        import httpx

        adapter = ArbeitnowAdapter()
        with _mock_httpx_get({}, status_code=429):
            with pytest.raises(httpx.HTTPStatusError):
                adapter.discover()

    def test_malformed_json_raises(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("no JSON")
        mock_response.raise_for_status.return_value = None

        adapter = ArbeitnowAdapter()
        with patch("httpx.get", return_value=mock_response):
            with pytest.raises(ValueError, match="no JSON"):
                adapter.discover()

    def test_missing_data_key_raises(self):
        adapter = ArbeitnowAdapter()
        with _mock_httpx_get({"unexpected": "structure"}):
            with pytest.raises(ValueError, match="Expected 'data' list"):
                adapter.discover()

    def test_data_not_a_list_raises(self):
        adapter = ArbeitnowAdapter()
        with _mock_httpx_get({"data": "not a list"}):
            with pytest.raises(ValueError, match="Expected 'data' list"):
                adapter.discover()

    def test_response_not_a_dict_raises(self):
        adapter = ArbeitnowAdapter()
        with _mock_httpx_get([1, 2, 3]):
            with pytest.raises(ValueError, match="Expected JSON object"):
                adapter.discover()

    def test_missing_title_skips_job(self):
        adapter = ArbeitnowAdapter()
        job = {"slug": "no-title", "company_name": "Co"}
        response = _arbeitnow_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert len(result) == 0

    def test_missing_company_skips_job(self):
        adapter = ArbeitnowAdapter()
        job = {"slug": "no-company", "title": "Role"}
        response = _arbeitnow_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert len(result) == 0

    def test_mixed_valid_and_invalid_jobs(self):
        """Valid jobs are returned, invalid ones are skipped."""
        adapter = ArbeitnowAdapter()
        jobs = [
            _sample_arbeitnow_job(slug="good-1", title="Good Job", company_name="Good Co"),
            {"slug": "bad"},  # missing title and company
            _sample_arbeitnow_job(slug="good-2", title="Another Good Job", company_name="Good Co 2"),
        ]
        response = _arbeitnow_api_response(jobs)
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert len(result) == 2
        assert result[0].external_id == "good-1"
        assert result[1].external_id == "good-2"


# ── Adapter registry tests ────────────────────────────────────────────────


class TestArbeitnowRegistry:
    def test_list_source_names(self):
        names = list_source_names()
        assert "arbeitnow" in names
        assert "remotive" in names

    def test_get_adapter_class(self):
        cls = get_adapter_class("arbeitnow")
        assert cls is not None
        assert issubclass(cls, ArbeitnowAdapter)

    def test_create_adapter(self):
        adapter = create_adapter("arbeitnow")
        assert isinstance(adapter, ArbeitnowAdapter)
        assert adapter.source_name == "arbeitnow"

    def test_case_insensitive_lookup(self):
        adapter = create_adapter("Arbeitnow")
        assert isinstance(adapter, ArbeitnowAdapter)


# ── Normalization + Arbeitnow integration tests ───────────────────────────


class TestArbeitnowNormalization:
    """Test that Arbeitnow raw output normalizes correctly."""

    def test_normalize_arbeitnow_raw(self):
        adapter = ArbeitnowAdapter()
        response = _arbeitnow_api_response([_sample_arbeitnow_job()])
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        assert len(normalized) == 1

        opp = normalized[0]
        assert opp.source_name == "arbeitnow"
        assert opp.external_id == "senior-python-developer-berlin-12345"
        assert opp.normalized_title == "Senior Python Developer"
        assert opp.normalized_company_name == "TechCo GmbH"
        assert opp.opportunity_type == "FULL_TIME"
        assert opp.normalized_location == "Berlin"

    def test_normalize_all_batch(self):
        adapter = ArbeitnowAdapter()
        jobs = [
            _sample_arbeitnow_job(slug=f"job-{i}", title=f"  Job {i}  ", company_name=f"  Co {i}  ")
            for i in range(5)
        ]
        response = _arbeitnow_api_response(jobs)
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        assert len(normalized) == 5
        for opp in normalized:
            assert opp.normalized_title == opp.normalized_title.strip()
            assert opp.normalized_company_name == opp.normalized_company_name.strip()


# ── Deduplication integration tests ───────────────────────────────────────


class TestArbeitnowDeduplication:
    """Test that Arbeitnow-sourced opportunities deduplicate correctly."""

    def test_deduplicate_by_external_id(self):
        """Same slug from same source is deduped."""
        from app.discovery.deduplicator import deduplicate

        adapter = ArbeitnowAdapter()
        job = _sample_arbeitnow_job(slug="same-job")
        response = _arbeitnow_api_response([job, job])
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        assert len(deduped) == 1

    def test_deduplicate_by_url(self):
        """Same URL from same source is deduped."""
        from app.discovery.deduplicator import deduplicate

        job1 = _sample_arbeitnow_job(slug="job-1", title="Job A")
        job2 = _sample_arbeitnow_job(slug="job-2", title="Job B")
        job2["url"] = job1["url"]  # same URL

        adapter = ArbeitnowAdapter()
        response = _arbeitnow_api_response([job1, job2])
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        assert len(deduped) == 1


# ── Full pipeline integration ─────────────────────────────────────────────


class TestArbeitnowIngestionPipeline:
    """End-to-end: adapter → normalize → dedup → ingest into the database."""

    def test_full_pipeline_single_job(self, db):
        from app.discovery.deduplicator import deduplicate
        from app.discovery.normalizer import normalize_all
        from app.services.discovery import ingest

        adapter = ArbeitnowAdapter()
        job = _sample_arbeitnow_job()
        response = _arbeitnow_api_response([job])
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

        opp = db.query(Opportunity).filter(
            Opportunity.title == "Senior Python Developer"
        ).first()
        assert opp is not None
        assert opp.type == "FULL_TIME"
        assert opp.status == "DISCOVERED"
        assert opp.source_url is not None

        company = db.query(Company).filter(Company.name == "TechCo GmbH").first()
        assert company is not None
        assert opp.company_id == company.id

    def test_full_pipeline_multiple_jobs(self, db):
        from app.discovery.deduplicator import deduplicate
        from app.discovery.normalizer import normalize_all
        from app.services.discovery import ingest

        adapter = ArbeitnowAdapter()
        jobs = [
            _sample_arbeitnow_job(slug="fe-dev", title="Frontend Dev", company_name="Co A"),
            _sample_arbeitnow_job(slug="be-dev", title="Backend Dev", company_name="Co B"),
            _sample_arbeitnow_job(slug="devops", title="DevOps Eng", company_name="Co A"),
        ]
        response = _arbeitnow_api_response(jobs)
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        result = ingest(db, deduped)

        assert result.ingested == 3
        assert result.companies_created == 2  # Co A shared

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

        adapter = ArbeitnowAdapter()
        job = _sample_arbeitnow_job(slug="dedup-test", title="Dedup Test", company_name="Dedup Co")
        response = _arbeitnow_api_response([job])

        # First run
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

        opps = db.query(Opportunity).filter(
            Opportunity.title == "Dedup Test"
        ).all()
        assert len(opps) == 1

    def test_deadline_always_none(self, db):
        """Arbeitnow never provides deadlines — verify None in DB."""
        from app.discovery.deduplicator import deduplicate
        from app.discovery.normalizer import normalize_all
        from app.services.discovery import ingest

        adapter = ArbeitnowAdapter()
        job = _sample_arbeitnow_job(slug="no-deadline")
        response = _arbeitnow_api_response([job])
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        ingest(db, deduped)

        opp = db.query(Opportunity).filter(
            Opportunity.title == "Senior Python Developer"
        ).first()
        assert opp.deadline is None


# ── API endpoint tests ────────────────────────────────────────────────────


class TestArbeitnowEndpoint:
    """Test the API endpoint with Arbeitnow as source."""

    def test_run_source_arbeitnow_success(self, client, db):
        """POST /discovery/run/arbeitnow with mocked HTTP."""
        job = _sample_arbeitnow_job(slug="api-test", title="API Test Job", company_name="API Co")
        response_data = _arbeitnow_api_response([job])

        with _mock_httpx_get(response_data):
            response = client.post("/discovery/run/arbeitnow")

        assert response.status_code == 200
        data = response.json()
        assert data["source_name"] == "arbeitnow"
        assert data["raw_count"] >= 1
        assert data["ingested"] >= 1
        assert data["errors"] == []

        opp = db.query(Opportunity).filter(
            Opportunity.title == "API Test Job"
        ).first()
        assert opp is not None

    def test_list_sources_includes_arbeitnow(self, client):
        response = client.get("/discovery/sources")
        assert response.status_code == 200
        data = response.json()
        assert "arbeitnow" in data["sources"]
        assert "remotive" in data["sources"]


# ── Remotive regression tests ─────────────────────────────────────────────


class TestRemotiveRegression:
    """Verify Remotive adapter still works after adding Arbeitnow."""

    def test_remotive_adapter_still_works(self):
        from app.discovery.adapters.remotive import RemotiveAdapter

        adapter = RemotiveAdapter()
        assert adapter.source_name == "remotive"

        # Quick mock test
        job = {
            "id": 1,
            "url": "https://remotive.com/test",
            "title": "Test Job",
            "company_name": "Test Co",
            "job_type": "full_time",
        }
        response = {"jobs": [job]}
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert len(result) == 1
        assert result[0].source_name == "remotive"

    def test_remotive_ingestion_still_works(self, db):
        from app.discovery.deduplicator import deduplicate
        from app.discovery.normalizer import normalize_all
        from app.services.discovery import ingest
        from app.discovery.adapters.remotive import RemotiveAdapter

        adapter = RemotiveAdapter()
        job = {
            "id": 9999,
            "url": "https://remotive.com/test-regression",
            "title": "Regression Test",
            "company_name": "Regression Co",
            "job_type": "internship",
            "candidate_required_location": "Remote",
        }
        response = {"jobs": [job]}
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        result = ingest(db, deduped)

        assert result.ingested == 1
        opp = db.query(Opportunity).filter(
            Opportunity.title == "Regression Test"
        ).first()
        assert opp is not None
        assert opp.type == "INTERNSHIP"


# ── Existing API preservation tests ───────────────────────────────────────


class TestExistingAPIPreservation:
    """Verify existing APIs still work."""

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_opportunity_crud(self, client, db):
        company_resp = client.post("/companies", json={"name": "Arbeitnow Test Co"})
        company_id = company_resp.json()["id"]

        opp_resp = client.post("/opportunities", json={
            "company_id": company_id,
            "type": "FULL_TIME",
            "title": "Arbeitnow CRUD Test",
        })
        assert opp_resp.status_code == 201
        opp_id = opp_resp.json()["id"]

        get_resp = client.get(f"/opportunities/{opp_id}")
        assert get_resp.status_code == 200

        del_resp = client.delete(f"/opportunities/{opp_id}")
        assert del_resp.status_code == 204
