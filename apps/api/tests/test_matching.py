"""Comprehensive tests for the Opportunity ↔ Profile matching engine.

Tests cover:
  1. Skill normalization (case, synonyms, separators)
  2. Feature extraction (profile + opportunity)
  3. Deterministic scoring (all components)
  4. Score bounds and determinism
  5. Explanation generation
  6. Location compatibility
  7. Opportunity type matching
  8. Ranking order
  9. API endpoints
  10. Existing API preservation
"""

from __future__ import annotations

import pytest

from app.matching.extractor import (
    OpportunityFeatures,
    ProfileFeatures,
    extract_opportunity_features,
    extract_profile_features,
)
from app.matching.normalizer import normalize_skill, normalize_skills
from app.matching.scorer import MatchResult, _location_compatible, score_match
from app.models.company import Company
from app.models.opportunity import Opportunity
from app.models.profile import Profile
from app.models.project import Project
from app.models.skill import Skill


# ══════════════════════════════════════════════════════════════════════════
# 1. SKILL NORMALIZATION
# ══════════════════════════════════════════════════════════════════════════


class TestSkillNormalization:
    def test_case_normalization(self):
        assert normalize_skill("Python") == "python"
        assert normalize_skill("PYTHON") == "python"
        assert normalize_skill("pYtHoN") == "python"

    def test_whitespace_handling(self):
        assert normalize_skill("  Python  ") == "python"
        assert normalize_skill("Fast  API") == "fastapi"

    def test_common_abbreviations(self):
        assert normalize_skill("JS") == "javascript"
        assert normalize_skill("TS") == "typescript"
        assert normalize_skill("Py") == "python"
        assert normalize_skill("K8s") == "kubernetes"
        assert normalize_skill("ML") == "machine learning"
        assert normalize_skill("AI") == "artificial intelligence"
        assert normalize_skill("DL") == "deep learning"
        assert normalize_skill("NLP") == "natural language processing"
        assert normalize_skill("CV") == "computer vision"
        assert normalize_skill("LLM") == "large language model"

    def test_cloud_aliases(self):
        assert normalize_skill("AWS") == "amazon web services"
        assert normalize_skill("GCP") == "google cloud platform"
        assert normalize_skill("Azure") == "microsoft azure"

    def test_database_aliases(self):
        assert normalize_skill("Postgres") == "postgresql"
        assert normalize_skill("PostgreSQL") == "postgresql"
        assert normalize_skill("PSQL") == "postgresql"
        assert normalize_skill("Mongo") == "mongodb"
        assert normalize_skill("MongoDB") == "mongodb"

    def test_framework_aliases(self):
        assert normalize_skill("FastAPI") == "fastapi"
        assert normalize_skill("Fast API") == "fastapi"
        assert normalize_skill("Node.js") == "nodejs"
        assert normalize_skill("Node JS") == "nodejs"
        assert normalize_skill("Vue.js") == "vuejs"
        assert normalize_skill("Next.js") == "nextjs"
        assert normalize_skill("React.js") == "reactjs"

    def test_separator_normalization(self):
        assert normalize_skill("CI/CD") == "ci cd"
        assert normalize_skill("C++") == "c++"  # preserved via alias
        assert normalize_skill("C#") == "c#"

    def test_unknown_skill_passes_through(self):
        assert normalize_skill("MyCustomTool") == "mycustomtool"
        assert normalize_skill("React Native") == "react native"

    def test_empty_string(self):
        assert normalize_skill("") == ""
        assert normalize_skill("   ") == ""

    def test_normalize_skills_batch(self):
        result = normalize_skills(["Python", "JS", "React", "PostgreSQL"])
        assert result == {"python", "javascript", "react", "postgresql"}


# ══════════════════════════════════════════════════════════════════════════
# 2. FEATURE EXTRACTION
# ══════════════════════════════════════════════════════════════════════════


