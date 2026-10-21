from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud_dashboard, schemas_dashboard as sd
from app.database import get_db
from app.models import User
from app.security import require_admin, require_customer, require_provider

router = APIRouter(prefix="/api/dashboard", tags=["Dashboards"])


@router.get("/customer", response_model=sd.CustomerDashboardOut)
def customer_dashboard(
    db: Session = Depends(get_db), current_user: User = Depends(require_customer)
):
    """Customer control panel: my requests, accepted services, messages, reviews."""
    return crud_dashboard.customer_dashboard(db, current_user)


@router.get("/provider", response_model=sd.ProviderDashboardOut)
def provider_dashboard(
    db: Session = Depends(get_db), current_user: User = Depends(require_provider)
):
    """Provider control panel: incoming requests, accepted jobs, profile checklist, rating."""
    return crud_dashboard.provider_dashboard(db, current_user)


@router.get("/admin", response_model=sd.AdminDashboardOut)
def admin_dashboard(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    """Admin control panel: platform totals."""
    return crud_dashboard.admin_dashboard(db)
