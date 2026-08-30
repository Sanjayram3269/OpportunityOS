"""Tests for the Discovery Engine foundation."""

from datetime import datetime, timezone

from app.discovery.adapters.base import SourceAdapter
from app.discovery.deduplicator import deduplicate
from app.discovery.models import RawOpportunity
from app.discovery.normalizer import NormalizedOpportunity, normalize, normalize_all, normalize_type
from app.models.company import Company
from app.models.opportunity import Opportunity
from app.models.opportunity_evidence import OpportunityEvidence
from sqlalchemy import select


# ═══════════════════════════════════════════════════════════════════════════
# 1. Adapter contract
# ═══════════════════════════════════════════════════════════════════════════


class TestAdapterContract:
    def test_cannot_instantiate_base(self):
        """SourceAdapter is abstract — direct instantiation must fail."""
        try:
            SourceAdapter()  # type: ignore[abstract]
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_concrete_adapter_implements_interface(self):
        """A minimal concrete adapter satisfies the interface."""

        class StubAdapter(SourceAdapter):
            @property
            def source_name(self) -> str:
                return "stub"

            def discover(self) -> list[RawOpportunity]:
                return []

        adapter = StubAdapter()
        assert adapter.source_name == "stub"
        assert adapter.discover() == []

    def test_concrete_adapter_returns_raw_opportunities(self):
        """Adapter can return populated RawOpportunity records."""

        class FakeAdapter(SourceAdapter):
            @property
            def source_name(self) -> str:
                return "fake"

            def discover(self) -> list[RawOpportunity]:
                return [
                    RawOpportunity(
                        source_name="fake",
                        title="SWE Intern",
                        company_name="Acme Corp",
                        opportunity_type="internship",
                    )
                ]

        items = FakeAdapter().discover()
        assert len(items) == 1
        assert items[0].title == "SWE Intern"
        assert items[0].company_name == "Acme Corp"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Normalization
# ═══════════════════════════════════════════════════════════════════════════


class TestNormalizeType:
    def test_known_type_passes_through(self):
        assert normalize_type("INTERNSHIP") == "INTERNSHIP"
        assert normalize_type("FULL_TIME") == "FULL_TIME"

    def test_aliases(self):
        assert normalize_type("intern") == "INTERNSHIP"
        assert normalize_type("full time") == "FULL_TIME"
        assert normalize_type("Freelance") == "FREELANCE"
        assert normalize_type("hackathons") == "HACKATHON"

    def test_unknown_defaults_to_other(self):
        assert normalize_type("something_random") == "OTHER"

    def test_none_defaults_to_other(self):
        assert normalize_type(None) == "OTHER"