class TestFeatureExtraction:
    def test_profile_features_with_skills(self, db):
        """Profile with skills extracts normalized skill set."""
        profile = Profile(name="Test", email="test@example.com")
        db.add(profile)
        db.flush()

        skill1 = Skill(profile_id=profile.id, name="Python")
        skill2 = Skill(profile_id=profile.id, name="JavaScript")
        skill3 = Skill(profile_id=profile.id, name="React")
        db.add_all([skill1, skill2, skill3])
        db.flush()

        features = extract_profile_features(profile, skills=[skill1, skill2, skill3])
        assert features.skills == {"python", "javascript", "react"}

    def test_profile_features_with_projects(self, db):
        """Profile with projects extracts technologies and description skills."""
        profile = Profile(name="Test", email="test2@example.com")
        db.add(profile)
        db.flush()

        project = Project(
            profile_id=profile.id,
            name="Test Project",
            description="A web app built with React and Node.js",
            technologies="React, Node.js, PostgreSQL",
        )
        db.add(project)
        db.flush()

        features = extract_profile_features(profile, projects=[project])
        assert "react" in features.project_technologies
        assert "nodejs" in features.project_technologies
        assert "postgresql" in features.project_technologies

    def test_profile_features_with_headline(self, db):
        """Profile headline extracts skill signals."""
        profile = Profile(
            name="Test",
            email="test3@example.com",
            headline="Software Engineer | Python | Machine Learning",
        )
        db.add(profile)
        db.flush()

        features = extract_profile_features(profile)
        assert "python" in features.headline_skills
        assert "machine learning" in features.headline_skills

    def test_profile_features_with_bio(self, db):
        """Profile bio extracts skill signals."""
        profile = Profile(
            name="Test",
            email="test4@example.com",
            bio="I love building things with TypeScript and AWS.",
        )
        db.add(profile)
        db.flush()

        features = extract_profile_features(profile)
        assert "typescript" in features.bio_skills
        assert "amazon web services" in features.bio_skills

    def test_opportunity_features_from_description(self, db):
        """Opportunity description extracts skills."""
        company = Company(name="TestCo")
        db.add(company)
        db.flush()

        opp = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Python Developer",
            description="We need someone with Python, Django, and PostgreSQL experience.",
        )
        db.add(opp)
        db.flush()

        features = extract_opportunity_features(opp, company_name="TestCo")
        assert "python" in features.description_skills
        assert "django" in features.description_skills
        assert "postgresql" in features.description_skills
        assert features.company_name == "TestCo"

    def test_opportunity_features_from_title(self, db):
        """Opportunity title extracts skills."""
        company = Company(name="TestCo2")
        db.add(company)
        db.flush()

        opp = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Machine Learning Engineer",
        )
        db.add(opp)
        db.flush()

        features = extract_opportunity_features(opp)
        assert "machine learning" in features.title_skills

    def test_empty_profile_features(self, db):
        """Empty profile produces no skills."""
        profile = Profile(name="Empty", email="empty@example.com")
        db.add(profile)
        db.flush()

        features = extract_profile_features(profile)
        assert not features.all_skills
        assert not features.has_any_data

    def test_sparse_opportunity_features(self, db):
        """Opportunity with no description still works."""
        company = Company(name="SparseCo")
        db.add(company)
        db.flush()

        opp = Opportunity(
            company_id=company.id,
            type="OTHER",
            title="Some Role",
        )
        db.add(opp)
        db.flush()

        features = extract_opportunity_features(opp)
        assert features.title_skills == set()
        assert features.description_skills == set()


# ══════════════════════════════════════════════════════════════════════════
# 3. SCORING ENGINE
# ══════════════════════════════════════════════════════════════════════════


def _make_profile_features(skills=None, headline=None, bio=None, **kwargs):
    """Helper to create ProfileFeatures for testing."""
    return ProfileFeatures(
        skills=skills or set(),
        headline=headline,
        bio=bio,
        **kwargs,
    )


def _make_opp_features(title="Test Role", opp_type="FULL_TIME", location=None, description=None, skills=None):
    """Helper to create OpportunityFeatures for testing."""
    return OpportunityFeatures(
        title=title,
        type=opp_type,
        location=location,
        description=description,
        description_skills=skills or set(),
    )


