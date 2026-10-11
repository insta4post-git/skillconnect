from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.models import ProviderProfile, User, WeekDay
from app.security import require_provider

router = APIRouter(prefix="/api/providers", tags=["providers"])

# Only logged-in PROVIDER users can use these endpoints, and every one of them
# works on the caller's own profile ("me"). No user id appears in any URL.

DAY_ORDER = {day: index for index, day in enumerate(WeekDay)}


def get_profile_or_404(user: User) -> ProviderProfile:
    if user.provider_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider profile not created yet. Save it first with PUT /api/providers/me.",
        )
    return user.provider_profile


def build_provider_out(user: User, profile: ProviderProfile) -> schemas.ProviderProfileOut:
    skills = sorted((link.skill for link in profile.skills), key=lambda s: s.name)
    slots = sorted(
        profile.availability,
        key=lambda a: (DAY_ORDER[a.day_of_week], a.start_time),
    )
    return schemas.ProviderProfileOut.model_validate(
        {
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "photo_url": user.photo_url,
            "bio": user.bio,
            "location": user.location,
            "description": profile.description,
            "experience_years": profile.experience_years,
            "qualification": profile.qualification,
            "working_area": profile.working_area,
            "service_mode": profile.service_mode,
            "pricing_info": profile.pricing_info,
            "availability_notes": profile.availability_notes,
            "skills": skills,
            "availability": slots,
            "is_complete": bool(user.location_id and profile.description and skills),
        },
        from_attributes=True,
    )


@router.get("/me", response_model=schemas.ProviderProfileOut)
def get_my_provider_profile(current_user: User = Depends(require_provider)):
    profile = get_profile_or_404(current_user)
    return build_provider_out(current_user, profile)


@router.put("/me", response_model=schemas.ProviderProfileOut)
def save_my_provider_profile(
    payload: schemas.ProviderProfileIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    profile = crud.upsert_provider_profile(db, current_user, payload)
    return build_provider_out(current_user, profile)


@router.put("/me/skills", response_model=schemas.ProviderProfileOut)
def save_my_skills(
    payload: schemas.ProviderSkillsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    profile = get_profile_or_404(current_user)
    try:
        crud.set_provider_skills(db, profile, payload.skill_ids)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return build_provider_out(current_user, profile)


@router.put("/me/availability", response_model=schemas.ProviderProfileOut)
def save_my_availability(
    payload: schemas.AvailabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    profile = get_profile_or_404(current_user)
    crud.set_provider_availability(db, profile, payload.slots)
    return build_provider_out(current_user, profile)