class TestNormalize:
    def test_whitespace_collapsed(self):
        raw = RawOpportunity(
            source_name="test",
            title="  Hello   World  ",
            company_name="  Acme  Corp  ",
        )
        norm = normalize(raw)
        assert norm.normalized_title == "Hello World"
        assert norm.normalized_company_name == "Acme Corp"

    def test_unicode_normalized(self):
        raw = RawOpportunity(
            source_name="test",
            title="Caf\u00e9 Corp\u00ae",
            company_name="Caf\u00e9 Corp\u00ae",
        )
        norm = normalize(raw)
        # NFKC normalization
        assert "\u00e9" in norm.normalized_title or "e" in norm.normalized_title

    def test_url_normalized(self):
        raw = RawOpportunity(
            source_name="test",
            title="Job",
            company_name="Co",
            source_url="  https://Example.COM/job/123/  ",
        )
        norm = normalize(raw)
        assert norm.canonical_source_url == "https://example.com/job/123"

    def test_url_fragment_stripped(self):
        raw = RawOpportunity(
            source_name="test",
            title="Job",
            company_name="Co",
            source_url="https://example.com/job/123#section",
        )
        norm = normalize(raw)
        assert norm.canonical_source_url == "https://example.com/job/123"

    def test_url_trailing_slash_stripped(self):
        raw = RawOpportunity(
            source_name="test",
            title="Job",
            company_name="Co",
            source_url="https://example.com/job/123/",
        )
        norm = normalize(raw)
        assert norm.canonical_source_url == "https://example.com/job/123"

    def test_none_url_stays_none(self):
        raw = RawOpportunity(
            source_name="test",
            title="Job",
            company_name="Co",
            source_url=None,
        )
        norm = normalize(raw)
        assert norm.canonical_source_url is None

    def test_location_normalized(self):
        raw = RawOpportunity(
            source_name="test",
            title="Job",
            company_name="Co",
            location="  San   Francisco,  CA  ",
        )
        norm = normalize(raw)
        assert norm.normalized_location == "San Francisco, CA"

    def test_none_location_stays_none(self):
        raw = RawOpportunity(
            source_name="test",
            title="Job",
            company_name="Co",
            location=None,
        )
        norm = normalize(raw)
        assert norm.normalized_location is None

    def test_source_name_lowercased(self):
        raw = RawOpportunity(
            source_name="LinkedIn",
            title="Job",
            company_name="Co",
        )
        norm = normalize(raw)
        assert norm.source_name == "linkedin"

    def test_external_id_stripped(self):
        raw = RawOpportunity(
            source_name="test",
            title="Job",
            company_name="Co",
            external_id="  abc123  ",
        )
        norm = normalize(raw)
        assert norm.external_id == "abc123"

    def test_description_preserved(self):
        raw = RawOpportunity(
            source_name="test",
            title="Job",
            company_name="Co",
            description="  A great  opportunity  ",
        )
        norm = normalize(raw)
        assert norm.description == "A great  opportunity"

    def test_normalize_all_batch(self):
        items = [
            RawOpportunity(source_name="s", title=f"Job {i}", company_name="Co")
            for i in range(5)
        ]
        result = normalize_all(items)
        assert len(result) == 5


# ═══════════════════════════════════════════════════════════════════════════
# 3. Deduplication
# ═══════════════════════════════════════════════════════════════════════════


def _make_norm(
    source_name: str = "test",
    external_id: str | None = None,
    source_url: str | None = None,
    title: str = "SWE Intern",
    company_name: str = "Acme Corp",
    description: str | None = None,
) -> NormalizedOpportunity:
    return NormalizedOpportunity(
        source_name=source_name,
        external_id=external_id,
        canonical_source_url=source_url,
        normalized_title=title,
        normalized_company_name=company_name,
        description=description,
        opportunity_type="OTHER",
        normalized_location=None,
        deadline=None,
        salary_or_value=None,
        metadata={},
    )


class TestDeduplication:
    def test_no_duplicates(self):
        items = [
            _make_norm(title="Job A", company_name="Co1"),
            _make_norm(title="Job B", company_name="Co2"),
        ]
        result = deduplicate(items)
        assert len(result) == 2

    def test_same_external_id_deduped(self):
        items = [
            _make_norm(external_id="ext-1", title="Job A"),
            _make_norm(external_id="ext-1", title="Job A copy"),
        ]
        result = deduplicate(items)
        assert len(result) == 1

    def test_different_source_same_external_id_not_deduped(self):
        items = [
            _make_norm(source_name="src1", external_id="ext-1"),
            _make_norm(source_name="src2", external_id="ext-1"),
        ]
        result = deduplicate(items)
        assert len(result) == 2

    def test_same_url_deduped(self):
        items = [
            _make_norm(source_url="https://example.com/job/1"),
            _make_norm(source_url="https://example.com/job/1"),
        ]
        result = deduplicate(items)
        assert len(result) == 1

    def test_different_company_same_title_not_deduped(self):
        items = [
            _make_norm(title="SWE Intern", company_name="Co1"),
            _make_norm(title="SWE Intern", company_name="Co2"),
        ]
        result = deduplicate(items)
        assert len(result) == 2

    def test_same_company_same_title_deduped(self):
        items = [
            _make_norm(title="SWE Intern", company_name="Acme"),
            _make_norm(title="SWE Intern", company_name="Acme"),
        ]
        result = deduplicate(items)
        assert len(result) == 1

    def test_empty_input(self):
        result = deduplicate([])
        assert result == []

    def test_first_occurrence_kept(self):
        items = [
            _make_norm(title="Job A", company_name="Co"),
            _make_norm(title="Job A", company_name="Co", description="second"),
        ]
        result = deduplicate(items)
        assert len(result) == 1
        assert result[0].description is None  # first occurrence kept

    def test_normalized_company_title_dedup(self):
        """Identical normalized company+title from the same source are deduped."""
        items = [
            _make_norm(title="SWE Intern", company_name="Acme"),
            _make_norm(title="SWE Intern", company_name="Acme"),
        ]
        result = deduplicate(items)
        assert len(result) == 1

    def test_url_takes_priority_over_title(self):
        """If two items share a URL, only the URL dedup fires; title is secondary."""
        items = [
            _make_norm(source_url="https://x.com/1", title="Job A"),
            _make_norm(source_url="https://x.com/1", title="Job B"),
        ]
        result = deduplicate(items)
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 4. Ingestion (database)
# ═══════════════════════════════════════════════════════════════════════════