class TestScoring:
    def test_score_bounds(self):
        """Score must always be 0–100."""
        pf = _make_profile_features()
        of = _make_opp_features()
        result = score_match(pf, of)
        assert 0 <= result.score <= 100

    def test_exact_skill_match_high_score(self):
        """Many shared skills → high score."""
        pf = _make_profile_features(
            skills={"python", "django", "postgresql", "react", "javascript", "docker", "aws", "git"},
        )
        of = _make_opp_features(
            skills={"python", "django", "postgresql", "react", "javascript", "docker", "aws"},
        )
        result = score_match(pf, of)
        assert result.score >= 35
        assert len(result.matched_skills) >= 5

    def test_no_matching_skills_low_score(self):
        """No shared skills → lower score."""
        pf = _make_profile_features(skills={"cooking", "painting"})
        of = _make_opp_features(skills={"python", "react"})
        result = score_match(pf, of)
        assert result.score < 30
        assert len(result.matched_skills) == 0

    def test_partial_skill_overlap(self):
        """Some shared skills → moderate score."""
        pf = _make_profile_features(skills={"python", "react"})
        of = _make_opp_features(skills={"python", "react", "aws", "docker"})
        result = score_match(pf, of)
        assert 10 <= result.score <= 50
        assert "python" in result.matched_skills
        assert "react" in result.matched_skills

    def test_determinism(self):
        """Same inputs always produce the same score."""
        pf = _make_profile_features(skills={"python", "django"})
        of = _make_opp_features(skills={"python", "django", "postgresql"})
        r1 = score_match(pf, of)
        r2 = score_match(pf, of)
        assert r1.score == r2.score
        assert r1.matched_skills == r2.matched_skills
        assert r1.explanation == r2.explanation

    def test_missing_skills_listed(self):
        """Skills in opportunity but not in profile appear in missing_skills."""
        pf = _make_profile_features(skills={"python"})
        of = _make_opp_features(skills={"python", "react", "aws"})
        result = score_match(pf, of)
        assert "react" in result.missing_skills
        assert "aws" in result.missing_skills
        assert "python" not in result.missing_skills

    def test_matched_signals_populated(self):
        """Matched signals are generated for good matches."""
        pf = _make_profile_features(
            skills={"python", "django", "postgresql"},
            headline="Python Developer",
        )
        of = _make_opp_features(
            title="Python Developer",
            skills={"python", "django", "postgresql"},
        )
        result = score_match(pf, of)
        assert len(result.matched_signals) > 0

    def test_concerns_for_missing_skills(self):
        """Concerns are generated when important skills are missing."""
        pf = _make_profile_features(skills={"python"})
        of = _make_opp_features(skills={"python", "react", "aws", "docker", "kubernetes"})
        result = score_match(pf, of)
        assert len(result.concerns) > 0

    def test_explanation_generated(self):
        """Explanation is always a non-empty string."""
        pf = _make_profile_features(skills={"python"})
        of = _make_opp_features(skills={"python"})
        result = score_match(pf, of)
        assert isinstance(result.explanation, str)
        assert len(result.explanation) > 0


# ══════════════════════════════════════════════════════════════════════════
# 4. TITLE RELEVANCE
# ══════════════════════════════════════════════════════════════════════════


class TestTitleRelevance:
    def test_matching_headline_and_title(self):
        """Headline matching opportunity title boosts score."""
        pf = _make_profile_features(headline="Software Engineer")
        of = _make_opp_features(title="Software Engineer")
        result = score_match(pf, of)
        assert result.title_relevance_score > 0

    def test_unrelated_title(self):
        """Unrelated title gives low title score."""
        pf = _make_profile_features(headline="Marketing Manager")
        of = _make_opp_features(title="Python Backend Developer")
        result = score_match(pf, of)
        assert result.title_relevance_score < 10

    def test_experience_title_alignment(self):
        """Experience titles matching opportunity title boosts score."""
        pf = ProfileFeatures(
            experience_titles={"software engineer", "backend developer"},
        )
        of = _make_opp_features(title="Software Engineer")
        result = score_match(pf, of)
        assert result.title_relevance_score > 0


# ══════════════════════════════════════════════════════════════════════════
# 5. LOCATION COMPATIBILITY
# ══════════════════════════════════════════════════════════════════════════


class TestLocationCompatibility:
    def test_remote_opportunity(self):
        """Remote opportunities are always compatible."""
        assert _location_compatible(None, "Remote") == 10
        assert _location_compatible("Chennai", "Remote") == 10

    def test_worldwide_opportunity(self):
        """Worldwide opportunities are always compatible."""
        assert _location_compatible(None, "Worldwide") == 10
        assert _location_compatible("Bengaluru", "Worldwide") == 10

    def test_no_opportunity_location(self):
        """No opportunity location → assume flexible."""
        assert _location_compatible("Chennai", None) == 8

    def test_no_profile_location(self):
        """No profile location → don't penalize."""
        assert _location_compatible(None, "Bengaluru") == 5

    def test_exact_match(self):
        """Exact city match → full score."""
        assert _location_compatible("Bengaluru", "Bengaluru") == 10

    def test_containment_match(self):
        """"Bengaluru, India" contains "India" → high score."""
        assert _location_compatible("Bengaluru, India", "India") == 9
        assert _location_compatible("India", "Bengaluru, India") == 9

    def test_country_level_match(self):
        """Both mention same country → moderate score."""
        assert _location_compatible("Mumbai, India", "Delhi, India") == 7

    def test_mismatch(self):
        """Different locations → low but non-zero score."""
        assert _location_compatible("Chennai", "Berlin") == 2

    def test_empty_strings(self):
        """Empty strings handled gracefully."""
        assert _location_compatible("", "") == 8
        assert _location_compatible("", "Remote") == 10


