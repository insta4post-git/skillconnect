from datetime import datetime, time
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models import ServiceMode, UserRole, WeekDay


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
