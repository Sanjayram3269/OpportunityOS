"""Comprehensive tests for the AI Intelligence Layer.

Tests cover:
  1. AIInsight data model
  2. Provider abstraction and exceptions
  3. OpenAI-compatible provider (mocked)
  4. Prompt construction
  5. JSON parsing from AI text
  6. Provider timeout / HTTP failure / malformed response
  7. Missing API key handling
  8. Deterministic score preservation
  9. AI cannot overwrite deterministic score
  10. AI unavailable fallback
  11. Full insight service integration
  12. API endpoint
  13. Existing matching regression
  14. Existing API preservation
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.base import (
    AIInsight,
    AIPermissionError,
    AIProviderError,
    AITimeoutError,
)
from app.ai.prompts import (
    build_insight_prompt,
    build_match_result_summary,
    build_opportunity_summary,
    build_profile_summary,
)
from app.ai.providers.openai_compat import (
    OpenAICompatProvider,
    _extract_content,
    _parse_json_from_text,
)
from app.matching.extractor import (
    OpportunityFeatures,
    ProfileFeatures,
)
from app.matching.scorer import MatchResult, score_match
from app.models.company import Company
from app.models.opportunity import Opportunity
from app.models.profile import Profile
from app.models.project import Project
from app.models.skill import Skill


# ══════════════════════════════════════════════════════════════════════════
# 1. AIInsight DATA MODEL
# ══════════════════════════════════════════════════════════════════════════


class TestAIInsightModel:
    def test_default_is_unavailable(self):
        insight = AIInsight()
        assert insight.available is False
        assert insight.strengths == []
        assert insight.gaps == []
        assert insight.recommendations == []
        assert insight.outreach_angles == []

    def test_unavailable_with_reason(self):
        insight = AIInsight.unavailable("No API key")
        assert insight.available is False
        assert insight.error == "No API key"

    def test_from_dict_valid(self):
        data = {
            "match_explanation": "Strong Python match",
            "strengths": ["Python", "Django"],
            "gaps": ["AWS"],
            "recommendations": ["Add AWS project"],
            "outreach_angles": ["Mention Django project"],
            "application_advice": "Apply soon",
        }
        insight = AIInsight.from_dict(data)
        assert insight.available is True
        assert insight.match_explanation == "Strong Python match"
        assert insight.strengths == ["Python", "Django"]
        assert insight.gaps == ["AWS"]
        assert insight.recommendations == ["Add AWS project"]
        assert insight.outreach_angles == ["Mention Django project"]
        assert insight.application_advice == "Apply soon"

    def test_from_dict_with_string_list(self):
        """If the AI returns a single string instead of a list, wrap it."""
        data = {
            "strengths": "Python expertise",
            "gaps": "",
        }
        insight = AIInsight.from_dict(data)
        assert insight.strengths == ["Python expertise"]
        assert insight.gaps == []

    def test_from_dict_invalid_type(self):
        insight = AIInsight.from_dict("not a dict")  # type: ignore
        assert insight.available is False
        assert "Invalid" in (insight.error or "")

    def test_from_dict_unknown_fields_ignored(self):
        data = {
            "match_explanation": "Good match",
            "unknown_field": "should be ignored",
            "strengths": [],
        }
        insight = AIInsight.from_dict(data)
        assert insight.match_explanation == "Good match"
        assert not hasattr(insight, "unknown_field")


# ══════════════════════════════════════════════════════════════════════════
# 2. PROVIDER EXCEPTIONS
# ══════════════════════════════════════════════════════════════════════════


class TestProviderExceptions:
    def test_hierarchies(self):
        assert issubclass(AIPermissionError, AIProviderError)
        assert issubclass(AITimeoutError, AIProviderError)
        assert issubclass(AIProviderError, Exception)

    def test_can_be_caught_as_base(self):
        with pytest.raises(AIProviderError):
            raise AIPermissionError("no key")


# ══════════════════════════════════════════════════════════════════════════
# 3. PROMPT CONSTRUCTION
# ══════════════════════════════════════════════════════════════════════════


class TestPromptConstruction:
    def test_profile_summary_basic(self):
        summary = build_profile_summary(
            profile_name="Sanjay",
            headline="Python Engineer",
            skills=["python", "django"],
        )
        assert summary["name"] == "Sanjay"
        assert summary["headline"] == "Python Engineer"
        assert summary["skills"] == ["django", "python"]

    def test_profile_summary_with_long_bio(self):
        bio = "x" * 600
        summary = build_profile_summary(bio=bio)
        assert len(summary["bio"]) <= 500

    def test_opportunity_summary_basic(self):
        summary = build_opportunity_summary(
            title="Python Developer",
            company_name="Google",
            location="Remote",
        )
        assert summary["title"] == "Python Developer"
        assert summary["company"] == "Google"
        assert summary["location"] == "Remote"

    def test_opportunity_summary_truncates_long_description(self):
        desc = "x" * 2000
        summary = build_opportunity_summary(description=desc)
        assert len(summary["description"]) <= 1500

    def test_match_result_summary(self):
        summary = build_match_result_summary(
            score=58,
            matched_skills=["python", "django"],
            missing_skills=["aws"],
            matched_signals=["3 shared skills"],
            concerns=["Missing AWS"],
            explanation="Good match",
            component_scores={"skill_overlap": 20},
        )
        assert summary["score"] == 58
        assert summary["matched_skills"] == ["python", "django"]
        assert summary["component_scores"]["skill_overlap"] == 20

    def test_build_insight_prompt_contains_context(self):
        prompt = build_insight_prompt(
            profile_summary={"name": "Test", "skills": ["python"]},
            opportunity_summary={"title": "Python Dev", "company": "Co"},
            match_result={"score": 45},
        )
        assert "Test" in prompt
        assert "Python Dev" in prompt
        assert "45" in prompt
        assert "JSON" in prompt


# ══════════════════════════════════════════════════════════════════════════
# 4. JSON PARSING FROM AI TEXT
# ══════════════════════════════════════════════════════════════════════════


class TestJSONParsing:
    def test_parse_json_code_block(self):
        text = 'Here is the analysis:\n```json\n{"match_explanation": "Good"}\n```\nDone.'
        result = _parse_json_from_text(text)
        assert result is not None
        assert result["match_explanation"] == "Good"

    def test_parse_json_raw_object(self):
        text = '{"match_explanation": "Strong", "strengths": ["Python"]}'
        result = _parse_json_from_text(text)
        assert result is not None
        assert result["match_explanation"] == "Strong"

    def test_parse_json_with_surrounding_text(self):
        text = 'Based on the analysis:\n{"match_explanation": "OK"}\nNote: some extra text'
        result = _parse_json_from_text(text)
        assert result is not None
        assert result["match_explanation"] == "OK"

    def test_parse_json_invalid(self):
        result = _parse_json_from_text("This is not JSON at all")
        assert result is None

    def test_parse_json_empty_code_block(self):
        result = _parse_json_from_text("```json\n\n```")
        # Empty code block, should still find nothing
        assert result is None


# ══════════════════════════════════════════════════════════════════════════
# 5. CONTENT EXTRACTION
# ══════════════════════════════════════════════════════════════════════════


class TestContentExtraction:
    def test_extract_from_openai_format(self):
        data = {
            "choices": [
                {"message": {"content": "Hello world"}}
            ]
        }
        assert _extract_content(data) == "Hello world"

    def test_extract_from_generated_text(self):
        data = {"generated_text": "Hello world"}
        assert _extract_content(data) == "Hello world"

    def test_extract_no_choices(self):
        data = {"choices": []}
        assert _extract_content(data) is None

    def test_extract_no_content(self):
        data = {"choices": [{"message": {}}]}
        assert _extract_content(data) is None


# ══════════════════════════════════════════════════════════════════════════
# 6. OPENAI-COMPATIBLE PROVIDER
# ══════════════════════════════════════════════════════════════════════════


def _make_ai_response(content: dict) -> dict:
    """Build a mock OpenAI-compatible API response."""
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(content),
                }
            }
        ]
    }


class TestOpenAICompatProvider:
    def test_missing_api_key_raises(self):
        provider = OpenAICompatProvider(
            api_url="https://example.com/v1/chat/completions",
            api_key=None,
        )
        assert provider.provider_name == "openai_compat"

    @pytest.mark.anyio
    async def test_missing_api_key_permission_error(self):
        provider = OpenAICompatProvider(
            api_url="https://example.com/v1/chat/completions",
            api_key=None,
        )
        context = {"profile_summary": {}, "opportunity_summary": {}, "match_result": {}}
        with pytest.raises(AIPermissionError):
            await provider.generate_insight(context)

    @pytest.mark.anyio
    async def test_huggingface_provider_name(self):
        provider = OpenAICompatProvider(
            api_url="https://api-inference.huggingface.co/models/mistral",
            api_key="test-key",
            model="mistral",
        )
        assert provider.provider_name == "huggingface"
        assert provider.model_name == "mistral"

    @pytest.mark.anyio
    async def test_openrouter_provider_name(self):
        provider = OpenAICompatProvider(
            api_url="https://openrouter.ai/api/v1/chat/completions",
            api_key="test-key",
        )
        assert provider.provider_name == "openrouter"

    @pytest.mark.anyio
    async def test_successful_insight(self):
        ai_response = {
            "match_explanation": "Strong Python match",
            "strengths": ["Python", "Django"],
            "gaps": ["AWS"],
            "recommendations": ["Add cloud project"],
            "outreach_angles": ["Mention Django experience"],
            "application_advice": "Apply now",
        }

        provider = OpenAICompatProvider(
            api_url="https://example.com/v1/chat/completions",
            api_key="test-key",
            model="test-model",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _make_ai_response(ai_response)

        with patch("app.ai.providers.openai_compat.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await provider.generate_insight({
                "profile_summary": {},
                "opportunity_summary": {},
                "match_result": {},
            })

        assert result["match_explanation"] == "Strong Python match"
        assert result["strengths"] == ["Python", "Django"]
        assert result["provider"] == "openai_compat"  # example.com is not huggingface
        assert result["model"] == "test-model"

    @pytest.mark.anyio
    async def test_timeout_handling(self):
        provider = OpenAICompatProvider(
            api_url="https://example.com/v1/chat/completions",
            api_key="test-key",
        )

        with patch("app.ai.providers.openai_compat.httpx.AsyncClient") as mock_client:
            import httpx
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(AITimeoutError):
                await provider.generate_insight({
                    "profile_summary": {},
                    "opportunity_summary": {},
                    "match_result": {},
                })

    @pytest.mark.anyio
    async def test_http_error_handling(self):
        provider = OpenAICompatProvider(
            api_url="https://example.com/v1/chat/completions",
            api_key="test-key",
        )

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")

        with patch("app.ai.providers.openai_compat.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(AIProviderError):
                await provider.generate_insight({
                    "profile_summary": {},
                    "opportunity_summary": {},
                    "match_result": {},
                })

    @pytest.mark.anyio
    async def test_malformed_json_response(self):
        provider = OpenAICompatProvider(
            api_url="https://example.com/v1/chat/completions",
            api_key="test-key",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "I cannot do that."}}]
        }

        with patch("app.ai.providers.openai_compat.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(AIProviderError, match="could not parse JSON"):
                await provider.generate_insight({
                    "profile_summary": {},
                    "opportunity_summary": {},
                    "match_result": {},
                })

    @pytest.mark.anyio
    async def test_empty_choices_response(self):
        provider = OpenAICompatProvider(
            api_url="https://example.com/v1/chat/completions",
            api_key="test-key",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"choices": []}

        with patch("app.ai.providers.openai_compat.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(AIProviderError, match="no content"):
                await provider.generate_insight({
                    "profile_summary": {},
                    "opportunity_summary": {},
                    "match_result": {},
                })


# ══════════════════════════════════════════════════════════════════════════
# 7. DETERMINISTIC SCORE PRESERVATION
# ══════════════════════════════════════════════════════════════════════════


class TestScorePreservation:
    def test_ai_cannot_overwrite_score(self):
        """The AIInsight model has no score field — only MatchResult has one."""
        insight = AIInsight.from_dict({
            "match_explanation": "Good",
            "score": 999,  # This should NOT be accepted
        })
        assert not hasattr(insight, "score") or getattr(insight, "score", None) is None
        # The score lives in MatchResult, not AIInsight

    def test_deterministic_score_always_same(self):
        """Same inputs → same score, regardless of AI state."""
        pf = ProfileFeatures(skills={"python", "django"})
        of = OpportunityFeatures(
            title="Python Dev", type="FULL_TIME",
            description_skills={"python", "django", "postgresql"},
        )
        r1 = score_match(pf, of)
        r2 = score_match(pf, of)
        assert r1.score == r2.score


# ══════════════════════════════════════════════════════════════════════════
# 8. AI INSIGHT SERVICE (FALLBACK)
# ══════════════════════════════════════════════════════════════════════════


class TestInsightService:
    def test_no_provider_returns_unavailable(self, db):
        """When provider is None, insight is unavailable but match still works."""
        from app.services.ai_insight import generate_insight

        profile = Profile(name="AI Test", email="ai@test.com")
        db.add(profile)
        db.flush()

        skill = Skill(profile_id=profile.id, name="Python")
        db.add(skill)
        db.flush()

        company = Company(name="AITestCo")
        db.add(company)
        db.flush()

        opp = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Python Developer",
            description="Python, Django required.",
        )
        db.add(opp)
        db.flush()

        import asyncio

        insight, match_result = asyncio.run(
            generate_insight(db, profile, opp, provider=None)
        )

        assert insight.available is False
        assert match_result.score >= 0
        assert "python" in match_result.matched_skills

    def test_provider_permission_error_graceful(self, db):
        """Provider with no API key returns unavailable, not crash."""
        from app.services.ai_insight import generate_insight

        profile = Profile(name="AI Test 2", email="ai2@test.com")
        db.add(profile)
        db.flush()

        skill = Skill(profile_id=profile.id, name="Python")
        db.add(skill)
        db.flush()

        company = Company(name="AITestCo2")
        db.add(company)
        db.flush()

        opp = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Python Developer",
        )
        db.add(opp)
        db.flush()

        provider = OpenAICompatProvider(
            api_url="https://example.com/v1/chat/completions",
            api_key=None,  # No key
        )

        import asyncio

        insight, match_result = asyncio.run(
            generate_insight(db, profile, opp, provider=provider)
        )

        assert insight.available is False
        assert insight.error is not None
        assert match_result.score >= 0

    def test_provider_timeout_graceful(self, db):
        """Provider timeout returns unavailable, not crash."""
        from app.services.ai_insight import generate_insight

        profile = Profile(name="AI Test 3", email="ai3@test.com")
        db.add(profile)
        db.flush()

        company = Company(name="AITestCo3")
        db.add(company)
        db.flush()

        opp = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Some Role",
        )
        db.add(opp)
        db.flush()

        mock_provider = MagicMock()
        mock_provider.provider_name = "mock"
        mock_provider.model_name = "mock-model"
        mock_provider.generate_insight = AsyncMock(side_effect=AITimeoutError("timeout"))

        import asyncio

        insight, match_result = asyncio.run(
            generate_insight(db, profile, opp, provider=mock_provider)
        )

        assert insight.available is False
        assert "timeout" in (insight.error or "").lower()
        assert match_result.score >= 0

    def test_provider_generic_error_graceful(self, db):
        """Provider error returns unavailable, not crash."""
        from app.services.ai_insight import generate_insight

        profile = Profile(name="AI Test 4", email="ai4@test.com")
        db.add(profile)
        db.flush()

        company = Company(name="AITestCo4")
        db.add(company)
        db.flush()

        opp = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Some Role",
        )
        db.add(opp)
        db.flush()

        mock_provider = MagicMock()
        mock_provider.provider_name = "mock"
        mock_provider.model_name = "mock-model"
        mock_provider.generate_insight = AsyncMock(
            side_effect=AIProviderError("server down")
        )

        import asyncio

        insight, match_result = asyncio.run(
            generate_insight(db, profile, opp, provider=mock_provider)
        )

        assert insight.available is False
        assert match_result.score >= 0


# ══════════════════════════════════════════════════════════════════════════
# 9. BUILD CONTEXT
# ══════════════════════════════════════════════════════════════════════════


class TestBuildContext:
    def test_context_structure(self, db):
        from app.services.ai_insight import build_context

        profile = Profile(
            name="Context Test", email="ctx@test.com",
            headline="Python Engineer",
        )
        db.add(profile)
        db.flush()

        skill = Skill(profile_id=profile.id, name="Python")
        db.add(skill)
        db.flush()

        project = Project(
            profile_id=profile.id,
            name="Test Project",
            description="Built with Django and PostgreSQL",
            technologies="Django, PostgreSQL",
        )
        db.add(project)
        db.flush()

        company = Company(name="ContextCo")
        db.add(company)
        db.flush()

        opp = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Python Backend Developer",
            description="Python, Django, PostgreSQL experience required.",
        )
        db.add(opp)
        db.flush()

        context = build_context(db, profile, opp)

        assert "profile_summary" in context
        assert "opportunity_summary" in context
        assert "match_result_summary" in context
        assert "match_result" in context

        ps = context["profile_summary"]
        assert ps["name"] == "Context Test"
        assert ps["headline"] == "Python Engineer"
        assert "python" in ps["skills"]

        ms = context["match_result_summary"]
        assert 0 <= ms["score"] <= 100


# ══════════════════════════════════════════════════════════════════════════
# 10. API ENDPOINT
# ══════════════════════════════════════════════════════════════════════════


class TestInsightAPI:
    def test_insight_endpoint_no_ai_configured(self, client, db):
        """GET /matching/.../insight returns deterministic result when AI is off."""
        profile = Profile(name="API Insight", email="api-insight@test.com")
        db.add(profile)
        db.flush()

        skill = Skill(profile_id=profile.id, name="Python")
        db.add(skill)
        db.flush()

        company = Company(name="InsightCo")
        db.add(company)
        db.flush()

        opp = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Python Developer",
            description="Python, Django required.",
        )
        db.add(opp)
        db.flush()

        response = client.get(
            f"/matching/profiles/{profile.id}/opportunities/{opp.id}/insight"
        )
        assert response.status_code == 200
        data = response.json()

        # Deterministic score present
        assert 0 <= data["score"] <= 100
        assert data["opportunity_id"] == opp.id
        assert data["company_name"] == "InsightCo"
        assert isinstance(data["matched_skills"], list)

        # AI insight unavailable
        assert data["ai_insight"]["available"] is False

    def test_insight_endpoint_profile_not_found(self, client, db):
        company = Company(name="Co")
        db.add(company)
        db.flush()
        opp = Opportunity(company_id=company.id, type="FULL_TIME", title="X")
        db.add(opp)
        db.flush()

        response = client.get(
            f"/matching/profiles/99999/opportunities/{opp.id}/insight"
        )
        assert response.status_code == 404

    def test_insight_endpoint_opportunity_not_found(self, client, db):
        profile = Profile(name="X", email="x2@test.com")
        db.add(profile)
        db.flush()

        response = client.get(
            f"/matching/profiles/{profile.id}/opportunities/99999/insight"
        )
        assert response.status_code == 404

    def test_insight_with_mocked_ai_provider(self, client, db):
        """Insight endpoint with a mocked AI provider returns full data."""
        profile = Profile(name="Mock AI", email="mock@test.com")
        db.add(profile)
        db.flush()

        skill = Skill(profile_id=profile.id, name="Python")
        db.add(skill)
        db.flush()

        company = Company(name="MockCo")
        db.add(company)
        db.flush()

        opp = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Python Developer",
            description="Python, Django, PostgreSQL.",
        )
        db.add(opp)
        db.flush()

        mock_provider = MagicMock()
        mock_provider.provider_name = "mock"
        mock_provider.model_name = "mock-model"
        mock_provider.generate_insight = AsyncMock(return_value={
            "match_explanation": "Strong Python match with 3 shared skills",
            "strengths": ["Python", "Django", "PostgreSQL"],
            "gaps": ["AWS experience"],
            "recommendations": ["Add a cloud project"],
            "outreach_angles": ["Mention your Django project"],
            "application_advice": "Apply quickly",
        })

        with patch(
            "app.api.routes.ai_insight._get_ai_provider",
            return_value=mock_provider,
        ):
            response = client.get(
                f"/matching/profiles/{profile.id}/opportunities/{opp.id}/insight"
            )

        assert response.status_code == 200
        data = response.json()

        # Deterministic score
        assert 0 <= data["score"] <= 100
        assert "python" in data["matched_skills"]

        # AI insight
        assert data["ai_insight"]["available"] is True
        assert data["ai_insight"]["provider"] == "mock"
        assert data["ai_insight"]["model"] == "mock-model"
        assert "Python match" in data["ai_insight"]["match_explanation"]
        assert "Python" in data["ai_insight"]["strengths"]
        assert "AWS" in data["ai_insight"]["gaps"][0]


# ══════════════════════════════════════════════════════════════════════════
# 11. EXISTING MATCHING REGRESSION
# ══════════════════════════════════════════════════════════════════════════


class TestMatchingRegression:
    def test_deterministic_match_still_works(self, client, db):
        """The original matching endpoint is unaffected."""
        profile = Profile(name="Regress", email="regress@test.com")
        db.add(profile)
        db.flush()

        skill = Skill(profile_id=profile.id, name="Python")
        db.add(skill)
        db.flush()

        company = Company(name="RegressCo")
        db.add(company)
        db.flush()

        opp = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Python Developer",
            description="Python and Django.",
        )
        db.add(opp)
        db.flush()

        response = client.get(
            f"/matching/profiles/{profile.id}/opportunities/{opp.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "score" in data
        assert "ai_insight" not in data  # Original endpoint has no AI fields

    def test_ranking_still_works(self, client, db):
        profile = Profile(name="Ranker", email="ranker@test.com")
        db.add(profile)
        db.flush()

        company = Company(name="RankCo")
        db.add(company)
        db.flush()

        opp = Opportunity(
            company_id=company.id,
            type="FULL_TIME",
            title="Dev",
        )
        db.add(opp)
        db.flush()

        response = client.get(f"/matching/profiles/{profile.id}/ranked")
        assert response.status_code == 200


# ══════════════════════════════════════════════════════════════════════════
# 12. EXISTING API PRESERVATION
# ══════════════════════════════════════════════════════════════════════════


class TestExistingAPIPreservation:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_opportunity_crud(self, client, db):
        company_resp = client.post("/companies", json={"name": "AI Test Co"})
        company_id = company_resp.json()["id"]

        opp_resp = client.post("/opportunities", json={
            "company_id": company_id,
            "type": "FULL_TIME",
            "title": "AI CRUD Test",
        })
        assert opp_resp.status_code == 201
        opp_id = opp_resp.json()["id"]

        get_resp = client.get(f"/opportunities/{opp_id}")
        assert get_resp.status_code == 200

        del_resp = client.delete(f"/opportunities/{opp_id}")
        assert del_resp.status_code == 204

    def test_discovery_endpoint_still_works(self, client, db):
        raw_item = {
            "source_name": "manual",
            "title": "Manual Entry",
            "company_name": "Manual Co",
        }
        response = client.post("/discovery/run", json=[raw_item])
        assert response.status_code == 200
