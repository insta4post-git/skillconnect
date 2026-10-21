"""Step 12 database helpers: public provider profile and review list."""

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app import schemas_profile as sp
from app.crud import provider_card
from app.models import (
    ProviderProfile,
    ProviderSkill,
    RequestStatus,
    Review,
    ServiceRequest,
    User,
    UserRole,
)

RECENT_REVIEWS = 5
_WORDS = {5: "five", 4: "four", 3: "three", 2: "two", 1: "one"}


def short_name(full_name: str) -> str:
    """'Meera Shah' -> 'Meera S.'   'Meera' -> 'Meera'.  Reviews are public."""
    parts = (full_name or "").split()
    if not parts:
        return "Customer"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0].upper()}."


def breakdown_from_rows(rows) -> sp.RatingBreakdown:
    """rows = [(rating, how_many), ...]"""
    data = {name: 0 for name in _WORDS.values()}
    for rating, number in rows:
        if rating in _WORDS:
            data[_WORDS[rating]] = int(number)
    return sp.RatingBreakdown(**data)


def public_review_out(review) -> sp.PublicReviewOut:
    return sp.PublicReviewOut(
        id=review.id,
        rating=review.rating,
        comment=review.comment,
        skill_name=review.service_request.skill.name,
        reviewer_name=short_name(review.reviewer.full_name),
        created_at=review.created_at,
    )


def find_public_profile(db: Session, provider_id: int):
    """A provider's profile, but only if it is complete (same rule as search)."""
    return (
        db.query(ProviderProfile)
        .join(User, User.id == ProviderProfile.user_id)
        .options(
            joinedload(ProviderProfile.user).joinedload(User.location),
            selectinload(ProviderProfile.skills).joinedload(ProviderSkill.skill),
            selectinload(ProviderProfile.availability),
        )
        .filter(
            ProviderProfile.user_id == provider_id,
            User.role == UserRole.PROVIDER,
            User.location_id.isnot(None),
            ProviderProfile.description.isnot(None),
            ProviderProfile.description != "",
            ProviderProfile.skills.any(),
        )
        .first()
    )


def list_provider_reviews(db: Session, provider_id: int, page: int, page_size: int, limit=None):
    rows = (
        db.query(Review)
        .options(
            joinedload(Review.service_request).joinedload(ServiceRequest.skill),
            joinedload(Review.reviewer),
        )
        .filter(Review.provider_id == provider_id)
        .order_by(Review.id.desc())
        .offset((page - 1) * page_size)
        .limit(limit or page_size)
        .all()
    )
    return [public_review_out(row) for row in rows]


def build_public_profile(card, profile, breakdown, reviews, completed_jobs) -> sp.ProviderPublicOut:
    return sp.ProviderPublicOut(
        **card.model_dump(),
        description=profile.description,
        qualification=profile.qualification,
        completed_jobs=completed_jobs,
        rating_breakdown=breakdown,
        recent_reviews=reviews,
    )


def public_provider_profile(db: Session, provider_id: int):
    profile = find_public_profile(db, provider_id)
    if profile is None:
        return None
    average, count = (
        db.query(func.avg(Review.rating), func.count(Review.id))
        .filter(Review.provider_id == provider_id)
        .one()
    )
    breakdown = breakdown_from_rows(
        db.query(Review.rating, func.count(Review.id))
        .filter(Review.provider_id == provider_id)
        .group_by(Review.rating)
        .all()
    )
    completed = (
        db.query(func.count(ServiceRequest.id))
        .filter(
            ServiceRequest.provider_id == provider_id,
            ServiceRequest.status == RequestStatus.COMPLETED,
        )
        .scalar()
        or 0
    )
    reviews = list_provider_reviews(db, provider_id, 1, RECENT_REVIEWS)
    card = provider_card(profile, average, count)
    return build_public_profile(card, profile, breakdown, reviews, int(completed))
