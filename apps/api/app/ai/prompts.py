"""Prompt templates for AI intelligence generation.

The prompt is deliberately structured to:
- Include only necessary context (skills, project, experience, opportunity)
- Explicitly instruct the model not to fabricate facts
- Request structured JSON output
- Distinguish known facts from suggestions
"""

from __future__ import annotations

from typing import Any


SYSTEM_PROMPT = """\
You are an AI career advisor for OpportunityOS. You analyze job/opportunity \
matches and provide actionable, honest advice.

RULES:
- Only use information provided in the context below.
- Do NOT invent skills, experience, projects, certifications, or achievements.
- Do NOT fabricate company information or contacts.
- Do NOT claim the user has skills not listed in their profile.
- Distinguish between KNOWN FACTS (from the provided data) and \
SUGGESTIONS (what they could do to improve their candidacy).
- Be concise and specific.
- Return ONLY valid JSON matching the requested schema.\
"""


def build_insight_prompt(
    profile_summary: dict[str, Any],
    opportunity_summary: dict[str, Any],
    match_result: dict[str, Any],
) -> str:
    """Build the user message containing structured context for the AI.

    Args:
        profile_summary: Extracted profile data.
        opportunity_summary: Extracted opportunity data.
        match_result: Deterministic match result data.

    Returns:
        A structured prompt string for the AI model.
    """
    parts = [
        "# Match Analysis Request",
        "",
        "## Profile Information",
        _format_dict(profile_summary),
        "",
        "## Opportunity Information",
        _format_dict(opportunity_summary),
        "",
        "## Deterministic Match Result",
        _format_dict(match_result),
        "",
        "## Your Task",
        "Analyze this match and return a JSON object with exactly these fields:",
        "",
        '```json',
        "{",
        '  "match_explanation": "Why this opportunity matches the profile (2-4 sentences)",',
        '  "strengths": ["Specific strengths from the profile that align", "..."],',
        '  "gaps": ["Important skills/requirements that appear missing", "..."],',
        '  "recommendations": ["What the user should emphasize or improve", "..."],',
        '  "outreach_angles": ["Genuine points for a personalized message", "..."],',
        '  "application_advice": "Concise advice specific to this opportunity"',
        "}",
        '```',
        "",
        "Return ONLY the JSON object. No other text.",
    ]
    return "\n".join(parts)


def _format_dict(data: dict[str, Any]) -> str:
    """Format a dict into readable context blocks."""
    lines: list[str] = []
    for key, value in data.items():
        label = key.replace("_", " ").title()
        if isinstance(value, list):
            if value:
                items = ", ".join(str(v) for v in value)
                lines.append(f"- **{label}**: {items}")
            else:
                lines.append(f"- **{label}**: None")
        elif value is None or value == "":
            lines.append(f"- **{label}**: Not provided")
        else:
            lines.append(f"- **{label}**: {value}")
    return "\n".join(lines)


def build_profile_summary(
    profile_name: str | None = None,
    headline: str | None = None,
    bio: str | None = None,
    skills: list[str] | None = None,
    project_technologies: list[str] | None = None,
    project_descriptions: list[str] | None = None,
    experience_titles: list[str] | None = None,
    experience_descriptions: list[str] | None = None,
) -> dict[str, Any]:
    """Build a clean profile summary dict for the prompt."""
    return {
        "name": profile_name,
        "headline": headline,
        "bio": bio[:500] if bio else None,
        "skills": sorted(skills) if skills else [],
        "project_technologies": sorted(project_technologies) if project_technologies else [],
        "relevant_projects": (
            project_descriptions[:3] if project_descriptions else []
        ),
        "experience_titles": sorted(experience_titles) if experience_titles else [],
        "relevant_experience": (
            experience_descriptions[:3] if experience_descriptions else []
        ),
    }


def build_opportunity_summary(
    title: str | None = None,
    company_name: str | None = None,
    description: str | None = None,
    location: str | None = None,
    opp_type: str | None = None,
    deadline: str | None = None,
    source_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a clean opportunity summary dict for the prompt."""
    summary: dict[str, Any] = {
        "title": title,
        "company": company_name,
        "location": location,
        "type": opp_type,
        "deadline": deadline,
        "source_url": source_url,
    }
    if description:
        # Truncate long descriptions to keep prompt manageable
        summary["description"] = description[:1500]
    if metadata:
        summary["metadata"] = metadata
    return summary


def build_match_result_summary(
    score: int,
    matched_skills: list[str],
    missing_skills: list[str],
    matched_signals: list[str],
    concerns: list[str],
    explanation: str,
    component_scores: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build a deterministic match result summary for the prompt."""
    return {
        "score": score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "matched_signals": matched_signals,
        "concerns": concerns,
        "deterministic_explanation": explanation,
        "component_scores": component_scores or {},
    }
