from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app import crud_profile, schemas_profile as sp
from app.database import get_db

# Public (no login), like search. It must be included AFTER providers.router in
# main.py, because that one owns the fixed path /api/providers/me.
router = APIRouter(prefix="/api/providers", tags=["Provider profile (public)"])


def not_found():
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found."
    )


@router.get("/{provider_id}", response_model=sp.ProviderPublicOut)
def provider_public_profile(
    provider_id: int = Path(ge=1), db: Session = Depends(get_db)
):
    """Public profile: details, average rating, number of reviews, rating split, recent reviews."""
    result = crud_profile.public_provider_profile(db, provider_id)
    if result is None:  # no such provider, or the profile is not complete yet
        raise not_found()
    return result


@router.get("/{provider_id}/reviews", response_model=list[sp.PublicReviewOut])
def provider_reviews(
    provider_id: int = Path(ge=1),
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """All reviews of one provider, newest first."""
    if crud_profile.find_public_profile(db, provider_id) is None:
        raise not_found()
    return crud_profile.list_provider_reviews(db, provider_id, page, page_size)
