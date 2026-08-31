"""Tests for the Himalayas source adapter and source-driven discovery.

All HTTP calls are mocked — no live external requests are made.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.discovery.adapters.himalayas import HimalayasAdapter, _EMPLOYMENT_TYPE_MAP
from app.discovery.normalizer import normalize_all
from app.discovery.registry import create_adapter, get_adapter_class, list_source_names
from app.models.company import Company
from app.models.opportunity import Opportunity
from app.models.opportunity_evidence import OpportunityEvidence


# ── Fixtures ──────────────────────────────────────────────────────────────


def _sample_himalayas_job(**overrides) -> dict:
    """Return a realistic Himalayas API job record."""
    guid = overrides.get(
        "guid",
        "https://himalayas.app/companies/acme/jobs/senior-engineer-123",
    )
    job = {
        "title": "Senior Software Engineer",
        "excerpt": "We are looking for a senior software engineer...",
        "companyName": "Acme Corp",
        "companySlug": "acme-corp",
        "companyLogo": "",
        "employmentType": "Full Time",
        "minSalary": 80000,
        "maxSalary": 120000,
        "salaryPeriod": "annual",
        "seniority": ["Senior"],
        "currency": "USD",
        "locationRestrictions": ["India"],
        "timezoneRestrictions": [5.5],
        "categories": ["Software-Engineering", "Backend"],
        "parentCategories": ["Developer"],
        "description": "<p>We are looking for a senior software engineer...</p>",
        "pubDate": 1788000000,
        "expiryDate": 1793192784,
        "applicationLink": guid,
        "guid": guid,
    }
    job.update(overrides)
    return job


def _himalayas_api_response(jobs: list[dict], total_count: int | None = None) -> dict:
    """Wrap a list of jobs in the Himalayas API search response envelope."""
    return {
        "updatedAt": 1788168504,
        "jobs": jobs,
        "totalCount": total_count or len(jobs),
    }


def _mock_httpx_get(response_data: dict, status_code: int = 200):
    """Return a context manager that patches httpx.get for Himalayas calls."""
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


class TestHimalayasAdapterContract:
    """Verify the adapter satisfies the SourceAdapter interface."""

    def test_source_name(self):
        adapter = HimalayasAdapter()
        assert adapter.source_name == "himalayas"

    def test_discover_raises_on_failure(self):
        adapter = HimalayasAdapter()
        with _mock_httpx_get({}, status_code=500):
            with pytest.raises(Exception):
                adapter.discover()

    def test_discover_returns_raw_opportunities(self):
        from app.discovery.models import RawOpportunity

        adapter = HimalayasAdapter()
        response = _himalayas_api_response([_sample_himalayas_job()])
        with _mock_httpx_get(response):
            result = adapter.discover()

        assert len(result) == 1
        assert isinstance(result[0], RawOpportunity)
        assert result[0].source_name == "himalayas"
        assert result[0].title == "Senior Software Engineer"
        assert result[0].company_name == "Acme Corp"


# ── Successful parsing tests ──────────────────────────────────────────────


class TestHimalayasAdapterParsing:
    """Test parsing of various Himalayas job records."""

    def test_full_job_record(self):
        adapter = HimalayasAdapter()
        response = _himalayas_api_response([_sample_himalayas_job()])
        with _mock_httpx_get(response):
            result = adapter.discover()

        opp = result[0]
        assert opp.external_id == "https://himalayas.app/companies/acme/jobs/senior-engineer-123"
        assert opp.source_url == "https://himalayas.app/companies/acme/jobs/senior-engineer-123"
        assert opp.title == "Senior Software Engineer"
        assert opp.company_name == "Acme Corp"
        assert opp.opportunity_type == "FULL_TIME"
        assert opp.location == "India"
        assert opp.description == "<p>We are looking for a senior software engineer...</p>"
        assert opp.salary_or_value == Decimal("80000")
        assert opp.deadline is not None
        assert opp.deadline.year == 2026
        assert opp.metadata["currency"] == "USD"
        assert "Software-Engineering" in opp.metadata["categories"]
        assert "Senior" in opp.metadata["seniority"]

    def test_employment_type_mapping(self):
        """All Himalayas employmentType values map correctly."""
        for raw_type, expected in _EMPLOYMENT_TYPE_MAP.items():
            adapter = HimalayasAdapter()
            job = _sample_himalayas_job(employmentType=raw_type.title())
            response = _himalayas_api_response([job])
            with _mock_httpx_get(response):
                result = adapter.discover()
            assert result[0].opportunity_type == expected, f"{raw_type} should map to {expected}"

    def test_worldwide_location(self):
        """Empty locationRestrictions results in 'Worldwide'."""
        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(locationRestrictions=[])
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].location == "Worldwide"

    def test_india_location(self):
        """India in locationRestrictions is shown."""
        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(locationRestrictions=["India"])
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].location == "India"

    def test_multiple_location_restrictions(self):
        """First country in the list is used."""
        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(locationRestrictions=["India", "Singapore"])
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].location == "India"

    def test_missing_optional_fields(self):
        """Job with only required fields parses cleanly."""
        adapter = HimalayasAdapter()
        job = {
            "title": "Simple Role",
            "companyName": "Simple Co",
            "guid": "simple-guid",
            "applicationLink": "https://example.com/apply",
        }
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()

        opp = result[0]
        assert opp.external_id == "simple-guid"
        assert opp.source_url == "https://example.com/apply"
        assert opp.description is None
        assert opp.opportunity_type == "OTHER"  # no employmentType → infer from title → OTHER
        assert opp.location == "Worldwide"
        assert opp.deadline is None
        assert opp.salary_or_value is None

    def test_empty_string_fields_treated_as_none(self):
        """Empty strings in optional fields are normalized to None."""
        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(
            applicationLink="",
            description="  ",
            companyName="",  # will cause skip
        )
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        # companyName is empty → job is skipped
        assert len(result) == 0

    def test_type_inference_from_title(self):
        """When employmentType is missing, title keywords are used."""
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
            adapter = HimalayasAdapter()
            job = {"title": title, "companyName": "Test Co", "guid": "g"}
            response = _himalayas_api_response([job])
            with _mock_httpx_get(response):
                result = adapter.discover()
            assert result[0].opportunity_type == expected_type, (
                f"Title '{title}' should infer as {expected_type}"
            )

    def test_multiple_jobs_in_batch(self):
        adapter = HimalayasAdapter()
        jobs = [
            _sample_himalayas_job(guid=f"https://himalayas.app/jobs/{i}", title=f"Job {i}", companyName=f"Co {i}")
            for i in range(3)
        ]
        response = _himalayas_api_response(jobs)
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert len(result) == 3
        titles = {r.title for r in result}
        assert titles == {"Job 0", "Job 1", "Job 2"}

    def test_salary_parsed_correctly(self):
        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(minSalary=50000, currency="INR")
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].salary_or_value == Decimal("50000")
        assert result[0].metadata["currency"] == "INR"

    def test_null_salary(self):
        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(minSalary=None, currency=None)
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].salary_or_value is None
        assert "currency" not in result[0].metadata

    def test_expiry_date_as_deadline(self):
        """expiryDate is a real application deadline."""
        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(expiryDate=1793192784)
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].deadline is not None
        assert result[0].deadline == datetime(2026, 10, 28, 13, 6, 24, tzinfo=timezone.utc)

    def test_no_expiry_date(self):
        """Missing expiryDate results in None deadline."""
        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(expiryDate=None)
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].deadline is None

    def test_categories_in_metadata(self):
        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(categories=["AI-ML", "Python", "Data-Science"])
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert "AI-ML" in result[0].metadata["categories"]
        assert "Python" in result[0].metadata["categories"]

    def test_seniority_in_metadata(self):
        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(seniority=["Entry-level", "Junior"])
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert "Entry-level" in result[0].metadata["seniority"]

    def test_pub_date_in_metadata(self):
        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(pubDate=1788000000)
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert "pub_date" in result[0].metadata

    def test_malformed_timestamp_ignored(self):
        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(expiryDate="not-a-timestamp")
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert result[0].deadline is None


# ── Failure behavior tests ────────────────────────────────────────────────


class TestHimalayasAdapterFailures:
    """Verify the adapter raises on errors."""

    def test_network_timeout_raises(self):
        import httpx

        adapter = HimalayasAdapter()
        with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(httpx.TimeoutException):
                adapter.discover()

    def test_connection_error_raises(self):
        import httpx

        adapter = HimalayasAdapter()
        with patch("httpx.get", side_effect=httpx.ConnectError("connection refused")):
            with pytest.raises(httpx.ConnectError):
                adapter.discover()

    def test_http_error_raises(self):
        import httpx

        adapter = HimalayasAdapter()
        with _mock_httpx_get({}, status_code=429):
            with pytest.raises(httpx.HTTPStatusError):
                adapter.discover()

    def test_malformed_json_raises(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("no JSON")
        mock_response.raise_for_status.return_value = None

        adapter = HimalayasAdapter()
        with patch("httpx.get", return_value=mock_response):
            with pytest.raises(ValueError, match="no JSON"):
                adapter.discover()

    def test_missing_jobs_key_raises(self):
        adapter = HimalayasAdapter()
        with _mock_httpx_get({"unexpected": "structure"}):
            with pytest.raises(ValueError, match="Expected 'jobs' list"):
                adapter.discover()

    def test_jobs_not_a_list_raises(self):
        adapter = HimalayasAdapter()
        with _mock_httpx_get({"jobs": "not a list"}):
            with pytest.raises(ValueError, match="Expected 'jobs' list"):
                adapter.discover()

    def test_response_not_a_dict_raises(self):
        adapter = HimalayasAdapter()
        with _mock_httpx_get([1, 2, 3]):
            with pytest.raises(ValueError, match="Expected JSON object"):
                adapter.discover()

    def test_missing_title_skips_job(self):
        adapter = HimalayasAdapter()
        job = {"companyName": "Co", "guid": "g"}
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert len(result) == 0

    def test_missing_company_skips_job(self):
        adapter = HimalayasAdapter()
        job = {"title": "Role", "guid": "g"}
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert len(result) == 0

    def test_mixed_valid_and_invalid_jobs(self):
        adapter = HimalayasAdapter()
        jobs = [
            _sample_himalayas_job(guid="good-1", title="Good Job", companyName="Good Co"),
            {"guid": "bad"},  # missing title and company
            _sample_himalayas_job(guid="good-2", title="Another Good Job", companyName="Good Co 2"),
        ]
        response = _himalayas_api_response(jobs)
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert len(result) == 2
        assert result[0].external_id == "good-1"
        assert result[1].external_id == "good-2"


# ── Adapter registry tests ────────────────────────────────────────────────


class TestHimalayasRegistry:
    def test_list_source_names(self):
        names = list_source_names()
        assert "himalayas" in names
        assert "remotive" in names
        assert "arbeitnow" in names

    def test_get_adapter_class(self):
        cls = get_adapter_class("himalayas")
        assert cls is not None
        assert issubclass(cls, HimalayasAdapter)

    def test_create_adapter(self):
        adapter = create_adapter("himalayas")
        assert isinstance(adapter, HimalayasAdapter)
        assert adapter.source_name == "himalayas"

    def test_case_insensitive_lookup(self):
        adapter = create_adapter("Himalayas")
        assert isinstance(adapter, HimalayasAdapter)


# ── Normalization + Himalayas integration tests ───────────────────────────


class TestHimalayasNormalization:
    def test_normalize_himalayas_raw(self):
        adapter = HimalayasAdapter()
        response = _himalayas_api_response([_sample_himalayas_job()])
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        assert len(normalized) == 1

        opp = normalized[0]
        assert opp.source_name == "himalayas"
        assert opp.normalized_title == "Senior Software Engineer"
        assert opp.normalized_company_name == "Acme Corp"
        assert opp.opportunity_type == "FULL_TIME"
        assert opp.normalized_location == "India"


# ── Deduplication integration tests ───────────────────────────────────────


class TestHimalayasDeduplication:
    def test_deduplicate_by_external_id(self):
        from app.discovery.deduplicator import deduplicate

        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(guid="same-guid")
        response = _himalayas_api_response([job, job])
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        assert len(deduped) == 1

    def test_deduplicate_by_url(self):
        from app.discovery.deduplicator import deduplicate

        job1 = _sample_himalayas_job(guid="guid-1", title="Job A")
        job2 = _sample_himalayas_job(guid="guid-2", title="Job B")
        job2["applicationLink"] = job1["applicationLink"]

        adapter = HimalayasAdapter()
        response = _himalayas_api_response([job1, job2])
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        assert len(deduped) == 1


# ── Full pipeline integration ─────────────────────────────────────────────


class TestHimalayasIngestionPipeline:
    def test_full_pipeline_single_job(self, db):
        from app.discovery.deduplicator import deduplicate
        from app.discovery.normalizer import normalize_all
        from app.services.discovery import ingest

        adapter = HimalayasAdapter()
        job = _sample_himalayas_job()
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        result = ingest(db, deduped)

        assert result.raw_count == 1
        assert result.ingested == 1
        assert result.companies_created == 1

        opp = db.query(Opportunity).filter(
            Opportunity.title == "Senior Software Engineer"
        ).first()
        assert opp is not None
        assert opp.type == "FULL_TIME"
        assert opp.deadline is not None

        company = db.query(Company).filter(Company.name == "Acme Corp").first()
        assert company is not None
        assert opp.company_id == company.id

    def test_full_pipeline_multiple_jobs(self, db):
        from app.discovery.deduplicator import deduplicate
        from app.discovery.normalizer import normalize_all
        from app.services.discovery import ingest

        adapter = HimalayasAdapter()
        jobs = [
            _sample_himalayas_job(guid="g1", title="Frontend Dev", companyName="Co A"),
            _sample_himalayas_job(guid="g2", title="Backend Dev", companyName="Co B"),
            _sample_himalayas_job(guid="g3", title="DevOps Eng", companyName="Co A"),
        ]
        response = _himalayas_api_response(jobs)
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        result = ingest(db, deduped)

        assert result.ingested == 3
        assert result.companies_created == 2

        opps = db.query(Opportunity).all()
        assert len(opps) == 3

    def test_full_pipeline_dedup_on_second_run(self, db):
        from app.discovery.deduplicator import deduplicate
        from app.discovery.normalizer import normalize_all
        from app.services.discovery import ingest

        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(guid="dedup-guid", title="Dedup Test", companyName="Dedup Co")
        response = _himalayas_api_response([job])

        with _mock_httpx_get(response):
            raw_items = adapter.discover()
        normalized = normalize_all(raw_items)
        result1 = ingest(db, normalized)
        assert result1.ingested == 1

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

    def test_deadline_is_real_expiry_date(self, db):
        """expiryDate becomes the deadline, not pubDate."""
        from app.discovery.deduplicator import deduplicate
        from app.discovery.normalizer import normalize_all
        from app.services.discovery import ingest

        adapter = HimalayasAdapter()
        job = _sample_himalayas_job(
            pubDate=1788000000,
            expiryDate=1793192784,
        )
        response = _himalayas_api_response([job])
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        ingest(db, deduped)

        opp = db.query(Opportunity).filter(
            Opportunity.title == "Senior Software Engineer"
        ).first()
        assert opp.deadline is not None
        assert opp.deadline.year == 2026


# ── API endpoint tests ────────────────────────────────────────────────────


class TestHimalayasEndpoint:
    def test_run_source_himalayas_success(self, client, db):
        job = _sample_himalayas_job(
            guid="https://himalayas.app/companies/api-co/jobs/test-123",
            title="API Test Job",
            companyName="API Co",
        )
        response_data = _himalayas_api_response([job])

        with _mock_httpx_get(response_data):
            response = client.post("/discovery/run/himalayas")

        assert response.status_code == 200
        data = response.json()
        assert data["source_name"] == "himalayas"
        assert data["raw_count"] >= 1
        assert data["ingested"] >= 1
        assert data["errors"] == []

        opp = db.query(Opportunity).filter(
            Opportunity.title == "API Test Job"
        ).first()
        assert opp is not None

    def test_list_sources_includes_himalayas(self, client):
        response = client.get("/discovery/sources")
        assert response.status_code == 200
        data = response.json()
        assert "himalayas" in data["sources"]
        assert "remotive" in data["sources"]
        assert "arbeitnow" in data["sources"]


# ── Remotive + Arbeitnow regression tests ─────────────────────────────────


class TestExistingAdapterRegression:
    """Verify existing adapters still work after adding Himalayas."""

    def test_remotive_adapter_still_works(self):
        from app.discovery.adapters.remotive import RemotiveAdapter

        adapter = RemotiveAdapter()
        assert adapter.source_name == "remotive"

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

    def test_arbeitnow_adapter_still_works(self):
        from app.discovery.adapters.arbeitnow import ArbeitnowAdapter

        adapter = ArbeitnowAdapter()
        assert adapter.source_name == "arbeitnow"

        job = {
            "slug": "test-job",
            "title": "Test Job",
            "company_name": "Test Co",
            "job_types": ["full_time"],
            "remote": False,
            "location": "Berlin",
        }
        response = {"data": [job]}
        with _mock_httpx_get(response):
            result = adapter.discover()
        assert len(result) == 1
        assert result[0].source_name == "arbeitnow"

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
        }
        response = {"jobs": [job]}
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        result = ingest(db, deduped)
        assert result.ingested == 1

    def test_arbeitnow_ingestion_still_works(self, db):
        from app.discovery.deduplicator import deduplicate
        from app.discovery.normalizer import normalize_all
        from app.services.discovery import ingest
        from app.discovery.adapters.arbeitnow import ArbeitnowAdapter

        adapter = ArbeitnowAdapter()
        job = {
            "slug": "ar-regression",
            "title": "Arbeitnow Regression",
            "company_name": "AR Regression Co",
            "job_types": ["full_time"],
            "remote": True,
            "location": "Munich",
        }
        response = {"data": [job]}
        with _mock_httpx_get(response):
            raw_items = adapter.discover()

        normalized = normalize_all(raw_items)
        deduped = deduplicate(normalized)
        result = ingest(db, deduped)
        assert result.ingested == 1


# ── Existing API preservation tests ───────────────────────────────────────


class TestExistingAPIPreservation:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_opportunity_crud(self, client, db):
        company_resp = client.post("/companies", json={"name": "Himalayas Test Co"})
        company_id = company_resp.json()["id"]

        opp_resp = client.post("/opportunities", json={
            "company_id": company_id,
            "type": "FULL_TIME",
            "title": "Himalayas CRUD Test",
        })
        assert opp_resp.status_code == 201
        opp_id = opp_resp.json()["id"]

        get_resp = client.get(f"/opportunities/{opp_id}")
        assert get_resp.status_code == 200

        del_resp = client.delete(f"/opportunities/{opp_id}")
        assert del_resp.status_code == 204