# ══════════════════════════════════════════════════════════════════════════
# 6. OPPORTUNITY TYPE MATCHING
# ══════════════════════════════════════════════════════════════════════════


class TestTypeMatching:
    def test_no_preference_gives_moderate_score(self):
        """Without explicit preference, common types get decent score."""
        from app.matching.scorer import _type_fit_score
        assert _type_fit_score(None, "FULL_TIME") >= 3
        assert _type_fit_score(None, "INTERNSHIP") >= 3
        assert _type_fit_score(None, "RESEARCH") >= 3

    def test_matching_type(self):
        """Matching type preference → full score."""
        from app.matching.scorer import _type_fit_score
        assert _type_fit_score("FULL_TIME", "FULL_TIME") == 5
        assert _type_fit_score("INTERNSHIP", "INTERNSHIP") == 5

    def test_compatible_type(self):
        """Compatible type → good score."""
        from app.matching.scorer import _type_fit_score
        assert _type_fit_score("FULL_TIME", "INTERNSHIP") >= 4


# ══════════════════════════════════════════════════════════════════════════
# 7. MISSING PROFILE DATA
# ══════════════════════════════════════════════════════════════════════════


class TestMissingData:
    def test_empty_profile_scores_zero_skills(self):
        """Empty profile → 0 skill score but non-negative total."""
        pf = _make_profile_features()
        of = _make_opp_features(skills={"python"})
        result = score_match(pf, of)
        assert result.skill_overlap_score == 0
        assert result.score >= 0

    def test_sparse_opportunity(self):
        """Opportunity with no description → minimal but non-negative."""
        pf = _make_profile_features(skills={"python"})
        of = _make_opp_features()  # no skills
        result = score_match(pf, of)
        assert result.score >= 0


# ══════════════════════════════════════════════════════════════════════════
# 8. RANKING ORDER
# ══════════════════════════════════════════════════════════════════════════


class TestRanking:
    def test_ranking_order(self, db):
        """Higher-scored opportunities come first."""
        profile = Profile(name="Ranker", email="ranker@example.com")
        db.add(profile)
        db.flush()

        skill = Skill(profile_id=profile.id, name="Python")
        db.add(skill)
        db.flush()

        company = Company(name="RankCo")
        db.add(company)
        db.flush()

        # Perfect match
        opp1 = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Python Developer",
            description="We need Python, Django, PostgreSQL.",
        )
        # No match
        opp2 = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Marketing Manager",
            description="Marketing, SEO, social media.",
        )
        db.add_all([opp1, opp2])
        db.flush()

        from app.services.matching import rank_opportunities

        results = rank_opportunities(db, profile, [opp1, opp2])
        assert len(results) == 2
        # Python developer should rank higher
        assert results[0].score >= results[1].score


# ══════════════════════════════════════════════════════════════════════════
# 9. API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════


