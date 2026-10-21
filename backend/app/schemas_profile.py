"""Step 12: public provider profile with ratings and recent reviews."""

from datetime import datetime
from typing import Optional

from app.schemas import ProviderCardOut
from pydantic import BaseModel


class PublicReviewOut(BaseModel):
    id: int
    rating: int
    comment: Optional[str] = None
    skill_name: str
    reviewer_name: str  # "Meera S." (first name + last initial only)
    created_at: datetime  # UTC


class RatingBreakdown(BaseModel):
    five: int = 0
    four: int = 0
    three: int = 0
    two: int = 0
    one: int = 0


class ProviderPublicOut(ProviderCardOut):
    """Everything a customer may see before sending a request. No email, no phone."""

    description: Optional[str] = None
    qualification: Optional[str] = None
    completed_jobs: int = 0
    rating_breakdown: RatingBreakdown
    recent_reviews: list[PublicReviewOut] = []
