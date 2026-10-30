from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.services.misc_services import DashboardService
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return DashboardService(db).get_summary(current_user)


@router.get("/executive-summary")
def get_executive_dashboard_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Executive Dashboard Phase 1 — additive, separate endpoint. /summary
    above is completely untouched, so nothing that already uses it changes."""
    return DashboardService(db).get_executive_summary(current_user)


@router.get("/top-lists")
def get_dashboard_top_lists(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Executive Dashboard Phase 2 — Top Lists."""
    return DashboardService(db).get_top_lists()


@router.get("/calendar")
def get_dashboard_calendar(days_ahead: int = 30, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Executive Dashboard Phase 2 — Calendar Widget."""
    return DashboardService(db).get_calendar_events(days_ahead)
