from datetime import date, datetime, time, timedelta
from decimal import Decimal
from string import capwords

from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager, joinedload, selectinload

from app import schemas
from app.models import (
    Availability,
    Category,
    Location,
    Message,
    ProviderProfile,
    ProviderSkill,
    RequestServiceMode,
    RequestStatus,
    Review,
    ServiceMode,
    ServiceRequest,
    Skill,
    User,
    UserRole,
    WeekDay,
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


# ------------------------------------------------ search and discovery (Step 6)

DAY_ORDER = {day: index for index, day in enumerate(WeekDay)}
MAX_SEARCH_WORDS = 5
# Words people type in a sentence like "I need a plumber near me" that are not skills
SEARCH_STOPWORDS = {
    "need", "want", "looking", "find", "hire", "get", "for", "near", "nearby",
    "me", "my", "the", "and", "with", "in", "at", "to", "of", "an", "is",
    "someone", "who", "any", "good", "best",
}


def search_words(q: str | None) -> list[str]:
    """Split a search sentence into useful lowercase words."""
    words = []
    for raw in (q or "").lower().split():
        word = raw.strip(".,!?;:()\"'")
        if len(word) >= 2 and word not in SEARCH_STOPWORDS:
            words.append(word)
    return words[:MAX_SEARCH_WORDS]


def search_providers(
    db: Session,
    *,
    q: str | None = None,
    skill_id: int | None = None,
    category_id: int | None = None,
    city: str | None = None,
    area: str | None = None,
    pincode: str | None = None,
    service_mode: ServiceMode | None = None,
    day: WeekDay | None = None,
    at_time=None,
    min_rating: float | None = None,
    sort: str = "rating",
    near_location: Location | None = None,
    page: int = 1,
    page_size: int = 10,
):
    """Return (rows, total). Each row is (ProviderProfile, avg_rating, review_count).

    Only complete profiles are listed: the user has a location, the profile has a
    description and at least one skill (the same rule as is_complete).
    """
    rating = (
        db.query(
            Review.provider_id.label("provider_id"),
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("review_count"),
        )
        .group_by(Review.provider_id)
        .subquery()
    )
    avg_col = rating.c.avg_rating
    count_col = rating.c.review_count

    base = (
        db.query(ProviderProfile, avg_col, count_col)
        .join(User, ProviderProfile.user_id == User.id)
        .join(Location, User.location_id == Location.id)
        .outerjoin(rating, rating.c.provider_id == User.id)
        .filter(
            User.role == UserRole.PROVIDER,
            ProviderProfile.description.isnot(None),
            ProviderProfile.skills.any(),
        )
    )

    # --- skill / category / free text
    if skill_id is not None:
        base = base.filter(ProviderProfile.skills.any(ProviderSkill.skill_id == skill_id))
    if category_id is not None:
        base = base.filter(
            ProviderProfile.skills.any(
                ProviderSkill.skill.has(Skill.category_id == category_id)
            )
        )
    for word in search_words(q):  # every word must match somewhere
        pattern = f"%{escape_like(word)}%"
        base = base.filter(
            or_(
                User.full_name.ilike(pattern, escape="!"),
                ProviderProfile.skills.any(
                    ProviderSkill.skill.has(Skill.name.ilike(pattern, escape="!"))
                ),
                ProviderProfile.skills.any(
                    ProviderSkill.skill.has(
                        Skill.category.has(Category.name.ilike(pattern, escape="!"))
                    )
                ),
            )
        )

    # --- location (typed filters win over "near me")
    if not city and near_location is not None:
        city = near_location.city
    if city:
        base = base.filter(func.lower(Location.city) == city.strip().lower())
    if area:
        base = base.filter(Location.area.ilike(f"%{escape_like(area.strip())}%", escape="!"))
    if pincode:
        base = base.filter(Location.pincode == pincode)

    # --- service type: a provider with BOTH matches either kind of request
    if service_mode is not None:
        base = base.filter(
            ProviderProfile.service_mode.in_([service_mode, ServiceMode.BOTH])
        )

    # --- availability on a weekday (and optionally at a time of day)
    if day is not None:
        conditions = [Availability.is_active == 1, Availability.day_of_week == day]
        if at_time is not None:
            conditions += [Availability.start_time <= at_time, Availability.end_time > at_time]
        base = base.filter(ProviderProfile.availability.any(and_(*conditions)))

    # --- rating (providers with no reviews are left out)
    if min_rating is not None:
        base = base.filter(avg_col >= min_rating)

    total = base.with_entities(func.count(ProviderProfile.id)).scalar() or 0

    # --- ordering
    rating_order = [func.coalesce(avg_col, 0).desc(), func.coalesce(count_col, 0).desc()]
    if sort == "experience":
        keys = [func.coalesce(ProviderProfile.experience_years, 0).desc(), *rating_order]
    elif sort == "newest":
        keys = [ProviderProfile.created_at.desc()]
    else:
        keys = rating_order
    if near_location is not None:  # same pincode first, then same area, then the rest
        whens = []
        if near_location.pincode:
            whens.append((Location.pincode == near_location.pincode, 0))
        if near_location.area:
            whens.append((func.lower(Location.area) == near_location.area.lower(), 1))
        if whens:
            keys = [case(*whens, else_=2), *keys]
    keys += [User.full_name, ProviderProfile.id]

    rows = (
        base.options(
            contains_eager(ProviderProfile.user).contains_eager(User.location),
            selectinload(ProviderProfile.skills).selectinload(ProviderSkill.skill),
            selectinload(ProviderProfile.availability),
        )
        .order_by(*keys)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total


def provider_card(profile, avg_rating, review_count) -> schemas.ProviderCardOut:
    """Public search result. It never contains the provider's email or phone."""
    user = profile.user
    summary = profile.description or ""
    if len(summary) > 160:
        summary = summary[:157].rstrip() + "..."
    skills = sorted((link.skill for link in profile.skills), key=lambda s: s.name)
    days = sorted(
        {slot.day_of_week for slot in profile.availability if slot.is_active},
        key=lambda d: DAY_ORDER[d],
    )
    return schemas.ProviderCardOut.model_validate(
        {
            "user_id": user.id,
            "full_name": user.full_name,
            "photo_url": user.photo_url,
            "location": user.location,
            "summary": summary,
            "experience_years": profile.experience_years,
            "working_area": profile.working_area,
            "service_mode": profile.service_mode,
            "pricing_info": profile.pricing_info,
            "skills": skills,
            "available_days": days,
            "avg_rating": round(float(avg_rating), 1) if avg_rating is not None else None,
            "review_count": int(review_count or 0),
        },
        from_attributes=True,
    )


# ------------------------------------- regular / long-term requests (Step 7)

MAX_PENDING_REQUESTS_PER_CUSTOMER = 10


def join_days(days) -> str:
    """[MONDAY, FRIDAY] -> "MONDAY,FRIDAY" (stored in one column)."""
    return ",".join(day.value for day in days)


def split_days(text: str | None) -> list[WeekDay]:
    return [WeekDay(part) for part in text.split(",") if part] if text else []


def session_hours(start: time, end: time) -> float:
    minutes = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
    return round(minutes / 60, 2)


def count_pending_requests(db: Session, customer: User) -> int:
    return (
        db.query(ServiceRequest)
        .filter(
            ServiceRequest.customer_id == customer.id,
            ServiceRequest.status == RequestStatus.PENDING,
        )
        .count()
    )


def find_overlapping_regular_request(
    db: Session, *, customer: User, provider_id: int, skill_id: int, start, end
) -> ServiceRequest | None:
    """An open (pending or accepted) request for the same provider and skill
    whose dates overlap the new one."""
    return (
        db.query(ServiceRequest)
        .filter(
            ServiceRequest.customer_id == customer.id,
            ServiceRequest.provider_id == provider_id,
            ServiceRequest.skill_id == skill_id,
            ServiceRequest.service_mode == RequestServiceMode.REGULAR,
            ServiceRequest.status.in_([RequestStatus.PENDING, RequestStatus.ACCEPTED]),
            ServiceRequest.start_date <= end,
            ServiceRequest.end_date >= start,
        )
        .first()
    )


def resolve_request_location(
    db: Session, customer: User, location_in: schemas.LocationIn | None
) -> Location:
    """The location typed in the request, or else the one saved in the profile."""
    if location_in is not None:
        return get_or_create_location(
            db,
            city=location_in.city,
            area=location_in.area,
            pincode=location_in.pincode,
        )
    return customer.location  # the router already checked it exists


def create_regular_request(
    db: Session,
    *,
    customer: User,
    provider: User,
    data: schemas.RegularRequestCreate,
) -> ServiceRequest:
    location = resolve_request_location(db, customer, data.location)
    request = ServiceRequest(
        customer_id=customer.id,
        provider_id=provider.id,
        skill_id=data.skill_id,
        location_id=location.id,
        service_mode=RequestServiceMode.REGULAR,
        start_date=data.start_date,
        end_date=data.end_date,
        working_days=join_days(data.working_days),
        start_time=data.start_time,
        end_time=data.end_time,
        duration_hours=Decimal(str(session_hours(data.start_time, data.end_time))),
        address_details=data.address_details,
        message=data.details,
        status=RequestStatus.PENDING,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def find_same_day_short_term_request(
    db: Session, *, customer: User, provider_id: int, skill_id: int, day: date
) -> ServiceRequest | None:
    """An open (pending or accepted) short-term request for the same provider
    and skill on the same calendar day."""
    day_start = datetime.combine(day, time.min)
    return (
        db.query(ServiceRequest)
        .filter(
            ServiceRequest.customer_id == customer.id,
            ServiceRequest.provider_id == provider_id,
            ServiceRequest.skill_id == skill_id,
            ServiceRequest.service_mode == RequestServiceMode.NON_REGULAR,
            ServiceRequest.status.in_([RequestStatus.PENDING, RequestStatus.ACCEPTED]),
            ServiceRequest.scheduled_at >= day_start,
            ServiceRequest.scheduled_at < day_start + timedelta(days=1),
        )
        .first()
    )


def create_short_term_request(
    db: Session,
    *,
    customer: User,
    provider: User,
    data: schemas.ShortTermRequestCreate,
) -> ServiceRequest:
    location = resolve_request_location(db, customer, data.location)
    request = ServiceRequest(
        customer_id=customer.id,
        provider_id=provider.id,
        skill_id=data.skill_id,
        location_id=location.id,
        service_mode=RequestServiceMode.NON_REGULAR,
        scheduled_at=datetime.combine(data.service_date, data.start_time),
        duration_hours=Decimal(str(data.duration_hours)),
        address_details=data.address_details,
        message=data.details,
        status=RequestStatus.PENDING,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def _request_query(db: Session):
    return db.query(ServiceRequest).options(
        joinedload(ServiceRequest.customer),
        joinedload(ServiceRequest.provider),
        joinedload(ServiceRequest.skill),
        joinedload(ServiceRequest.location),
    )


def list_my_requests(
    db: Session,
    user: User,
    status: RequestStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[ServiceRequest]:
    """Customers see the requests they sent, providers the ones they received."""
    column = (
        ServiceRequest.customer_id
        if user.role == UserRole.CUSTOMER
        else ServiceRequest.provider_id
    )
    query = _request_query(db).filter(column == user.id)
    if status is not None:
        query = query.filter(ServiceRequest.status == status)
    return (
        query.order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def get_request_for_party(
    db: Session, request_id: int, user: User
) -> ServiceRequest | None:
    """The request, but only if this user is its customer or its provider."""
    return (
        _request_query(db)
        .filter(
            ServiceRequest.id == request_id,
            or_(
                ServiceRequest.customer_id == user.id,
                ServiceRequest.provider_id == user.id,
            ),
        )
        .first()
    )


def party_dict(user, show_contact: bool) -> dict:
    """Name and photo always; email and phone only when show_contact is True."""
    return {
        "id": user.id,
        "full_name": user.full_name,
        "photo_url": user.photo_url,
        "email": user.email if show_contact else None,
        "phone": user.phone if show_contact else None,
    }


def request_out(request) -> schemas.RequestOut:
    """Build the API response. No email or phone is included."""
    days = split_days(request.working_days)
    total = None
    if request.start_date and request.end_date and days:
        total = schemas.count_sessions(request.start_date, request.end_date, days)
    show_contact = request.status in (RequestStatus.ACCEPTED, RequestStatus.COMPLETED)
    return schemas.RequestOut.model_validate(
        {
            "id": request.id,
            "status": request.status,
            "service_mode": request.service_mode,
            "customer": party_dict(request.customer, show_contact),
            "provider": party_dict(request.provider, show_contact),
            "skill": request.skill,
            "scheduled_at": request.scheduled_at,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "working_days": days,
            "start_time": request.start_time,
            "end_time": request.end_time,
            "session_hours": (
                float(request.duration_hours)
                if request.duration_hours is not None
                else None
            ),
            "total_sessions": total,
            "location": request.location,
            "address_details": request.address_details,
            "details": request.message,
            "created_at": request.created_at,
            "updated_at": request.updated_at,
        },
        from_attributes=True,
    )


# ----------------------------------------- request status changes (Step 9)


class RequestActionError(Exception):
    """A status change that is not allowed. The router turns it into an HTTP error."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# action -> (who may do it, statuses it can start from, new status, past tense)
REQUEST_ACTIONS = {
    "accept": ("provider", (RequestStatus.PENDING,), RequestStatus.ACCEPTED, "accepted"),
    "reject": ("provider", (RequestStatus.PENDING,), RequestStatus.REJECTED, "rejected"),
    "complete": ("provider", (RequestStatus.ACCEPTED,), RequestStatus.COMPLETED, "completed"),
    "cancel": (
        "customer",
        (RequestStatus.PENDING, RequestStatus.ACCEPTED),
        RequestStatus.CANCELLED,
        "cancelled",
    ),
}


def request_timing(request, now) -> tuple[bool, bool]:
    """(has_started, can_still_start) for a short-term or long-term request."""
    if request.scheduled_at is not None:  # short-term: one start time
        return request.scheduled_at <= now, request.scheduled_at > now
    if request.start_date is not None and request.end_date is not None:  # long-term
        today = now.date()
        return request.start_date <= today, request.end_date >= today
    return True, True


def check_action(action: str, request, user_id: int, now) -> None:
    """Raise RequestActionError unless this user may do this action right now."""
    side, allowed_from, _new_status, past = REQUEST_ACTIONS[action]
    owner_id = request.provider_id if side == "provider" else request.customer_id
    if user_id != owner_id:
        raise RequestActionError(403, f"Only the {side} can {action} a request.")
    if request.status not in allowed_from:
        allowed = " or ".join(status.value for status in allowed_from)
        raise RequestActionError(
            409,
            f"A {request.status.value} request cannot be {past}. "
            f"Only {allowed} requests can be {past}.",
        )
    has_started, can_still_start = request_timing(request, now)
    if action == "accept" and not can_still_start:
        raise RequestActionError(
            400, "This request is out of date: the requested time has already passed."
        )
    if action == "complete" and not has_started:
        raise RequestActionError(
            400, "You can mark a request completed only after the service has started."
        )


def apply_action(db: Session, request: ServiceRequest, user_id: int, action: str) -> None:
    """Check the rules, then change the status in one atomic UPDATE.

    The UPDATE only matches if the status is still one the action may start from,
    so two people clicking at the same moment cannot both win."""
    check_action(action, request, user_id, datetime.now())
    _side, allowed_from, new_status, _past = REQUEST_ACTIONS[action]
    changed = (
        db.query(ServiceRequest)
        .filter(
            ServiceRequest.id == request.id,
            ServiceRequest.status.in_(allowed_from),
        )
        .update(
            {"status": new_status, "updated_at": datetime.utcnow()},
            synchronize_session=False,
        )
    )
    db.commit()
    if changed == 0:
        raise RequestActionError(
            409, "This request was just changed by someone else. Reload and try again."
        )


# ------------------------------------------------------- messaging (Step 10)

MAX_MESSAGES_PER_REQUEST = 300
# Chat is open only while the request is still alive. After it is closed,
# completed, rejected or cancelled, the history stays readable but read-only.
MESSAGING_OPEN_STATUSES = (RequestStatus.PENDING, RequestStatus.ACCEPTED)


def can_send_message(request) -> bool:
    return request.status in MESSAGING_OPEN_STATUSES


def message_out(message, user_id: int) -> schemas.MessageOut:
    return schemas.MessageOut(
        id=message.id,
        request_id=message.service_request_id,
        sender_id=message.sender_id,
        sender_name=message.sender.full_name,
        is_mine=message.sender_id == user_id,
        body=message.body,
        created_at=message.created_at,
    )


def list_messages(
    db: Session, request_id: int, after_id: int = 0, limit: int = MAX_MESSAGES_PER_REQUEST
) -> list[Message]:
    """Oldest first. Pass after_id=<last id you have> to get only newer ones."""
    return (
        db.query(Message)
        .options(joinedload(Message.sender))
        .filter(Message.service_request_id == request_id, Message.id > after_id)
        .order_by(Message.id.asc())
        .limit(limit)
        .all()
    )


def count_messages(db: Session, request_id: int) -> int:
    return (
        db.query(func.count(Message.id))
        .filter(Message.service_request_id == request_id)
        .scalar()
        or 0
    )


def create_message(db: Session, request_id: int, sender: User, body: str) -> Message:
    message = Message(service_request_id=request_id, sender_id=sender.id, body=body)
    db.add(message)
    db.commit()
    db.refresh(message)
    message.sender = sender
    return message


def list_inbox(db: Session, user: User, page: int = 1, page_size: int = 20) -> list[schemas.InboxItemOut]:
    """One row per request that has messages, most recent conversation first."""
    stats = (
        db.query(
            Message.service_request_id.label("rid"),
            func.max(Message.id).label("last_id"),
            func.count(Message.id).label("n"),
        )
        .group_by(Message.service_request_id)
        .subquery()
    )
    rows = (
        db.query(ServiceRequest, stats.c.last_id, stats.c.n)
        .join(stats, stats.c.rid == ServiceRequest.id)
        .options(
            joinedload(ServiceRequest.customer),
            joinedload(ServiceRequest.provider),
            joinedload(ServiceRequest.skill),
        )
        .filter(
            or_(
                ServiceRequest.customer_id == user.id,
                ServiceRequest.provider_id == user.id,
            )
        )
        .order_by(stats.c.last_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    last_ids = [row[1] for row in rows]
    last_messages = (
        {m.id: m for m in db.query(Message).filter(Message.id.in_(last_ids)).all()}
        if last_ids
        else {}
    )
    return [inbox_item(request, count, last_messages[last_id], user.id) for request, last_id, count in rows]


def inbox_item(request, count: int, last, user_id: int) -> schemas.InboxItemOut:
    other = request.provider if request.customer_id == user_id else request.customer
    text = last.body if len(last.body) <= 100 else last.body[:97] + "..."
    return schemas.InboxItemOut(
        request_id=request.id,
        request_status=request.status,
        skill_name=request.skill.name,
        other_party=schemas.PartyOut(id=other.id, full_name=other.full_name, photo_url=other.photo_url),
        message_count=count,
        last_message=text,
        last_message_at=last.created_at,
        last_message_is_mine=last.sender_id == user_id,
    )
