from datetime import date, datetime, time, timedelta
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models import (
    RequestServiceMode,
    RequestStatus,
    ServiceMode,
    UserRole,
    WeekDay,
)


def _blank_to_none(value):
    """Turn empty or whitespace-only text from a form into None."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


# ---------------------------------------------------------------- auth (Step 3)


class UserRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: Literal["CUSTOMER", "PROVIDER"]
    phone: Optional[str] = Field(default=None, max_length=20)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password is too long (max 72 bytes).")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    full_name: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: UserRole
    phone: Optional[str] = None
    created_at: datetime


class MessageResponse(BaseModel):
    message: str


# ------------------------------------------------- user profile (Step 4)


class LocationIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    city: str = Field(min_length=2, max_length=100)
    area: Optional[str] = Field(default=None, max_length=100)
    pincode: Optional[str] = Field(default=None, pattern=r"^\d{6}$")

    @field_validator("area", "pincode", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        return _blank_to_none(value)


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    city: str
    area: Optional[str] = None
    pincode: Optional[str] = None


class UserProfileUpdate(BaseModel):
    """Send ALL fields every time. Anything you leave out is cleared."""

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=120)
    phone: Optional[str] = Field(default=None, pattern=r"^\+?[0-9 \-]{7,20}$")
    bio: Optional[str] = Field(default=None, max_length=1000)
    location: Optional[LocationIn] = None

    @field_validator("phone", "bio", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        return _blank_to_none(value)


class UserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    role: UserRole
    bio: Optional[str] = None
    photo_url: Optional[str] = None
    location: Optional[LocationOut] = None
    created_at: datetime


# ------------------------------------------- services catalog (Step 4)


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category_id: int


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    skills: list[SkillOut] = []


# ------------------------------------------ skill search and add (Step 5)


class SkillDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category_id: int
    category_name: str
    is_custom: bool  # True = added by a provider, False = official skill


class SkillCreate(BaseModel):
    """A provider suggests a new skill inside an existing category."""

    model_config = ConfigDict(str_strip_whitespace=True)

    category_id: int = Field(ge=1)
    # letters (any language), digits, spaces and & / . ' + -
    name: str = Field(min_length=2, max_length=60, pattern=r"^[\w][\w &/.'+\-]*$")


# ------------------------------------------------ provider profile (Step 4)


class ProviderProfileIn(BaseModel):
    """Send ALL fields every time. Anything you leave out is cleared."""

    model_config = ConfigDict(str_strip_whitespace=True)

    description: str = Field(min_length=10, max_length=2000)
    experience_years: Optional[int] = Field(default=None, ge=0, le=60)
    qualification: Optional[str] = Field(default=None, max_length=255)
    working_area: Optional[str] = Field(default=None, max_length=255)
    service_mode: ServiceMode = ServiceMode.BOTH
    pricing_info: Optional[str] = Field(default=None, max_length=500)
    availability_notes: Optional[str] = Field(default=None, max_length=255)

    @field_validator(
        "qualification",
        "working_area",
        "pricing_info",
        "availability_notes",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value):
        return _blank_to_none(value)


class ProviderSkillsUpdate(BaseModel):
    skill_ids: list[int] = Field(max_length=15)


class AvailabilitySlotIn(BaseModel):
    day_of_week: WeekDay
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class AvailabilityUpdate(BaseModel):
    slots: list[AvailabilitySlotIn] = Field(max_length=21)

    @model_validator(mode="after")
    def no_overlaps(self):
        by_day: dict[WeekDay, list[AvailabilitySlotIn]] = {}
        for slot in self.slots:
            by_day.setdefault(slot.day_of_week, []).append(slot)
        for day, day_slots in by_day.items():
            day_slots.sort(key=lambda s: s.start_time)
            for earlier, later in zip(day_slots, day_slots[1:]):
                if later.start_time < earlier.end_time:
                    raise ValueError(f"Overlapping time slots on {day.value}")
        return self


class AvailabilitySlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day_of_week: WeekDay
    start_time: time
    end_time: time


class ProviderProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    photo_url: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[LocationOut] = None
    description: Optional[str] = None
    experience_years: Optional[int] = None
    qualification: Optional[str] = None
    working_area: Optional[str] = None
    service_mode: ServiceMode
    pricing_info: Optional[str] = None
    availability_notes: Optional[str] = None
    skills: list[SkillOut] = []
    availability: list[AvailabilitySlotOut] = []
    is_complete: bool


# ------------------------------------------ search and discovery (Step 6)


class ProviderCardOut(BaseModel):
    """One search result. Public, so no email and no phone number."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str
    photo_url: Optional[str] = None
    location: Optional[LocationOut] = None
    summary: Optional[str] = None
    experience_years: Optional[int] = None
    working_area: Optional[str] = None
    service_mode: ServiceMode
    pricing_info: Optional[str] = None
    skills: list[SkillOut] = []
    available_days: list[WeekDay] = []
    avg_rating: Optional[float] = None
    review_count: int = 0


