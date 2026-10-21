"""Database helpers for Step 11: dashboards, reviews and the admin panel."""

from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app import schemas
from app import schemas_dashboard as sd
from app.crud import DAY_ORDER, _request_query, escape_like, request_out
from app.models import (
    Category,
    Message,
    ProviderProfile,
    ProviderSkill,
    RequestStatus,
    Review,
    ServiceRequest,
    Skill,
    User,
    UserRole,
)

RECENT_LIMIT = 5


# ------------------------------------------------------------ small helpers


def counts_from_rows(rows) -> sd.StatusCounts:
    """rows = [(RequestStatus, how_many), ...]  ->  StatusCounts (missing = 0)."""
    data = {status.value.lower(): 0 for status in RequestStatus}
    for status, number in rows:
        data[status.value.lower()] = int(number)
    data["total"] = sum(data.values())
    return sd.StatusCounts(**data)


def rating_number(value) -> float | None:
    return None if value is None else round(float(value), 1)


def dashboard_profile(user: User) -> sd.DashboardProfile:
    location = user.location
    return sd.DashboardProfile(
        id=user.id,
        full_name=user.full_name,
        photo_url=user.photo_url,
        city=location.city if location else None,
        area=location.area if location else None,
    )


def count_requests_by_status(db: Session, *filters) -> sd.StatusCounts:
    rows = (
        db.query(ServiceRequest.status, func.count(ServiceRequest.id))
        .filter(*filters)
        .group_by(ServiceRequest.status)
        .all()
    )
    return counts_from_rows(rows)


def conversation_count(db: Session, user: User) -> int:
    """How many of my requests have at least one message."""
    return (
        db.query(func.count(func.distinct(Message.service_request_id)))
        .select_from(Message)
        .join(ServiceRequest, ServiceRequest.id == Message.service_request_id)
        .filter(
            or_(
                ServiceRequest.customer_id == user.id,
                ServiceRequest.provider_id == user.id,
            )
        )
        .scalar()
        or 0
    )


def recent_requests(db: Session, *filters, limit: int = RECENT_LIMIT) -> list[schemas.RequestOut]:
    rows = (
        _request_query(db)
        .filter(*filters)
        .order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc())
        .limit(limit)
        .all()
    )
    return [request_out(row) for row in rows]


# ---------------------------------------------------------------- dashboards


def customer_dashboard(db: Session, user: User) -> sd.CustomerDashboardOut:
    mine = ServiceRequest.customer_id == user.id
    reviewed_ids = select(Review.service_request_id)
    pending_reviews = (
        db.query(func.count(ServiceRequest.id))
        .filter(
            mine,
            ServiceRequest.status == RequestStatus.COMPLETED,
            ServiceRequest.id.notin_(reviewed_ids),
        )
        .scalar()
        or 0
    )
    given = db.query(func.count(Review.id)).filter(Review.reviewer_id == user.id).scalar() or 0
    return sd.CustomerDashboardOut(
        profile=dashboard_profile(user),
        requests=count_requests_by_status(db, mine),
        recent_requests=recent_requests(db, mine),
        accepted_services=recent_requests(db, mine, ServiceRequest.status == RequestStatus.ACCEPTED),
        conversations=conversation_count(db, user),
        reviews_given=given,
        reviews_pending=pending_reviews,
    )


def build_checklist(user: User, profile) -> sd.ProfileChecklist:
    has_location = user.location_id is not None
    has_description = bool(profile and profile.description and profile.description.strip())
    has_skills = bool(profile and profile.skills)
    has_availability = bool(profile and any(slot.is_active for slot in profile.availability))
    return sd.ProfileChecklist(
        has_location=has_location,
        has_description=has_description,
        has_skills=has_skills,
        has_availability=has_availability,
        visible_in_search=has_location and has_description and has_skills,
    )


def provider_dashboard(db: Session, user: User) -> sd.ProviderDashboardOut:
    mine = ServiceRequest.provider_id == user.id
    profile = user.provider_profile
    average, review_count = (
        db.query(func.avg(Review.rating), func.count(Review.id))
        .filter(Review.provider_id == user.id)
        .one()
    )
    days = []
    if profile:
        days = sorted(
            {slot.day_of_week for slot in profile.availability if slot.is_active},
            key=lambda day: DAY_ORDER[day],
        )
    return sd.ProviderDashboardOut(
        profile=dashboard_profile(user),
        checklist=build_checklist(user, profile),
        requests=count_requests_by_status(db, mine),
        incoming_requests=recent_requests(db, mine, ServiceRequest.status == RequestStatus.PENDING),
        accepted_jobs=recent_requests(db, mine, ServiceRequest.status == RequestStatus.ACCEPTED),
        conversations=conversation_count(db, user),
        skills_count=len(profile.skills) if profile else 0,
        available_days=days,
        avg_rating=rating_number(average),
        review_count=int(review_count or 0),
    )


