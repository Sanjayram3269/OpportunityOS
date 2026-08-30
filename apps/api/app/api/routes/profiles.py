from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileUpdate
from app.services.profile import (
    create_profile,
    delete_profile,
    get_profile,
    list_profiles,
    update_profile,
)

router = APIRouter(
    prefix="/profiles",
    tags=["profiles"],
)


@router.post(
    "",
    response_model=ProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    profile_data: ProfileCreate,
    db: Session = Depends(get_db),
) -> ProfileRead:
    try:
        return create_profile(db, profile_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=list[ProfileRead],
)
def list_all(
    db: Session = Depends(get_db),
) -> list[ProfileRead]:
    return list_profiles(db)


@router.get(
    "/{profile_id}",
    response_model=ProfileRead,
)
def get_one(
    profile_id: int,
    db: Session = Depends(get_db),
) -> ProfileRead:
    profile = get_profile(db, profile_id)

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    return profile


@router.patch(
    "/{profile_id}",
    response_model=ProfileRead,
)
def update(
    profile_id: int,
    profile_data: ProfileUpdate,
    db: Session = Depends(get_db),
) -> ProfileRead:
    profile = get_profile(db, profile_id)

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    return update_profile(db, profile, profile_data)


@router.delete(
    "/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete(
    profile_id: int,
    db: Session = Depends(get_db),
) -> None:
    profile = get_profile(db, profile_id)

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    delete_profile(db, profile)