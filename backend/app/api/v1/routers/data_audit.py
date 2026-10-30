"""
Data Integrity Audit endpoint — see app/services/data_audit_service.py
for the full rationale. Read-only: every check is a SELECT, nothing is
ever modified, updated, or deleted by this endpoint.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import PermissionChecker
from app.services.data_audit_service import DataAuditService
from app.models.user import User

router = APIRouter(prefix="/data-audit", tags=["Data Integrity Audit"])


@router.get("")
def run_data_audit(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view"))):
    return DataAuditService(db).run_audit()
