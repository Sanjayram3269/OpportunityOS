"""Comprehensive tests for Discovery Intelligence 2.0.

Covers:
  - Source metadata
  - Location intelligence
  - Enrichment layer
  - Enhanced type classification
  - Skill extraction
  - Company resolution
  - Enhanced discovery API
  - Stub adapters
  - Backward compatibility
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# ── Source Metadata Tests ───────────────────────────────────────────────────


class TestSourceMetadata:
    """Test source metadata registry."""

    def test_list_source_metadata(self):
        from app.discovery.metadata import list_source_metadata

        all_meta = list_source_metadata()
        assert len(all_meta) >= 6  # 3 active + 3 stubs

    def test_get_metadata_for_known_source(self):
        from app.discovery.metadata import get_source_metadata

        meta = get_source_metadata("remotive")
        assert meta is not None
        assert meta.name == "remotive"
        assert meta.display_name == "Remotive"
        assert meta.requires_auth is False
        assert meta.adapter_available is True

    def test_get_metadata_for_unknown_source(self):
        from app.discovery.metadata import get_source_metadata

        assert get_source_metadata("nonexistent") is None

    def test_auth_required_sources(self):
        from app.discovery.metadata import list_source_metadata

        all_meta = list_source_metadata()
        auth_required = [m for m in all_meta if m.requires_auth]
        names = {m.name for m in auth_required}
        assert "linkedin" in names
        assert "handshake" in names
        assert "jobstep" in names

    def test_active_sources_have_no_auth(self):
        from app.discovery.metadata import list_enabled_sources

        active = list_enabled_sources()
        assert len(active) >= 3
        names = {m.name for m in active}
        assert "remotive" in names
        assert "linkedin" not in names
        assert "handshake" not in names

    def test_metadata_to_dict(self):
        from app.discovery.metadata import get_source_metadata

        meta = get_source_metadata("remotive")
        d = meta.to_dict()
        assert isinstance(d, dict)
        assert d["name"] == "remotive"
        assert d["enabled"] is True

    def test_stub_sources_not_enabled(self):
        from app.discovery.metadata import get_source_metadata

        for name in ("linkedin", "handshake", "jobstep"):
            meta = get_source_metadata(name)
            assert meta is not None
            assert meta.enabled is False
            assert meta.requires_auth is True


# ── Location Intelligence Tests ─────────────────────────────────────────────


class TestLocationIntelligence:
    """Test location normalization and analysis."""

    def test_none_location(self):
        from app.discovery.location import analyze_location

        info = analyze_location(None)
        assert info.normalized is None
        assert info.city is None
        assert info.country is None
        assert info.is_remote is False

    def test_empty_location(self):
        from app.discovery.location import analyze_location

        info = analyze_location("")
        assert info.normalized is None

    def test_bengaluru_normalization(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Bengaluru")
        assert info.city == "Bengaluru"
        assert info.country == "India"

    def test_bangalore_normalization(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Bangalore")
        assert info.city == "Bengaluru"
        assert info.country == "India"

    def test_bangalore_india_normalization(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Bangalore, India")
        assert info.city == "Bengaluru"
        assert info.country == "India"

    def test_chennai_normalization(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Chennai")
        assert info.city == "Chennai"
        assert info.country == "India"

    def test_hyderabad_normalization(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Hyderabad")
        assert info.city == "Hyderabad"
        assert info.country == "India"

    def test_pune_normalization(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Pune")
        assert info.city == "Pune"
        assert info.country == "India"

    def test_mumbai_normalization(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Mumbai")
        assert info.city == "Mumbai"
        assert info.country == "India"

    def test_delhi_ncr_normalization(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Delhi NCR")
        assert info.city == "Delhi NCR"
        assert info.country == "India"

    def test_noida_normalization(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Noida")
        assert info.city == "Delhi NCR"
        assert info.country == "India"

    def test_remote_detection(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Remote")
        assert info.is_remote is True
        assert info.is_worldwide is False

    def test_worldwide_detection(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Worldwide")
        assert info.is_worldwide is True
        assert info.is_remote is False

    def test_hybrid_detection(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Hybrid")
        assert info.is_hybrid is True

    def test_remote_with_city(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Remote - India")
        assert info.is_remote is True

    def test_preserves_raw_location(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Bangalore, India (Remote)")
        assert info.raw == "Bangalore, India (Remote)"
        assert info.is_remote is True

    def test_unknown_city_passes_through(self):
        from app.discovery.location import analyze_location

        info = analyze_location("Springfield, USA")
        assert info.city is not None
        assert info.country == "United States"


# ── Enrichment Tests ────────────────────────────────────────────────────────


class TestEnrichment:
    """Test the enrichment layer."""

    def _make_normalized(
        self,
        title: str = "Software Engineer",
        company: str = "Test Co",
        description: str | None = None,
        location: str | None = None,
        opp_type: str | None = None,
        metadata: dict | None = None,
    ):
        from app.discovery.normalizer import NormalizedOpportunity

        return NormalizedOpportunity(
            source_name="test",
            external_id="1",
            canonical_source_url="https://example.com/1",
            normalized_title=title,
            normalized_company_name=company,
            description=description,
            opportunity_type=opp_type or "OTHER",
            normalized_location=location,
            deadline=None,
            salary_or_value=None,
            metadata=metadata or {},
        )

    def test_enrich_returns_enriched_opportunity(self):
        from app.discovery.enrichment import enrich

        item = self._make_normalized(title="Python Developer")
        result = enrich(item)
        assert result.normalized_title == "Python Developer"
        assert result.source_name == "test"

    def test_enrich_extracts_skills_from_title(self):
        from app.discovery.enrichment import enrich

        item = self._make_normalized(
            title="Python Developer",
            description="We use React and PostgreSQL",
        )
        result = enrich(item)
        assert "python" in result.extracted_skills
        assert "react" in result.extracted_skills
        assert "postgresql" in result.extracted_skills

    def test_enrich_location_analysis(self):
        from app.discovery.enrichment import enrich

        item = self._make_normalized(location="Remote")
        result = enrich(item)
        assert result.is_remote is True
        assert result.location_info is not None

    def test_enrich_bengaluru_location(self):
        from app.discovery.enrichment import enrich

        item = self._make_normalized(location="Bangalore, India")
        result = enrich(item)
        assert result.city == "Bengaluru"
        assert result.country == "India"

    def test_enrich_category_inference(self):
        from app.discovery.enrichment import enrich

        item = self._make_normalized(title="Machine Learning Engineer")
        result = enrich(item)
        assert result.category is not None

    def test_enrich_all_batch(self):
        from app.discovery.enrichment import enrich_all

        items = [
            self._make_normalized(title=f"Job {i}", company=f"Co {i}")
            for i in range(5)
        ]
        results = enrich_all(items)
        assert len(results) == 5


# ── Type Classification Tests ───────────────────────────────────────────────


class TestTypeClassification:
    """Test enhanced opportunity type classification."""

    def test_internship_from_title(self):
        from app.discovery.enrichment import classify_opportunity_type

        assert classify_opportunity_type(None, title="Software Intern") == "INTERNSHIP"

    def test_full_time_from_title(self):
        from app.discovery.enrichment import classify_opportunity_type

        assert classify_opportunity_type(None, title="Senior Software Engineer") == "FULL_TIME"

    def test_part_time_from_title(self):
        from app.discovery.enrichment import classify_opportunity_type

        assert classify_opportunity_type(None, title="Part-Time Data Analyst") == "PART_TIME"

    def test_contract_from_title(self):
        from app.discovery.enrichment import classify_opportunity_type

        result = classify_opportunity_type(None, title="Contract Backend Developer")
        assert result == "CONTRACT"

    def test_freelance_from_title(self):
        from app.discovery.enrichment import classify_opportunity_type

        assert classify_opportunity_type(None, title="Freelance Designer") == "FREELANCE"

    def test_research_from_title(self):
        from app.discovery.enrichment import classify_opportunity_type

        assert classify_opportunity_type(None, title="Research Assistant") == "RESEARCH"

    def test_research_scientist(self):
        from app.discovery.enrichment import classify_opportunity_type

        assert classify_opportunity_type(None, title="Research Scientist") == "RESEARCH"

    def test_hackathon_from_title(self):
        from app.discovery.enrichment import classify_opportunity_type

        assert classify_opportunity_type(None, title="Hackathon Organizer") == "HACKATHON"

    def test_known_type_passthrough(self):
        from app.discovery.enrichment import classify_opportunity_type

        assert classify_opportunity_type("INTERNSHIP") == "INTERNSHIP"
        assert classify_opportunity_type("FULL_TIME") == "FULL_TIME"
        assert classify_opportunity_type("CONTRACT") == "CONTRACT"

    def test_ambiguous_title_fallback(self):
        from app.discovery.enrichment import classify_opportunity_type

        # "manager" is a known pattern -> FULL_TIME
        result = classify_opportunity_type(None, title="General Manager")
        assert result == "FULL_TIME"

    def test_missing_type_and_title(self):
        from app.discovery.enrichment import classify_opportunity_type

        assert classify_opportunity_type(None) == "OTHER"

    def test_description_fallback(self):
        from app.discovery.enrichment import classify_opportunity_type

        result = classify_opportunity_type(
            None,
            title="Opening",
            description="We are looking for a full-time software engineer",
        )
        assert result == "FULL_TIME"


# ── Skill Extraction Tests ──────────────────────────────────────────────────


class TestSkillExtraction:
    """Test skill extraction from opportunity fields."""

    def test_extract_python(self):
        from app.discovery.enrichment import extract_opportunity_skills

        skills = extract_opportunity_skills("Python Developer", None)
        assert "python" in skills

    def test_extract_multiple_skills(self):
        from app.discovery.enrichment import extract_opportunity_skills

        skills = extract_opportunity_skills(
            None,
            "We use Python, React, and PostgreSQL",
        )
        assert "python" in skills
        assert "react" in skills
        assert "postgresql" in skills

    def test_extract_from_metadata_tags(self):
        from app.discovery.enrichment import extract_opportunity_skills

        skills = extract_opportunity_skills(
            None, None, metadata={"tags": "python, docker, kubernetes"}
        )
        assert "python" in skills
        assert "docker" in skills

    def test_extract_ml_skills(self):
        from app.discovery.enrichment import extract_opportunity_skills

        skills = extract_opportunity_skills(
            "Machine Learning Engineer",
            "Experience with TensorFlow and PyTorch",
        )
        assert "machine learning" in skills
        assert "tensorflow" in skills
        assert "pytorch" in skills

    def test_no_false_positives(self):
        from app.discovery.enrichment import extract_opportunity_skills

        skills = extract_opportunity_skills("Office Manager", None)
        # "office" should not match a tech skill
        assert "office" not in skills

    def test_empty_text(self):
        from app.discovery.enrichment import extract_opportunity_skills

        skills = extract_opportunity_skills(None, None)
        assert len(skills) == 0


# ── Category Inference Tests ────────────────────────────────────────────────


class TestCategoryInference:
    """Test category inference from opportunity fields."""

    def test_software_category(self):
        from app.discovery.enrichment import infer_category

        cat = infer_category("Software Engineer", None)
        assert cat == "Software Engineering"

    def test_ml_category(self):
        from app.discovery.enrichment import infer_category

        cat = infer_category("Machine Learning Engineer", None)
        assert cat == "Machine Learning"

    def test_data_category(self):
        from app.discovery.enrichment import infer_category

        cat = infer_category("Data Analyst", None)
        assert cat == "Data"

    def test_metadata_category_passthrough(self):
        from app.discovery.enrichment import infer_category

        cat = infer_category(None, None, metadata={"category": "Blockchain"})
        assert cat == "Blockchain"

    def test_no_match(self):
        from app.discovery.enrichment import infer_category

        cat = infer_category("Manager", None)
        assert cat is None


# ── Registry Tests ──────────────────────────────────────────────────────────


class TestEnhancedRegistry:
    """Test enhanced registry with auth-required tracking."""

    def test_list_source_names_includes_stubs(self):
        from app.discovery.registry import list_source_names

        names = list_source_names()
        assert "remotive" in names
        assert "linkedin" in names
        assert "handshake" in names
        assert "jobstep" in names

    def test_list_active_source_names(self):
        from app.discovery.registry import list_active_source_names

        active = list_active_source_names()
        assert "remotive" in active
        assert "arbeitnow" in active
        assert "himalayas" in active
        assert "linkedin" not in active
        assert "handshake" not in active

    def test_is_auth_required(self):
        from app.discovery.registry import is_auth_required

        assert is_auth_required("linkedin") is True
        assert is_auth_required("handshake") is True
        assert is_auth_required("jobstep") is True
        assert is_auth_required("remotive") is False
        assert is_auth_required("arbeitnow") is False

    def test_create_stub_adapter(self):
        from app.discovery.registry import create_adapter

        adapter = create_adapter("linkedin")
        assert adapter.source_name == "linkedin"

    def test_stub_adapter_raises_on_discover(self):
        from app.discovery.registry import create_adapter

        adapter = create_adapter("linkedin")
        with pytest.raises(NotImplementedError):
            adapter.discover()


# ── Auth-required handling in run_source ────────────────────────────────────


class TestRunSourceAuthHandling:
    """Test that run_source handles auth-required sources gracefully."""

    def test_run_source_linkedin_returns_error(self, db):
        from app.services.discovery import run_source

        result = run_source(db, "linkedin")
        assert result.ingested == 0
        assert len(result.errors) > 0
        assert "authorized" in result.errors[0].lower() or "requires" in result.errors[0].lower()

    def test_run_source_handshake_returns_error(self, db):
        from app.services.discovery import run_source

        result = run_source(db, "handshake")
        assert result.ingested == 0
        assert len(result.errors) > 0


# ── Enriched Discovery (preview) Tests ──────────────────────────────────────


class TestEnrichedDiscovery:
    """Test enriched discovery (preview) endpoint."""

    def test_preview_linkedin_returns_error(self):
        from app.services.discovery import discover_enriched

        result = discover_enriched("linkedin")
        assert result.enriched_count == 0
        assert len(result.errors) > 0

    def test_preview_unknown_source(self):
        from app.services.discovery import discover_enriched

        result = discover_enriched("nonexistent")
        assert result.enriched_count == 0
        assert len(result.errors) > 0


# ── API Endpoint Tests ──────────────────────────────────────────────────────


class TestDiscoveryAPI:
    """Test enhanced discovery API endpoints."""

    def test_list_sources_metadata(self, client):
        response = client.get("/discovery/sources/metadata")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert data["total_count"] >= 6
        assert data["active_count"] >= 3
        assert data["auth_required_count"] >= 3

    def test_get_source_metadata(self, client):
        response = client.get("/discovery/sources/remotive/metadata")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "remotive"
        assert data["requires_auth"] is False

    def test_get_unknown_source_metadata(self, client):
        response = client.get("/discovery/sources/nonexistent/metadata")
        assert response.status_code == 404

    def test_discovery_health(self, client):
        response = client.get("/discovery/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded", "unavailable")
        assert "active_sources" in data
        assert "auth_required_sources" in data

    def test_original_sources_endpoint_still_works(self, client):
        response = client.get("/discovery/sources")
        assert response.status_code == 200
        data = response.json()
        assert "remotive" in data["sources"]

    def test_preview_linkedin(self, client):
        response = client.get("/discovery/sources/linkedin/preview")
        assert response.status_code == 200
        data = response.json()
        assert data["source_name"] == "linkedin"
        assert data["enriched_count"] == 0
        assert len(data["errors"]) > 0

    def test_run_source_still_works(self, client, db):
        """Backward compatibility — POST /discovery/run/{source} still works."""
        from unittest.mock import MagicMock, patch

        job = {
            "id": 500,
            "title": "Test Intelligence Job",
            "company_name": "Intelligence Co",
            "job_type": "full_time",
            "candidate_required_location": "Remote",
        }
        response_data = {"jobs": [job]}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data
        mock_response.raise_for_status.return_value = None

        with patch("httpx.get", return_value=mock_response):
            response = client.post("/discovery/run/remotive")

        assert response.status_code == 200
        data = response.json()
        assert data["source_name"] == "remotive"
        assert data["ingested"] >= 1

    def test_raw_ingestion_still_works(self, client, db):
        """Backward compatibility — POST /discovery/run (raw) still works."""
        raw_item = {
            "source_name": "manual",
            "title": "Manual Entry Intelligence",
            "company_name": "Manual Co",
        }
        response = client.post("/discovery/run", json=[raw_item])
        assert response.status_code == 200
        data = response.json()
        assert data["ingested"] == 1


# ── Existing API Regression Tests ───────────────────────────────────────────


class TestExistingAPIRegression:
    """Ensure existing APIs are not broken."""

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_opportunity_crud(self, client, db):
        company_resp = client.post("/companies", json={"name": "Regression Co"})
        company_id = company_resp.json()["id"]

        opp_resp = client.post("/opportunities", json={
            "company_id": company_id,
            "type": "FULL_TIME",
            "title": "Regression Test",
        })
        assert opp_resp.status_code == 201
        opp_id = opp_resp.json()["id"]

        get_resp = client.get(f"/opportunities/{opp_id}")
        assert get_resp.status_code == 200

        del_resp = client.delete(f"/opportunities/{opp_id}")
        assert del_resp.status_code == 204

    def test_company_crud(self, client, db):
        resp = client.post("/companies", json={"name": "Test Company Intel"})
        assert resp.status_code == 201
        company_id = resp.json()["id"]

        get_resp = client.get(f"/companies/{company_id}")
        assert get_resp.status_code == 200

        del_resp = client.delete(f"/companies/{company_id}")
        assert del_resp.status_code == 204

    def test_planning_endpoint(self, client, db):
        response = client.get("/opportunities/planning")
        assert response.status_code == 200


# ── End-to-end enrichment + ingestion test ──────────────────────────────────


class TestEnrichedIngestionPipeline:
    """Test the full pipeline: adapter → normalize → enrich → ingest."""

    def test_remotive_enriched_pipeline(self, db):
        from app.discovery.adapters.remotive import RemotiveAdapter
        from app.discovery.deduplicator import deduplicate
        from app.discovery.enrichment import enrich_all
        from app.discovery.normalizer import normalize_all
        from app.services.discovery import ingest
        from app.models.opportunity import Opportunity

        job = {
            "id": 600,
            "title": "Python Developer Intern",
            "company_name": "Enrichment Test Co",
            "job_type": "internship",
            "candidate_required_location": "Remote",
            "description": "We use Python, Django, PostgreSQL, and AWS.",
        }

        adapter = RemotiveAdapter()
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"jobs": [job]}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            raw_items = adapter.discover()

        # Normalize
        normalized = normalize_all(raw_items)
        assert len(normalized) == 1
        assert normalized[0].opportunity_type == "INTERNSHIP"

        # Enrich
        enriched = enrich_all(normalized)
        assert len(enriched) == 1
        e = enriched[0]
        assert e.is_remote is True
        assert "python" in e.extracted_skills
        assert e.opportunity_type == "INTERNSHIP"

        # Ingest
        result = ingest(db, normalized)
        assert result.ingested == 1

        # Verify in DB
        opp = db.query(Opportunity).filter(
            Opportunity.title == "Python Developer Intern"
        ).first()
        assert opp is not None
        assert opp.type == "INTERNSHIP"


# ── Idempotency test ───────────────────────────────────────────────────────


class TestDiscoveryIdempotency:
    """Ensure repeated runs don't create duplicates."""

    def test_same_source_twice_no_duplicates(self, db):
        from app.services.discovery import ingest
        from app.discovery.normalizer import normalize_all
        from app.discovery.models import RawOpportunity
        from app.models.opportunity import Opportunity

        raw = [
            RawOpportunity(
                source_name="test",
                external_id="idem-1",
                title="Idempotent Job",
                company_name="Idempotent Co",
            )
        ]
        normalized = normalize_all(raw)

        result1 = ingest(db, normalized)
        assert result1.ingested == 1

        result2 = ingest(db, normalized)
        assert result2.duplicates_skipped == 1
        assert result2.ingested == 0

        opps = db.query(Opportunity).filter(
            Opportunity.title == "Idempotent Job"
        ).all()
        assert len(opps) == 1
