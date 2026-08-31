"""Planning service — time horizon classification and priority scoring.

Derives planning information from existing Opportunity fields:
- deadline, match_score, status, priority, type

No new database columns. No fabricated dates.
All classification is deterministic and timezone-aware.

classify_horizon precedence (non-overlapping, in order):
  1. SUMMER_2027: deadline in May 1 – June 30, 2027
  2. NOW: deadline within 7 days (including past deadlines)
  3. UPCOMING: deadline within 8–30 days
  4. FUTURE: deadline beyond 30 days (outside Summer 2027)
  5. UNKNOWN: no deadline available

created_at is discovery metadata, NOT an opportunity deadline.
It must NOT be used to infer NOW/UPCOMING/FUTURE.

Planning priority (0–100):
- Combines deadline proximity, match_score, and opportunity priority
- Distinct from match_score (which measures candidate↔opportunity fit)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.opportunity import Opportunity

logger = logging.getLogger(__name__)

# ── Planning horizons ────────────────────────────────────────────────────

HORIZON_NOW = "NOW"
HORIZON_UPCOMING = "UPCOMING"
HORIZON_SUMMER_2027 = "SUMMER_2027"
HORIZON_FUTURE = "FUTURE"
HORIZON_UNKNOWN = "UNKNOWN"

# Summer 2027 planning window: May 1 – June 30, 2027
_SUMMER_2027_START = datetime(2027, 5, 1, tzinfo=timezone.utc)
_SUMMER_2027_END = datetime(2027, 7, 1, tzinfo=timezone.utc)


def classify_horizon(
    deadline: datetime | None,
    now: datetime | None = None,
) -> str:
    """Classify an opportunity into a planning horizon.

    Uses ONLY the deadline field for temporal classification.
    created_at is discovery metadata — it does NOT indicate when
    the opportunity must be acted on.

    Precedence (non-overlapping):
      1. SUMMER_2027: deadline in May 1 – June 30, 2027
      2. NOW: deadline within 7 days (including past deadlines)
      3. UPCOMING: deadline within 8–30 days
      4. FUTURE: deadline beyond 30 days (outside Summer 2027)
      5. UNKNOWN: no deadline available

    Args:
        deadline: The opportunity's application deadline (if known).
        now: Current time (for testability). Uses UTC now if None.

    Returns:
        One of: NOW, UPCOMING, SUMMER_2027, FUTURE, UNKNOWN
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # No deadline → UNKNOWN (created_at is NOT a substitute)
    if deadline is None:
        return HORIZON_UNKNOWN

    # Ensure timezone-aware
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    # 1. SUMMER_2027 takes precedence over generic FUTURE
    if _SUMMER_2027_START <= deadline < _SUMMER_2027_END:
        return HORIZON_SUMMER_2027

    days_until = (deadline - now).days

    # 2. NOW: deadline within 7 days or already past
    if days_until <= 7:
        return HORIZON_NOW

    # 3. UPCOMING: deadline within 8–30 days
    if days_until <= 30:
        return HORIZON_UPCOMING

    # 4. FUTURE: deadline beyond 30 days
    return HORIZON_FUTURE


