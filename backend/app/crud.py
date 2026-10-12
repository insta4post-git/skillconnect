from string import capwords

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager

from app import schemas
from app.models import (
    Availability,
    Category,
    Location,
    ProviderProfile,
    ProviderSkill,
    Skill,
    User,
    UserRole,
)
from app.security import hash_password


# ------------------------------------------------------------ users (Step 3)


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower().strip()).first()


def create_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    password: str,
    role: UserRole,
    phone: str | None = None,
) -> User:
    user = User(
        full_name=full_name.strip(),
        email=email.lower().strip(),
        password_hash=hash_password(password),
        role=role,
        phone=phone.strip() if phone else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ------------------------------------------------- locations (Step 4)


def get_or_create_location(
    db: Session, *, city: str, area: str | None = None, pincode: str | None = None
) -> Location:
    """Reuse an existing city/area/pincode row, or create it."""
    city = capwords(city.strip())
    area = capwords(area.strip()) if area else None
    pincode = pincode.strip() if pincode else None

    query = db.query(Location).filter(Location.city == city)
    query = query.filter(Location.area == area if area else Location.area.is_(None))
    query = query.filter(
        Location.pincode == pincode if pincode else Location.pincode.is_(None)
    )
    location = query.first()
    if location is None:
        location = Location(city=city, area=area, pincode=pincode)
        db.add(location)
        db.flush()  # gives the new row an id before we use it
    return location


# -------------------------------------------------- user profile (Step 4)


def update_user_profile(
    db: Session, user: User, data: schemas.UserProfileUpdate
) -> User:
    user.full_name = data.full_name
    user.phone = data.phone
    user.bio = data.bio
    if data.location is None:
        user.location_id = None
    else:
        location = get_or_create_location(
            db,
            city=data.location.city,
            area=data.location.area,
            pincode=data.location.pincode,
        )
        user.location_id = location.id
    db.commit()
    db.refresh(user)
    return user


# ------------------------------------------ skill search and add (Step 5)

MAX_CUSTOM_SKILLS_PER_USER = 5


def escape_like(text: str) -> str:
    """Make % and _ typed by the user match literally inside a LIKE search."""
    return text.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def search_skills(
    db: Session, *, q: str | None, category_id: int | None, limit: int
) -> list[Skill]:
    """Skills whose name OR category name contains q, optionally inside one category."""
    query = db.query(Skill).join(Skill.category).options(contains_eager(Skill.category))
    if category_id is not None:
        query = query.filter(Skill.category_id == category_id)
    q = (q or "").strip()
    if q:
        pattern = f"%{escape_like(q)}%"
        query = query.filter(
            or_(
                Skill.name.ilike(pattern, escape="!"),
                Category.name.ilike(pattern, escape="!"),
            )
        )
    return query.order_by(Category.name, Skill.name).limit(limit).all()


def get_or_create_custom_skill(
    db: Session, *, user: User, category: Category, name: str
) -> tuple[Skill, bool]:
    """Return (skill, created). If a skill with this name already exists
    (any capitalisation) it is returned as it is, in its own category."""
    name = " ".join(name.split())  # collapse extra spaces
    existing = db.query(Skill).filter(func.lower(Skill.name) == name.lower()).first()
    if existing:
        return existing, False

    added_so_far = db.query(Skill).filter(Skill.created_by_id == user.id).count()
    if added_so_far >= MAX_CUSTOM_SKILLS_PER_USER:
        raise ValueError(
            f"You can add at most {MAX_CUSTOM_SKILLS_PER_USER} new skills. "
            "Please choose from the existing list."
        )

    skill = Skill(category_id=category.id, name=name, created_by_id=user.id)
    db.add(skill)
    try:
        db.commit()
    except IntegrityError:  # someone added the same name a moment ago
        db.rollback()
        existing = (
            db.query(Skill).filter(func.lower(Skill.name) == name.lower()).first()
        )
        if existing:
            return existing, False
        raise
    db.refresh(skill)
    return skill, True


# --------------------------------------------- provider profile (Step 4)


def upsert_provider_profile(
    db: Session, user: User, data: schemas.ProviderProfileIn
) -> ProviderProfile:
    """Create the provider profile the first time, update it afterwards."""
    profile = user.provider_profile
    if profile is None:
        profile = ProviderProfile(user_id=user.id)
        db.add(profile)
    profile.description = data.description
    profile.experience_years = data.experience_years
    profile.qualification = data.qualification
    profile.working_area = data.working_area
    profile.service_mode = data.service_mode
    profile.pricing_info = data.pricing_info
    profile.availability_notes = data.availability_notes
    db.commit()
    db.refresh(user)
    return user.provider_profile


def set_provider_skills(
    db: Session, profile: ProviderProfile, skill_ids: list[int]
) -> None:
    """Make the provider's skills exactly match skill_ids."""
    wanted = list(dict.fromkeys(skill_ids))  # remove duplicates, keep order
    found = set()
    if wanted:
        found = {
            row.id for row in db.query(Skill.id).filter(Skill.id.in_(wanted)).all()
        }
    missing = [skill_id for skill_id in wanted if skill_id not in found]
    if missing:
        raise ValueError(f"These skill ids do not exist: {missing}")

    current = {link.skill_id: link for link in profile.skills}
    for skill_id, link in current.items():
        if skill_id not in found:
            profile.skills.remove(link)  # delete-orphan removes the row
    for skill_id in wanted:
        if skill_id not in current:
            profile.skills.append(ProviderSkill(skill_id=skill_id))
    db.commit()
    db.refresh(profile)


def set_provider_availability(
    db: Session, profile: ProviderProfile, slots: list[schemas.AvailabilitySlotIn]
) -> None:
    """Replace all weekly availability slots."""
    profile.availability = [
        Availability(
            day_of_week=slot.day_of_week,
            start_time=slot.start_time,
            end_time=slot.end_time,
        )
        for slot in slots
    ]
    db.commit()
    db.refresh(profile)
