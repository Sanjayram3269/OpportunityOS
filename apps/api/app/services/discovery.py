from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.discovery.deduplicator import deduplicate
from app.discovery.models import IngestionResult
from app.discovery.normalizer import NormalizedOpportunity
from app.models.company import Company
from app.models.opportunity import Opportunity
from app.models.opportunity_evidence import OpportunityEvidence


# ── Company resolution ────────────────────────────────────────────────────


def resolve_company(
    db: Session,
    company_name: str,
) -> Company:
    """Find an existing company by normalized name, or create a new one.

    Company name uniqueness is enforced at the DB level, so we do a
    read-then-create pattern here.  If the company already exists (even
    under slight name variations that survived normalization), we reuse it.
    """
    statement = select(Company).where(Company.name == company_name)
    company = db.scalar(statement)

    if company is not None:
        return company

    company = Company(name=company_name)
    db.add(company)

    try:
        db.commit()
    except IntegrityError:
        # Race condition: another request created the same company.
        db.rollback()
        company = db.scalar(statement)
        if company is None:
            raise  # genuinely failed — re-raise

    db.refresh(company)
    return company


# ── Duplicate detection (database) ────────────────────────────────────────


def _is_duplicate(
    db: Session,
    item: NormalizedOpportunity,
) -> bool:
    """Check whether an opportunity from this source already exists.

    Uses the ``opportunity_evidence`` table as the dedup index:
    a row with ``source=<source_name>`` and ``evidence_type='external_id'``
    means we've already ingested this external record.
    """
    if item.external_id is not None:
        statement = (
            select(OpportunityEvidence.id)
            .where(OpportunityEvidence.source == item.source_name)
            .where(OpportunityEvidence.evidence_type == "external_id")
            .where(OpportunityEvidence.content == item.external_id)
            .limit(1)
        )
        if db.scalar(statement) is not None:
            return True

    # Fallback: canonical URL duplicate
    if item.canonical_source_url is not None:
        statement = (
            select(Opportunity.id)
            .where(Opportunity.source_url == item.canonical_source_url)
            .limit(1)
        )
        if db.scalar(statement) is not None:
            return True

    return False


# ── Single-item ingestion ─────────────────────────────────────────────────


def _ingest_one(
    db: Session,
    item: NormalizedOpportunity,
) -> bool:
    """Persist a single normalized opportunity.

    Returns ``True`` if ingested, ``False`` if skipped (duplicate).
    """
    if _is_duplicate(db, item):
        return False

    # Resolve company
    company = resolve_company(db, item.normalized_company_name)

    # Create opportunity
    opportunity = Opportunity(
        company_id=company.id,
        type=item.opportunity_type,
        title=item.normalized_title,
        description=item.description,
        source_url=item.canonical_source_url,
        status="DISCOVERED",
        priority="MEDIUM",
        deadline=item.deadline,
    )
    db.add(opportunity)
    db.flush()  # get opportunity.id

    # Record evidence: external_id
    if item.external_id is not None:
        evidence = OpportunityEvidence(
            opportunity_id=opportunity.id,
            source=item.source_name,
            evidence_type="external_id",
            content=item.external_id,
        )
        db.add(evidence)

    # Record evidence: source_url (if present and different from opportunity.source_url)
    if item.canonical_source_url is not None:
        evidence = OpportunityEvidence(
            opportunity_id=opportunity.id,
            source=item.source_name,
            evidence_type="source_url",
            content=item.canonical_source_url,
        )
        db.add(evidence)

    db.flush()
    return True


# ── Batch ingestion ───────────────────────────────────────────────────────


def ingest(
    db: Session,
    items: list[NormalizedOpportunity],
) -> IngestionResult:
    """Ingest a batch of normalized opportunities into the database.

    Steps:
      1. Deduplicate within the batch
      2. For each item, check database for existing duplicates
      3. Resolve/create companies
      4. Persist new opportunities + evidence records

    Returns an ``IngestionResult`` summary.
    """
    # Deduplicate within batch first
    unique_items = deduplicate(items)

    source_name = unique_items[0].source_name if unique_items else "unknown"
    raw_count = len(items)
    ingested = 0
    duplicates_skipped = 0
    companies_created = 0
    errors: list[str] = []

    for item in unique_items:
        try:
            # Check if company already existed
            existing_company = db.scalar(
                select(Company).where(Company.name == item.normalized_company_name)
            )
            was_new_company = existing_company is None

            ingested_item = _ingest_one(db, item)

            if ingested_item:
                ingested += 1
                if was_new_company:
                    companies_created += 1
            else:
                duplicates_skipped += 1

        except Exception as exc:
            errors.append(f"{item.source_name}/{item.normalized_title}: {exc!s}")

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        errors.append("Failed to commit batch — integrity error")

    return IngestionResult(
        source_name=source_name,
        raw_count=raw_count,
        ingested=ingested,
        duplicates_skipped=duplicates_skipped,
        companies_created=companies_created,
        errors=errors,
    )
