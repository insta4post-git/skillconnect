from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.models import User
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["Messages"])


def load_request_or_404(db: Session, request_id: int, user: User):
    """Only the customer or the provider of this request may touch its chat."""
    request = crud.get_request_for_party(db, request_id, user)
    if request is None:  # not found, or it belongs to other people
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Request not found."
        )
    return request


# NOTE: "/messages/inbox" is a different path from "/requests/{id}/messages",
# so the order of these routes does not matter.
@router.get("/messages/inbox", response_model=list[schemas.InboxItemOut])
def inbox(
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """My conversations (one per request that has messages), newest first."""
    return crud.list_inbox(db, current_user, page, page_size)


@router.get("/requests/{request_id}/messages", response_model=schemas.ConversationOut)
def get_conversation(
    request_id: int = Path(ge=1),
    after_id: int = Query(default=0, ge=0, description="Only messages with a bigger id (for refreshing)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Conversation history for one request, oldest first."""
    request = load_request_or_404(db, request_id, current_user)
    rows = crud.list_messages(db, request.id, after_id)
    return schemas.ConversationOut(
        request_id=request.id,
        request_status=request.status,
        can_send=crud.can_send_message(request),
        messages=[crud.message_out(m, current_user.id) for m in rows],
    )


@router.post(
    "/requests/{request_id}/messages",
    response_model=schemas.MessageOut,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    payload: schemas.MessageCreate,
    request_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message to the other side of this request."""
    request = load_request_or_404(db, request_id, current_user)
    if not crud.can_send_message(request):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This request is {request.status.value}, so the chat is closed. "
            "You can still read the old messages.",
        )
    if crud.count_messages(db, request.id) >= crud.MAX_MESSAGES_PER_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This conversation reached the limit of {crud.MAX_MESSAGES_PER_REQUEST} messages.",
        )
    message = crud.create_message(db, request.id, current_user, payload.body)
    return crud.message_out(message, current_user.id)
