from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.models import Category, Skill, User
from app.security import require_provider

router = APIRouter(prefix="/api/services", tags=["services"])


def skill_detail(skill: Skill) -> schemas.SkillDetailOut:
    return schemas.SkillDetailOut(
        id=skill.id,
        name=skill.name,
        category_id=skill.category_id,
        category_name=skill.category.name,
        is_custom=skill.created_by_id is not None,
    )


@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    """Public list of service categories with their skills (A to Z)."""
    return db.query(Category).order_by(Category.name).all()


@router.get("/skills", response_model=list[schemas.SkillDetailOut])
def search_skills(
    q: str | None = Query(default=None, max_length=60, description="Search text"),
    category_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Public skill search. Matches the skill name or its category name."""
    skills = crud.search_skills(db, q=q, category_id=category_id, limit=limit)
    return [skill_detail(skill) for skill in skills]


@router.post(
    "/skills",
    response_model=schemas.SkillDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def add_skill(
    payload: schemas.SkillCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_provider),
):
    """A provider adds a skill that is missing from the list.

    If the skill already exists (any capitalisation) the existing one is returned
    with status 200. Then add it to your profile with PUT /api/providers/me/skills.
    """
    category = db.get(Category, payload.category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found."
        )
    try:
        skill, created = crud.get_or_create_custom_skill(
            db, user=current_user, category=category, name=payload.name
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not created:
        response.status_code = status.HTTP_200_OK
    return skill_detail(skill)