def admin_dashboard(db: Session) -> sd.AdminDashboardOut:
    week_ago = datetime.utcnow() - timedelta(days=7)
    role_rows = dict(db.query(User.role, func.count(User.id)).group_by(User.role).all())
    users = sd.UserCounts(
        total=sum(role_rows.values()),
        customers=role_rows.get(UserRole.CUSTOMER, 0),
        providers=role_rows.get(UserRole.PROVIDER, 0),
        admins=role_rows.get(UserRole.ADMIN, 0),
    )
    average, review_total = db.query(func.avg(Review.rating), func.count(Review.id)).one()
    return sd.AdminDashboardOut(
        users=users,
        new_users_7d=db.query(func.count(User.id)).filter(User.created_at >= week_ago).scalar() or 0,
        skills_total=db.query(func.count(Skill.id)).scalar() or 0,
        custom_skills=db.query(func.count(Skill.id)).filter(Skill.created_by_id.isnot(None)).scalar() or 0,
        categories=db.query(func.count(Category.id)).scalar() or 0,
        requests=count_requests_by_status(db),
        requests_7d=db.query(func.count(ServiceRequest.id)).filter(ServiceRequest.created_at >= week_ago).scalar() or 0,
        messages_total=db.query(func.count(Message.id)).scalar() or 0,
        reviews_total=int(review_total or 0),
        avg_rating=rating_number(average),
    )


# ------------------------------------------------------------------- reviews


class ReviewError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def check_can_review(request, customer_id: int, already_reviewed: bool) -> None:
    if request.customer_id != customer_id:
        raise ReviewError(403, "Only the customer of this request can review it.")
    if request.status != RequestStatus.COMPLETED:
        raise ReviewError(
            409, f"Only COMPLETED requests can be reviewed. This one is {request.status.value}."
        )
    if already_reviewed:
        raise ReviewError(409, "You already reviewed this request.")