class TestMatchingAPI:
    def test_single_match_success(self, client, db):
        """GET /matching/profiles/{id}/opportunities/{id} returns match result."""
        profile = Profile(name="API Tester", email="api@example.com")
        db.add(profile)
        db.flush()

        skill = Skill(profile_id=profile.id, name="Python")
        db.add(skill)
        db.flush()

        company = Company(name="APICo")
        db.add(company)
        db.flush()

        opp = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Python Developer",
            description="Python, Django, PostgreSQL required.",
        )
        db.add(opp)
        db.flush()

        response = client.get(f"/matching/profiles/{profile.id}/opportunities/{opp.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["score"] >= 0
        assert data["score"] <= 100
        assert data["opportunity_id"] == opp.id
        assert data["title"] == "Python Developer"
        assert data["company_name"] == "APICo"
        assert isinstance(data["matched_skills"], list)
        assert isinstance(data["explanation"], str)

    def test_single_match_profile_not_found(self, client, db):
        """Returns 404 for non-existent profile."""
        company = Company(name="Co")
        db.add(company)
        db.flush()
        opp = Opportunity(company_id=company.id, type="FULL_TIME", title="X")
        db.add(opp)
        db.flush()

        response = client.get(f"/matching/profiles/99999/opportunities/{opp.id}")
        assert response.status_code == 404

    def test_single_match_opportunity_not_found(self, client, db):
        """Returns 404 for non-existent opportunity."""
        profile = Profile(name="X", email="x@example.com")
        db.add(profile)
        db.flush()

        response = client.get(f"/matching/profiles/{profile.id}/opportunities/99999")
        assert response.status_code == 404

    def test_ranking_success(self, client, db):
        """GET /matching/profiles/{id}/ranked returns ranked results."""
        profile = Profile(name="Ranker", email="ranker2@example.com")
        db.add(profile)
        db.flush()

        skill = Skill(profile_id=profile.id, name="Python")
        db.add(skill)
        db.flush()

        company = Company(name="RankCo2")
        db.add(company)
        db.flush()

        opp1 = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Python Developer",
            description="Python and Django.",
        )
        opp2 = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Marketing Manager",
            description="Marketing and SEO.",
        )
        db.add_all([opp1, opp2])
        db.flush()

        response = client.get(f"/matching/profiles/{profile.id}/ranked")
        assert response.status_code == 200
        data = response.json()
        assert data["profile_id"] == profile.id
        assert data["total_opportunities"] == 2
        assert len(data["matches"]) == 2
        # First match should have higher or equal score
        assert data["matches"][0]["score"] >= data["matches"][1]["score"]

    def test_ranking_with_limit(self, client, db):
        """Limit parameter works."""
        profile = Profile(name="Lim", email="lim@example.com")
        db.add(profile)
        db.flush()

        company = Company(name="LimCo")
        db.add(company)
        db.flush()

        for i in range(5):
            opp = Opportunity(
                company_id=company.id,
                type="FULL_TIME",
                title=f"Role {i}",
            )
            db.add(opp)
        db.flush()

        response = client.get(f"/matching/profiles/{profile.id}/ranked?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["matches"]) == 2

    def test_ranking_profile_not_found(self, client, db):
        """Returns 404 for non-existent profile."""
        response = client.get("/matching/profiles/99999/ranked")
        assert response.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# 10. COMPONENT SCORE TRANSPARENCY
# ══════════════════════════════════════════════════════════════════════════


class TestComponentScores:
    def test_component_scores_sum_to_total(self, db):
        """Component scores should add up to the total score."""
        profile = Profile(name="Comp", email="comp@example.com")
        db.add(profile)
        db.flush()

        skill = Skill(profile_id=profile.id, name="Python")
        db.add(skill)
        db.flush()

        company = Company(name="CompCo")
        db.add(company)
        db.flush()

        opp = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Python Developer",
            description="Python, Django.",
        )
        db.add(opp)
        db.flush()

        from app.services.matching import match_opportunity

        result = match_opportunity(db, profile, opp)
        component_sum = (
            result.skill_overlap_score
            + result.title_relevance_score
            + result.experience_relevance_score
            + result.project_relevance_score
            + result.location_fit_score
            + result.type_fit_score
        )
        assert component_sum == result.score

    def test_all_component_scores_non_negative(self):
        """No component score should be negative."""
        pf = _make_profile_features(skills={"python"})
        of = _make_opp_features(skills={"python"})
        result = score_match(pf, of)
        assert result.skill_overlap_score >= 0
        assert result.title_relevance_score >= 0
        assert result.experience_relevance_score >= 0
        assert result.project_relevance_score >= 0
        assert result.location_fit_score >= 0
        assert result.type_fit_score >= 0


# ══════════════════════════════════════════════════════════════════════════
# 11. EXISTING API PRESERVATION
# ══════════════════════════════════════════════════════════════════════════


class TestExistingAPIPreservation:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_opportunity_crud(self, client, db):
        company_resp = client.post("/companies", json={"name": "Match Test Co"})
        company_id = company_resp.json()["id"]

        opp_resp = client.post("/opportunities", json={
            "company_id": company_id,
            "type": "FULL_TIME",
            "title": "Match CRUD Test",
        })
        assert opp_resp.status_code == 201
        opp_id = opp_resp.json()["id"]

        get_resp = client.get(f"/opportunities/{opp_id}")
        assert get_resp.status_code == 200

        del_resp = client.delete(f"/opportunities/{opp_id}")
        assert del_resp.status_code == 204

    def test_profile_crud(self, client, db):
        profile_resp = client.post("/profiles", json={
            "name": "Match Profile",
            "email": "match@example.com",
        })
        assert profile_resp.status_code == 201
        profile_id = profile_resp.json()["id"]

        get_resp = client.get(f"/profiles/{profile_id}")
        assert get_resp.status_code == 200

    def test_discovery_endpoint_still_works(self, client, db):
        raw_item = {
            "source_name": "manual",
            "title": "Manual Entry",
            "company_name": "Manual Co",
        }
        response = client.post("/discovery/run", json=[raw_item])
        assert response.status_code == 200
