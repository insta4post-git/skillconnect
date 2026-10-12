from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import Category

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    """Public list of service categories with their skills (for forms and search)."""
    return db.query(Category).order_by(Category.name).all()