class TestCompanyResolution:
    def test_creates_new_company(self, db):
        from app.services.discovery import resolve_company

        company = resolve_company(db, "New Startup Inc")
        assert company.id is not None
        assert company.name == "New Startup Inc"

    def test_reuses_existing_company(self, db):
        from app.services.discovery import resolve_company

        c1 = resolve_company(db, "Reuse Me")
        c2 = resolve_company(db, "Reuse Me")
        assert c1.id == c2.id

    def test_different_names_create_different_companies(self, db):
        from app.services.discovery import resolve_company

        c1 = resolve_company(db, "Company A")
        c2 = resolve_company(db, "Company B")
        assert c1.id != c2.id


class TestIngestion:
    def _raw(self, **overrides) -> RawOpportunity:
        defaults = {
            "source_name": "test_source",
            "title": "Test Opportunity",
            "company_name": "Test Co",
        }
        defaults.update(overrides)
        return RawOpportunity(**defaults)

    def test_basic_ingestion(self, db):
        from app.services.discovery import ingest

        raw = self._raw()
        normalized = normalize_all([raw])
        result = ingest(db, normalized)

        assert result.ingested == 1
        assert result.duplicates_skipped == 0
        assert result.companies_created == 1
        assert result.errors == []

        # Verify DB state
        opp = db.scalar(select(Opportunity).limit(1))
        assert opp is not None
        assert opp.title == "Test Opportunity"
        assert opp.type == "OTHER"

    def test_company_created_and_reused(self, db):
        from app.services.discovery import ingest

        raw1 = self._raw(title="Job 1", company_name="Shared Co")
        raw2 = self._raw(title="Job 2", company_name="Shared Co")
        result = ingest(db, normalize_all([raw1, raw2]))

        assert result.ingested == 2
        assert result.companies_created == 1

        company = db.scalar(select(Company).where(Company.name == "Shared Co"))
        assert company is not None
        assert len(list(company.id for _ in range(1))) == 1

    def test_duplicate_external_id_skipped(self, db):
        from app.services.discovery import ingest

        raw1 = self._raw(external_id="ext-1")
        raw2 = self._raw(external_id="ext-1", title="Same Ext ID")

        ingest(db, normalize_all([raw1]))
        result2 = ingest(db, normalize_all([raw2]))

        assert result2.duplicates_skipped == 1

    def test_duplicate_url_skipped(self, db):
        from app.services.discovery import ingest

        raw1 = self._raw(source_url="https://example.com/job/1")
        raw2 = self._raw(source_url="https://example.com/job/1", title="Same URL")

        ingest(db, normalize_all([raw1]))
        result2 = ingest(db, normalize_all([raw2]))

        assert result2.duplicates_skipped == 1

    def test_batch_dedup_before_db(self, db):
        """Duplicates within a single batch are removed before DB checks."""
        from app.services.discovery import ingest

        raw1 = self._raw(title="Job A")
        raw2 = self._raw(title="Job A")  # same company + title

        result = ingest(db, normalize_all([raw1, raw2]))
        assert result.raw_count == 2
        assert result.ingested == 1
        assert result.duplicates_skipped == 0  # removed by batch dedup, not DB

    def test_evidence_recorded(self, db):
        from app.services.discovery import ingest

        raw = self._raw(external_id="ext-42", source_url="https://example.com/job/42")
        ingest(db, normalize_all([raw]))

        evidences = list(
            db.scalars(
                select(OpportunityEvidence).where(
                    OpportunityEvidence.source == "test_source"
                )
            )
        )
        types = {e.evidence_type for e in evidences}
        assert "external_id" in types
        assert "source_url" in types

    def test_ingestion_result_summary(self, db):
        from app.services.discovery import ingest

        items = [
            self._raw(title="Job 1", external_id="e1"),
            self._raw(title="Job 2", external_id="e2"),
            self._raw(title="Job 3", company_name="Other Co"),
        ]
        result = ingest(db, normalize_all(items))
        assert result.source_name == "test_source"
        assert result.raw_count == 3
        assert result.ingested == 3
        assert result.companies_created == 2  # Test Co + Other Co


