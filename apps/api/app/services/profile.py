from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.schemas.profile import ProfileCreate, ProfileUpdate


def create_profile(
    db: Session,
    profile_data: ProfileCreate,
) -> Profile:
    profile = Profile(
        name=profile_data.name,
        email=str(profile_data.email),
        phone=profile_data.phone,
        linkedin_url=str(profile_data.linkedin_url)
        if profile_data.linkedin_url
        else None,
        github_url=str(profile_data.github_url)
        if profile_data.github_url
        else None,
        portfolio_url=str(profile_data.portfolio_url)
        if profile_data.portfolio_url
        else None,
        headline=profile_data.headline,
        bio=profile_data.bio,
    )

    db.add(profile)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("A profile with this email already exists")

    db.refresh(profile)

    return profile


def get_profile(
    db: Session,
    profile_id: int,
) -> Profile | None:
    statement = select(Profile).where(Profile.id == profile_id)

    return db.scalar(statement)


def list_profiles(
    db: Session,
) -> list[Profile]:
    statement = select(Profile).order_by(Profile.id)

    return list(db.scalars(statement).all())


def update_profile(
    db: Session,
    profile: Profile,
    profile_data: ProfileUpdate,
) -> Profile:
    update_data = profile_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is not None and field in {
            "linkedin_url",
            "github_url",
            "portfolio_url",
        }:
            value = str(value)

        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    return profile


def delete_profile(
    db: Session,
    profile: Profile,
) -> None:
    db.delete(profile)
    db.commit()