def calculate_planning_priority(
    *,
    match_score: int | None,
    deadline: datetime | None,
    priority: str,
    status: str,
    opp_type: str,
    now: datetime | None = None,
) -> tuple[int, list[str]]:
    """Calculate a deterministic planning priority score.

    Returns:
        A tuple of (score, reasons) where score is 0–100.

    Planning priority answers: "What should I act on first?"
    Match score answers: "How well do I fit?"

    These are intentionally separate concepts.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    score = 0
    reasons: list[str] = []

    # ── Deadline urgency (0–40 points) ──────────────────────────
    if deadline is not None:
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        days_until = (deadline - now).days

        if days_until < 0:
            score += 40
            reasons.append("Deadline has passed — highest urgency")
        elif days_until <= 3:
            score += 40
            reasons.append(f"Deadline in {days_until} day(s)")
        elif days_until <= 7:
            score += 35
            reasons.append(f"Deadline in {days_until} days")
        elif days_until <= 14:
            score += 25
            reasons.append(f"Deadline in {days_until} days")
        elif days_until <= 30:
            score += 15
            reasons.append(f"Deadline in {days_until} days")
        elif days_until <= 90:
            score += 5
            reasons.append(f"Deadline in {days_until} days (planning ahead)")
    else:
        reasons.append("No known deadline")

    # ── Match score contribution (0–30 points) ──────────────────
    if match_score is not None:
        match_points = int(match_score * 0.3)
        score += match_points
        if match_score >= 80:
            reasons.append(f"High match ({match_score}/100)")
        elif match_score >= 50:
            reasons.append(f"Moderate match ({match_score}/100)")
    else:
        reasons.append("No match score available")

    # ── Priority field contribution (0–15 points) ───────────────
    priority_upper = priority.upper() if priority else "MEDIUM"
    if priority_upper == "HIGH":
        score += 15
        reasons.append("Marked HIGH priority")
    elif priority_upper == "MEDIUM":
        score += 8
    elif priority_upper == "LOW":
        score += 3

    # ── Status contribution (0–10 points) ───────────────────────
    status_upper = status.upper() if status else "DISCOVERED"
    if status_upper == "DISCOVERED":
        score += 10
        reasons.append("Newly discovered — review needed")
    elif status_upper == "IN_PROGRESS":
        score += 8
    elif status_upper == "APPLIED":
        score += 5

    # ── Type contribution (0–5 points) ──────────────────────────
    type_upper = opp_type.upper() if opp_type else ""
    if type_upper in ("INTERNSHIP", "RESEARCH"):
        score += 5
        if type_upper == "INTERNSHIP":
            reasons.append("Internship — time-sensitive hiring cycle")
    elif type_upper in ("FULL_TIME", "STARTUP"):
        score += 3

    return min(100, score), reasons


def get_planning_data(
    db: Session,
    *,
    profile_id: int | None = None,
    horizon: str | None = None,
    min_match_score: int | None = None,
    opp_type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Get planning data for opportunities with classification and priority.

    Returns a list of planning info dicts, sorted by planning_priority desc.
    """
    now = datetime.now(timezone.utc)

    stmt = select(Opportunity)
    if opp_type is not None:
        stmt = stmt.where(Opportunity.type == opp_type)
    if status is not None:
        stmt = stmt.where(Opportunity.status == status)
    if priority is not None:
        stmt = stmt.where(Opportunity.priority == priority)
    if min_match_score is not None:
        stmt = stmt.where(
            Opportunity.match_score.isnot(None),
            Opportunity.match_score >= min_match_score,
        )

    opportunities = list(db.scalars(stmt))

    results = []
    for opp in opportunities:
        # Get company name
        company = db.get(Company, opp.company_id)
        company_name = company.name if company else None

        # Classify horizon
        hz = classify_horizon(opp.deadline, now)

        # Filter by horizon if requested
        if horizon is not None and hz != horizon:
            continue

        # Calculate planning priority
        priority_score, reasons = calculate_planning_priority(
            match_score=opp.match_score,
            deadline=opp.deadline,
            priority=opp.priority,
            status=opp.status,
            opp_type=opp.type,
            now=now,
        )

        results.append({
            "opportunity_id": opp.id,
            "title": opp.title,
            "company_name": company_name,
            "opportunity_type": opp.type,
            "status": opp.status,
            "priority": opp.priority,
            "deadline": opp.deadline,
            "match_score": opp.match_score,
            "planning_horizon": hz,
            "planning_priority": priority_score,
            "planning_priority_reasons": reasons,
        })

    # Sort by planning_priority descending
    results.sort(key=lambda r: (-r["planning_priority"], r["opportunity_id"]))

    return results[:limit]
