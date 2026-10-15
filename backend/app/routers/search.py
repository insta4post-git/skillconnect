from datetime import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.models import RequestServiceMode, ServiceMode, WeekDay
from app.security import bearer_scheme, get_current_user

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/providers", response_model=schemas.ProviderSearchOut)
def search_providers(
    q: str | None = Query(
        default=None,
        max_length=100,
        description='Free text, e.g. "plumber" or "I need a plumber near me"',
    ),
    skill_id: int | None = Query(default=None, ge=1),
    category_id: int | None = Query(default=None, ge=1),
    city: str | None = Query(default=None, max_length=100),
    area: str | None = Query(default=None, max_length=100),
    pincode: str | None = Query(default=None, pattern=r"^\d{6}$"),
    near_me: bool = Query(
        default=False,
        description="Use the city saved in my profile (login required). No GPS.",
    ),
    service_type: RequestServiceMode | None = Query(
        default=None, description="REGULAR (long term) or NON_REGULAR (short term)"
    ),
    available_day: WeekDay | None = Query(default=None),
    available_time: time | None = Query(
        default=None, description="HH:MM, needs available_day"
    ),
    min_rating: float | None = Query(default=None, ge=1, le=5),
    sort: Literal["rating", "experience", "newest"] = "rating",
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    """Public provider search. Login is only needed when near_me=true."""
    if available_time is not None and available_day is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="available_time needs available_day as well.",
        )

    near_location = None
    if near_me:
        user = get_current_user(credentials, db)  # 401 if not logged in
        if user.location is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Save your location first with PUT /api/users/me/profile.",
            )
        near_location = user.location

    rows, total = crud.search_providers(
        db,
        q=q,
        skill_id=skill_id,
        category_id=category_id,
        city=city,
        area=area,
        pincode=pincode,
        service_mode=ServiceMode(service_type.value) if service_type else None,
        day=available_day,
        at_time=available_time,
        min_rating=min_rating,
        sort=sort,
        near_location=near_location,
        page=page,
        page_size=page_size,
    )
    return schemas.ProviderSearchOut(
        total=total,
        page=page,
        page_size=page_size,
        has_more=page * page_size < total,
        results=[crud.provider_card(p, avg, count) for p, avg, count in rows],
    )
