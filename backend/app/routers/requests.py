from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.models import RequestStatus, ServiceMode, User, UserRole
from app.security import get_current_user, require_customer

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.post(
    "/regular",
    response_model=schemas.RequestOut,
    status_code=status.HTTP_201_CREATED,
)
def create_regular_request(
    payload: schemas.RegularRequestCreate,
    db: Session = Depends(get_db),
    customer: User = Depends(require_customer),
):
    """Customer sends a long-term (REGULAR) request to one provider.

    Example: a tutor for 3 months, Monday/Wednesday/Friday, 5 pm to 6:30 pm.
    The request starts as PENDING. The provider answers it in the next step.
    """
    provider = db.get(User, payload.provider_id)
    if (
        provider is None
        or provider.role != UserRole.PROVIDER
        or provider.provider_profile is None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found."
        )
    profile = provider.provider_profile
    if profile.service_mode == ServiceMode.NON_REGULAR:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This provider only takes short-term work.",
        )
    if payload.skill_id not in {link.skill_id for link in profile.skills}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This provider does not offer that skill.",
        )
    if payload.location is None and customer.location is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add a location to the request or save one with PUT /api/users/me/profile.",
        )
    if (
        crud.count_pending_requests(db, customer)
        >= crud.MAX_PENDING_REQUESTS_PER_CUSTOMER
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"You already have {crud.MAX_PENDING_REQUESTS_PER_CUSTOMER} pending "
                "requests. Wait for answers before sending more."
            ),
        )
    if crud.find_overlapping_regular_request(
        db,
        customer=customer,
        provider_id=provider.id,
        skill_id=payload.skill_id,
        start=payload.start_date,
        end=payload.end_date,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an open request to this provider for these dates and skill.",
        )

    request = crud.create_regular_request(
        db, customer=customer, provider=provider, data=payload
    )
    return crud.request_out(request)


# "/mine" must be declared before "/{request_id}"
@router.get("/mine", response_model=list[schemas.RequestOut])
def my_requests(
    status_filter: RequestStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Customers: requests I sent. Providers: requests I received."""
    if current_user.role not in (UserRole.CUSTOMER, UserRole.PROVIDER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to do this.",
        )
    rows = crud.list_my_requests(db, current_user, status_filter)
    return [crud.request_out(row) for row in rows]


@router.get("/{request_id}", response_model=schemas.RequestOut)
def get_request(
    request_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Only the customer or the provider of the request can open it."""
    request = crud.get_request_for_party(db, request_id, current_user)
    if request is None:  # also when it belongs to someone else: do not reveal it
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Request not found."
        )
    return crud.request_out(request)