# ═══════════════════════════════════════════════════════════════════════════
# 5. API endpoint
# ═══════════════════════════════════════════════════════════════════════════


class TestDiscoveryEndpoint:
    def test_run_discovery_basic(self, client):
        payload = [
            {
                "source_name": "manual",
                "title": "Python Developer",
                "company_name": "DevCorp",
                "opportunity_type": "FULL_TIME",
                "location": "Remote",
            }
        ]
        resp = client.post("/discovery/run", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_name"] == "manual"
        assert data["ingested"] == 1
        assert data["duplicates_skipped"] == 0
        assert data["companies_created"] == 1

    def test_run_discovery_batch(self, client):
        payload = [
            {
                "source_name": "manual",
                "title": "Job A",
                "company_name": "Co1",
            },
            {
                "source_name": "manual",
                "title": "Job B",
                "company_name": "Co2",
            },
        ]
        resp = client.post("/discovery/run", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ingested"] == 2

    def test_run_discovery_empty_batch(self, client):
        resp = client.post("/discovery/run", json=[])
        assert resp.status_code == 200
        data = resp.json()
        assert data["ingested"] == 0

    def test_run_discovery_deduplicates_batch(self, client):
        payload = [
            {
                "source_name": "manual",
                "title": "Same Job",
                "company_name": "Same Co",
            },
            {
                "source_name": "manual",
                "title": "Same Job",
                "company_name": "Same Co",
            },
        ]
        resp = client.post("/discovery/run", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_count"] == 2
        assert data["ingested"] == 1

    def test_run_discovery_skips_db_duplicates(self, client):
        payload = [
            {
                "source_name": "manual",
                "title": "Job",
                "company_name": "Co",
                "external_id": "ext-1",
            }
        ]
        # First run
        resp1 = client.post("/discovery/run", json=payload)
        assert resp1.json()["ingested"] == 1

        # Second run — same external_id, should be skipped
        resp2 = client.post("/discovery/run", json=payload)
        assert resp2.json()["duplicates_skipped"] == 1

    def test_run_discovery_missing_required_fields_fails(self, client):
        resp = client.post("/discovery/run", json=[{"source_name": "x"}])
        assert resp.status_code == 422

    def test_opportunities_visible_after_ingestion(self, client):
        payload = [
            {
                "source_name": "manual",
                "title": "Visible Job",
                "company_name": "VisibleCo",
            }
        ]
        client.post("/discovery/run", json=payload)
        resp = client.get("/opportunities")
        assert resp.status_code == 200
        titles = [o["title"] for o in resp.json()]
        assert "Visible Job" in titles


# ═══════════════════════════════════════════════════════════════════════════
# 6. Existing API preservation
# ═══════════════════════════════════════════════════════════════════════════


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
        resp = client.post(
            "/leads",
            json={"name": "Preserved Lead"},
        )
        assert resp.status_code == 201

    def test_opportunities_still_work(self, client):
        company_resp = client.post("/companies", json={"name": "Opp Co"})
        company_id = company_resp.json()["id"]
        resp = client.post(
            "/opportunities",
            json={"company_id": company_id, "type": "INTERNSHIP", "title": "Intern"},
        )
        assert resp.status_code == 201

    def test_health_still_works(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
