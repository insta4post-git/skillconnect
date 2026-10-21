from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app import crud, crud_dashboard, schemas_dashboard as sd
from app.database import get_db
from app.models import User, UserRole
from app.security import get_current_user, require_customer

router = APIRouter(prefix="/api", tags=["Reviews"])


@router.post(
    "/requests/{request_id}/review",
    response_model=sd.ReviewOut,
    status_code=status.HTTP_201_CREATED,
)
def review_request(
    payload: sd.ReviewCreate,
    request_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_customer),
):
    """Customer rates a COMPLETED request (1-5 stars + optional comment). One review per request."""
    request = crud.get_request_for_party(db, request_id, current_user)
    if request is None:  # not found, or it belongs to other people
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")
    try:
        review = crud_dashboard.create_review(db, request, current_user, payload)
    except crud_dashboard.ReviewError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return crud_dashboard.review_out(review, current_user.id)


@router.get("/reviews/mine", response_model=list[sd.ReviewOut])
def my_reviews(
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Customer: reviews I wrote. Provider: reviews I received."""
    if current_user.role not in (UserRole.CUSTOMER, UserRole.PROVIDER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not available for this account.")
    return crud_dashboard.list_my_reviews(db, current_user, page, page_size)
