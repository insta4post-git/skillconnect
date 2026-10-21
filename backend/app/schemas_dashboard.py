"""Response/request models for Step 11 (dashboards, reviews, admin panel)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models import RequestServiceMode, RequestStatus, UserRole, WeekDay
from app.schemas import PartyOut, RequestOut

MAX_REVIEW_COMMENT = 1000


class StatusCounts(BaseModel):
    pending: int = 0
    accepted: int = 0
    rejected: int = 0
    cancelled: int = 0
    completed: int = 0
    total: int = 0


class DashboardProfile(BaseModel):
    id: int
    full_name: str
    photo_url: Optional[str] = None
    city: Optional[str] = None
    area: Optional[str] = None


# ---------------------------------------------------------------- reviews


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=MAX_REVIEW_COMMENT)

    @field_validator("comment")
    @classmethod
    def blank_comment_is_none(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None


class ReviewOut(BaseModel):
    id: int
    request_id: int
    rating: int
    comment: Optional[str] = None
    skill_name: str
    other_party: PartyOut  # customer sees the provider; provider sees the customer
    created_at: datetime


# ---------------------------------------------------------------- dashboards


class CustomerDashboardOut(BaseModel):
    profile: DashboardProfile
    requests: StatusCounts  # requests I sent
    recent_requests: list[RequestOut]  # newest 5, any status
    accepted_services: list[RequestOut]  # newest 5 ACCEPTED (contact details visible)
    conversations: int  # requests that have messages
    reviews_given: int
    reviews_pending: int  # COMPLETED requests I have not reviewed yet


class ProfileChecklist(BaseModel):
    has_location: bool
    has_description: bool
    has_skills: bool
    has_availability: bool
    visible_in_search: bool  # location + description + at least one skill


class ProviderDashboardOut(BaseModel):
    profile: DashboardProfile
    checklist: ProfileChecklist
    requests: StatusCounts  # requests I received
    incoming_requests: list[RequestOut]  # newest 5 PENDING
    accepted_jobs: list[RequestOut]  # newest 5 ACCEPTED (contact details visible)
    conversations: int
    skills_count: int
    available_days: list[WeekDay]
    avg_rating: Optional[float] = None
    review_count: int = 0


class UserCounts(BaseModel):
    total: int = 0
    customers: int = 0
    providers: int = 0
    admins: int = 0


class AdminDashboardOut(BaseModel):
    users: UserCounts
    new_users_7d: int
    skills_total: int
    custom_skills: int  # added by providers (not from the seed list)
    categories: int
    requests: StatusCounts
    requests_7d: int
    messages_total: int
    reviews_total: int
    avg_rating: Optional[float] = None


# ---------------------------------------------------------------- admin lists


class AdminUserOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    role: UserRole
    city: Optional[str] = None
    created_at: datetime


class AdminProviderOut(AdminUserOut):
    skills_count: int = 0
    avg_rating: Optional[float] = None
    review_count: int = 0
    requests_received: int = 0


class AdminRequestOut(BaseModel):
    id: int
    status: RequestStatus
    service_mode: RequestServiceMode
    customer_id: int
    customer_name: str
    provider_id: int
    provider_name: str
    skill_name: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class AdminSkillOut(BaseModel):
    id: int
    name: str
    category: str
    official: bool  # True = from the seed list, False = added by a provider
    added_by: Optional[str] = None
    providers_count: int = 0
    requests_count: int = 0