class ProviderSearchOut(BaseModel):
    total: int
    page: int
    page_size: int
    has_more: bool
    results: list[ProviderCardOut]


# ------------------------------------- regular / long-term requests (Step 7)

MAX_REQUEST_DAYS = 365
MAX_SESSION_HOURS = 12
WEEK_ORDER = {day: index for index, day in enumerate(WeekDay)}


def count_sessions(start: date, end: date, days) -> int:
    """How many working days fall between start and end (both included)."""
    wanted = {WEEK_ORDER[d] for d in days}
    total = 0
    current = start
    while current <= end:
        if current.weekday() in wanted:  # Monday = 0, same order as WeekDay
            total += 1
        current += timedelta(days=1)
    return total


class RegularRequestCreate(BaseModel):
    """A customer asks one provider for long-term, recurring work."""

    model_config = ConfigDict(str_strip_whitespace=True)

    provider_id: int = Field(ge=1)
    skill_id: int = Field(ge=1)
    start_date: date
    end_date: date
    working_days: list[WeekDay] = Field(min_length=1, max_length=7)
    start_time: time  # daily start, e.g. "17:00"
    end_time: time  # daily end, e.g. "18:30"
    # Leave out to use the location saved in your profile
    location: Optional[LocationIn] = None
    address_details: Optional[str] = Field(default=None, max_length=255)
    details: str = Field(min_length=10, max_length=1000)

    @field_validator("address_details", mode="before")
    @classmethod
    def blank_address_to_none(cls, value):
        return _blank_to_none(value)

    @field_validator("start_date")
    @classmethod
    def start_not_in_past(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("start_date cannot be in the past")
        return value

    @field_validator("working_days")
    @classmethod
    def unique_days_in_week_order(cls, value):
        return sorted(set(value), key=lambda d: WEEK_ORDER[d])

    @model_validator(mode="after")
    def check_dates_and_times(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.end_date - self.start_date).days > MAX_REQUEST_DAYS:
            raise ValueError("A request can cover at most 1 year")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        minutes = (self.end_time.hour * 60 + self.end_time.minute) - (
            self.start_time.hour * 60 + self.start_time.minute
        )
        if minutes > MAX_SESSION_HOURS * 60:
            raise ValueError(f"One session can be at most {MAX_SESSION_HOURS} hours")
        if count_sessions(self.start_date, self.end_date, self.working_days) == 0:
            raise ValueError(
                "None of the chosen working days fall between start_date and end_date"
            )
        return self


class PartyOut(BaseModel):
    """Name and photo only. No email or phone is shared at this stage."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    photo_url: Optional[str] = None


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: RequestStatus
    service_mode: RequestServiceMode
    customer: PartyOut
    provider: PartyOut
    skill: SkillOut
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    working_days: list[WeekDay] = []
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    session_hours: Optional[float] = None
    total_sessions: Optional[int] = None
    location: Optional[LocationOut] = None
    address_details: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime
