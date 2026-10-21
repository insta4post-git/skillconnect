from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app import crud_dashboard, schemas_dashboard as sd
from app.database import get_db
from app.models import RequestStatus, Skill, User, UserRole
from app.security import require_admin

# Every route here needs an ADMIN login.
router = APIRouter(prefix="/api/admin", tags=["Admin"], dependencies=[Depends(require_admin)])

PAGE = Query(default=1, ge=1, le=1000)
PAGE_SIZE = Query(default=20, ge=1, le=100)


@router.get("/users", response_model=list[sd.AdminUserOut])
def list_users(
    role: UserRole | None = None,
    q: str | None = Query(default=None, max_length=100, description="Search name or email"),
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    db: Session = Depends(get_db),
):
    return crud_dashboard.admin_list_users(db, role, q, page, page_size)


@router.get("/providers", response_model=list[sd.AdminProviderOut])
def list_providers(
    q: str | None = Query(default=None, max_length=100),
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    db: Session = Depends(get_db),
):
    return crud_dashboard.admin_list_providers(db, q, page, page_size)


@router.get("/requests", response_model=list[sd.AdminRequestOut])
def list_requests(
    status_filter: RequestStatus | None = Query(default=None, alias="status"),
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    db: Session = Depends(get_db),
):
    return crud_dashboard.admin_list_requests(db, status_filter, page, page_size)


@router.get("/skills", response_model=list[sd.AdminSkillOut])
def list_skills(
    q: str | None = Query(default=None, max_length=100),
    custom_only: bool = Query(default=False, description="Only skills added by providers"),
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    db: Session = Depends(get_db),
):
    return crud_dashboard.admin_list_skills(db, q, custom_only, page, page_size)


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(skill_id: int = Path(ge=1), db: Session = Depends(get_db)):
    """Remove a skill that nobody uses (e.g. a misspelled custom skill)."""
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found.")
    providers, requests = crud_dashboard.skill_usage(db, skill_id)
    if providers or requests:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This skill is in use ({providers} provider(s), {requests} request(s)) and cannot be deleted.",
        )
    db.delete(skill)
    db.commit()