def create_review(db: Session, request, customer: User, payload) -> Review:
    exists = db.query(Review.id).filter(Review.service_request_id == request.id).first()
    check_can_review(request, customer.id, exists is not None)
    review = Review(
        service_request_id=request.id,
        reviewer_id=customer.id,
        provider_id=request.provider_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(review)
    try:
        db.commit()
    except IntegrityError:  # two clicks at the same moment: the unique key stops the second
        db.rollback()
        raise ReviewError(409, "You already reviewed this request.")
    db.refresh(review)
    return review


def review_out(review, viewer_id: int) -> sd.ReviewOut:
    other = review.provider if review.reviewer_id == viewer_id else review.reviewer
    return sd.ReviewOut(
        id=review.id,
        request_id=review.service_request_id,
        rating=review.rating,
        comment=review.comment,
        skill_name=review.service_request.skill.name,
        other_party=schemas.PartyOut(id=other.id, full_name=other.full_name, photo_url=other.photo_url),
        created_at=review.created_at,
    )


def list_my_reviews(db: Session, user: User, page: int, page_size: int) -> list[sd.ReviewOut]:
    """Customer: reviews I wrote. Provider: reviews I received."""
    column = Review.reviewer_id if user.role == UserRole.CUSTOMER else Review.provider_id
    rows = (
        db.query(Review)
        .options(
            joinedload(Review.service_request).joinedload(ServiceRequest.skill),
            joinedload(Review.reviewer),
            joinedload(Review.provider),
        )
        .filter(column == user.id)
        .order_by(Review.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [review_out(row, user.id) for row in rows]


# --------------------------------------------------------------- admin panel


def like_filter(q: str | None, *columns):
    if not q or not q.strip():
        return None
    pattern = f"%{escape_like(q.strip())}%"
    return or_(*[column.ilike(pattern, escape="!") for column in columns])


def admin_user_out(user, cls=sd.AdminUserOut, **extra):
    return cls(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        city=user.location.city if user.location else None,
        created_at=user.created_at,
        **extra,
    )


def _users_page(db: Session, role, q, page, page_size):
    query = db.query(User).options(joinedload(User.location))
    if role is not None:
        query = query.filter(User.role == role)
    condition = like_filter(q, User.full_name, User.email)
    if condition is not None:
        query = query.filter(condition)
    return query.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()


def admin_list_users(db: Session, role, q, page, page_size) -> list[sd.AdminUserOut]:
    return [admin_user_out(u) for u in _users_page(db, role, q, page, page_size)]


def admin_list_providers(db: Session, q, page, page_size) -> list[sd.AdminProviderOut]:
    users = _users_page(db, UserRole.PROVIDER, q, page, page_size)
    ids = [u.id for u in users]
    if not ids:
        return []
    skills = dict(
        db.query(ProviderProfile.user_id, func.count(ProviderSkill.id))
        .select_from(ProviderProfile)
        .join(ProviderSkill, ProviderSkill.provider_profile_id == ProviderProfile.id)
        .filter(ProviderProfile.user_id.in_(ids))
        .group_by(ProviderProfile.user_id)
        .all()
    )
    ratings = {
        provider_id: (avg, n)
        for provider_id, avg, n in db.query(Review.provider_id, func.avg(Review.rating), func.count(Review.id))
        .filter(Review.provider_id.in_(ids))
        .group_by(Review.provider_id)
        .all()
    }
    received = dict(
        db.query(ServiceRequest.provider_id, func.count(ServiceRequest.id))
        .filter(ServiceRequest.provider_id.in_(ids))
        .group_by(ServiceRequest.provider_id)
        .all()
    )
    result = []
    for user in users:
        avg, n = ratings.get(user.id, (None, 0))
        result.append(
            admin_user_out(
                user,
                sd.AdminProviderOut,
                skills_count=int(skills.get(user.id, 0)),
                avg_rating=rating_number(avg),
                review_count=int(n),
                requests_received=int(received.get(user.id, 0)),
            )
        )
    return result


def admin_request_out(request) -> sd.AdminRequestOut:
    return sd.AdminRequestOut(
        id=request.id,
        status=request.status,
        service_mode=request.service_mode,
        customer_id=request.customer_id,
        customer_name=request.customer.full_name,
        provider_id=request.provider_id,
        provider_name=request.provider.full_name,
        skill_name=request.skill.name,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def admin_list_requests(db: Session, status, page, page_size) -> list[sd.AdminRequestOut]:
    query = _request_query(db)
    if status is not None:
        query = query.filter(ServiceRequest.status == status)
    rows = (
        query.order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [admin_request_out(row) for row in rows]


def admin_list_skills(db: Session, q, custom_only, page, page_size) -> list[sd.AdminSkillOut]:
    query = db.query(Skill).options(joinedload(Skill.category))
    condition = like_filter(q, Skill.name)
    if condition is not None:
        query = query.filter(condition)
    if custom_only:
        query = query.filter(Skill.created_by_id.isnot(None))
    skills = query.order_by(Skill.name).offset((page - 1) * page_size).limit(page_size).all()
    ids = [s.id for s in skills]
    if not ids:
        return []
    providers = dict(
        db.query(ProviderSkill.skill_id, func.count(ProviderSkill.id))
        .filter(ProviderSkill.skill_id.in_(ids))
        .group_by(ProviderSkill.skill_id)
        .all()
    )
    used = dict(
        db.query(ServiceRequest.skill_id, func.count(ServiceRequest.id))
        .filter(ServiceRequest.skill_id.in_(ids))
        .group_by(ServiceRequest.skill_id)
        .all()
    )
    author_ids = {s.created_by_id for s in skills if s.created_by_id}
    authors = (
        dict(db.query(User.id, User.full_name).filter(User.id.in_(author_ids)).all())
        if author_ids
        else {}
    )
    return [
        sd.AdminSkillOut(
            id=s.id,
            name=s.name,
            category=s.category.name,
            official=s.created_by_id is None,
            added_by=authors.get(s.created_by_id),
            providers_count=int(providers.get(s.id, 0)),
            requests_count=int(used.get(s.id, 0)),
        )
        for s in skills
    ]


def skill_usage(db: Session, skill_id: int) -> tuple[int, int]:
    providers = db.query(func.count(ProviderSkill.id)).filter(ProviderSkill.skill_id == skill_id).scalar() or 0
    requests = db.query(func.count(ServiceRequest.id)).filter(ServiceRequest.skill_id == skill_id).scalar() or 0
    return providers, requests
