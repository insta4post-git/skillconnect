import enum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    PROVIDER = "PROVIDER"
    ADMIN = "ADMIN"


class ServiceMode(str, enum.Enum):
    REGULAR = "REGULAR"
    NON_REGULAR = "NON_REGULAR"
    BOTH = "BOTH"


class RequestServiceMode(str, enum.Enum):
    REGULAR = "REGULAR"
    NON_REGULAR = "NON_REGULAR"


class RequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class WeekDay(str, enum.Enum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    phone = Column(String(20), nullable=True)
    # Step 4: profile fields shared by every user (customers and providers)
    bio = Column(Text, nullable=True)
    photo_url = Column(String(500), nullable=True)
    location_id = Column(
        Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    location = relationship("Location", back_populates="users")
    provider_profile = relationship(
        "ProviderProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    customer_requests = relationship(
        "ServiceRequest",
        back_populates="customer",
        foreign_keys="ServiceRequest.customer_id",
    )
    provider_requests = relationship(
        "ServiceRequest",
        back_populates="provider",
        foreign_keys="ServiceRequest.provider_id",
    )
    sent_messages = relationship("Message", back_populates="sender")
    reviews_written = relationship(
        "Review", back_populates="reviewer", foreign_keys="Review.reviewer_id"
    )
    reviews_received = relationship(
        "Review", back_populates="provider", foreign_keys="Review.provider_id"
    )


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("city", "area", "pincode", name="uq_location_city_area_pincode"),
    )

    id = Column(Integer, primary_key=True)
    city = Column(String(100), nullable=False, index=True)
    area = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    users = relationship("User", back_populates="location")
    providers = relationship("ProviderProfile", back_populates="location")
    requests = relationship("ServiceRequest", back_populates="location")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    skills = relationship("Skill", back_populates="category", order_by="Skill.name")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True)
    category_id = Column(
        Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    name = Column(String(80), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
    # Step 5: NULL = official skill (from seed_skills.py), otherwise the provider who added it
    created_by_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    category = relationship("Category", back_populates="skills")
    provider_links = relationship("ProviderSkill", back_populates="skill")
    requests = relationship("ServiceRequest", back_populates="skill")


class ProviderProfile(Base):
    __tablename__ = "provider_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    # Step 4: photo and location now live on the users table for everyone.
    # These two columns are unused for now and can be removed in Step 14.
    location_id = Column(
        Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    photo_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    experience_years = Column(Integer, nullable=True)
    service_mode = Column(Enum(ServiceMode), nullable=False, default=ServiceMode.BOTH)
    availability_notes = Column(String(255), nullable=True)
    # Step 4: extra provider details
    qualification = Column(String(255), nullable=True)
    working_area = Column(String(255), nullable=True)
    pricing_info = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "experience_years IS NULL OR experience_years >= 0",
            name="ck_provider_experience_years",
        ),
    )

    user = relationship("User", back_populates="provider_profile")
    location = relationship("Location", back_populates="providers")
    skills = relationship(
        "ProviderSkill", back_populates="provider_profile", cascade="all, delete-orphan"
    )
    availability = relationship(
        "Availability",
        back_populates="provider_profile",
        cascade="all, delete-orphan",
    )


class ProviderSkill(Base):
    __tablename__ = "provider_skills"
    __table_args__ = (
        UniqueConstraint("provider_profile_id", "skill_id", name="uq_provider_skill"),
    )

    id = Column(Integer, primary_key=True)
    provider_profile_id = Column(
        Integer,
        ForeignKey("provider_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    skill_id = Column(
        Integer, ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False
    )

    provider_profile = relationship("ProviderProfile", back_populates="skills")
    skill = relationship("Skill", back_populates="provider_links")


class Availability(Base):
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True)
    provider_profile_id = Column(
        Integer,
        ForeignKey("provider_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week = Column(Enum(WeekDay), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    provider_profile = relationship("ProviderProfile", back_populates="availability")


class ServiceRequest(Base):
    __tablename__ = "service_requests"
    __table_args__ = (
        CheckConstraint("customer_id <> provider_id", name="ck_request_not_self"),
        CheckConstraint(
            "duration_hours IS NULL OR duration_hours > 0",
            name="ck_request_duration_positive",
        ),
    )

    id = Column(Integer, primary_key=True)
    customer_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id = Column(
        Integer, ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False
    )
    location_id = Column(
        Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    service_mode = Column(Enum(RequestServiceMode), nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    duration_hours = Column(Numeric(5, 2), nullable=True)
    message = Column(Text, nullable=True)
    # Step 7: long-term (REGULAR) requests. NON_REGULAR requests leave these empty.
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    working_days = Column(String(80), nullable=True)  # e.g. "MONDAY,WEDNESDAY,FRIDAY"
    start_time = Column(Time, nullable=True)  # daily start
    end_time = Column(Time, nullable=True)  # daily end
    address_details = Column(String(255), nullable=True)  # flat / landmark, private
    status = Column(
        Enum(RequestStatus), nullable=False, default=RequestStatus.PENDING, index=True
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    customer = relationship(
        "User", back_populates="customer_requests", foreign_keys=[customer_id]
    )
    provider = relationship(
        "User", back_populates="provider_requests", foreign_keys=[provider_id]
    )
    skill = relationship("Skill", back_populates="requests")
    location = relationship("Location", back_populates="requests")
    messages = relationship(
        "Message", back_populates="service_request", cascade="all, delete-orphan"
    )
    review = relationship(
        "Review",
        back_populates="service_request",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    service_request_id = Column(
        Integer,
        ForeignKey("service_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    service_request = relationship("ServiceRequest", back_populates="messages")
    sender = relationship("User", back_populates="sent_messages")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating_range"),
    )

    id = Column(Integer, primary_key=True)
    service_request_id = Column(
        Integer,
        ForeignKey("service_requests.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    reviewer_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    service_request = relationship("ServiceRequest", back_populates="review")
    reviewer = relationship(
        "User", back_populates="reviews_written", foreign_keys=[reviewer_id]
    )
    provider = relationship(
        "User", back_populates="reviews_received", foreign_keys=[provider_id]
    )
