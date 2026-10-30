from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO

from app.core.database import get_db
from app.api.deps import PermissionChecker
from app.schemas.reports import (
    FinancialReportOut, TenantReportOut, OwnerReportOut, PropertyReportOut,
    VacancyReportOut, OccupancyReportOut, UnitReportOut, IncomeReportOut, ExpenseReportOut,
    ProfitReportOut, DashboardAnalyticsOut,
    LeaseReportOut, MaintenanceReportOut, CollectionsReportOut, OutstandingReportOut, ContractExpirationReportOut,
    ReportScheduleCreate, ReportScheduleUpdate, ReportScheduleOut,
    InvoiceRegisterOut, PaymentRegisterOut, OverdueInvoiceReportOut,
)
from app.services.reports_service import ReportsService, ReportScheduleService, REPORT_TYPES, generate_report, report_to_document
from app.models.user import User

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/financial", response_model=FinancialReportOut)
def financial_report(
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).financial_report(date_from, date_to)


@router.get("/tenants", response_model=TenantReportOut)
def tenant_report(
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).tenant_report(date_from, date_to)


@router.get("/owners", response_model=OwnerReportOut)
def owner_report(
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).owner_report(date_from, date_to)


@router.get("/properties", response_model=PropertyReportOut)
def property_report(
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).property_report(date_from, date_to)


@router.get("/vacancy", response_model=VacancyReportOut)
def vacancy_report(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view"))):
    return ReportsService(db).vacancy_report()


@router.get("/occupancy", response_model=OccupancyReportOut)
def occupancy_report(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).occupancy_report(months)


@router.get("/units", response_model=UnitReportOut)
def units_report(
    property_id: Optional[int] = Query(None, description="Building/Villa id to scope to (Building Units Report / Villa Units Report). Omit for a portfolio-wide Unit Status/Availability Report."),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).units_report(property_id)


@router.get("/income", response_model=IncomeReportOut)
def income_report(
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).income_report(date_from, date_to)


@router.get("/expenses", response_model=ExpenseReportOut)
def expense_report(
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).expense_report(date_from, date_to)


@router.get("/profit", response_model=ProfitReportOut)
def profit_report(
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).profit_report(date_from, date_to)


@router.get("/analytics/dashboard", response_model=DashboardAnalyticsOut)
def dashboard_analytics(
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).dashboard_analytics(date_from, date_to)


# ---------------- Enterprise Reporting extension: 5 new report types ----------------
@router.get("/leases", response_model=LeaseReportOut)
def lease_report(
    contract_status: Optional[str] = Query(None), property_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).lease_report(contract_status, property_id, date_from, date_to)


# ---------------- Rent Billing Engine reports ----------------
# "Building/Owner Collection Report" and "Tenant Statement" reuse the
# existing /reports/collections and /reports/tenants endpoints above
# (already filterable) rather than duplicating them — see
# reports_service.py's ReportsService docstring on this.
@router.get("/invoices/register", response_model=InvoiceRegisterOut)
def invoice_register(
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None), invoice_status: Optional[str] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).invoice_register(date_from, date_to, invoice_status)


@router.get("/invoices/payment-register", response_model=PaymentRegisterOut)
def payment_register(
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).payment_register(date_from, date_to)


@router.get("/invoices/overdue", response_model=OverdueInvoiceReportOut)
def overdue_invoice_report(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view"))):
    return ReportsService(db).overdue_invoice_report()


@router.get("/maintenance", response_model=MaintenanceReportOut)
def maintenance_report(
    status: Optional[str] = Query(None), priority: Optional[str] = Query(None), property_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).maintenance_report(status, priority, property_id, date_from, date_to)


@router.get("/collections", response_model=CollectionsReportOut)
def collections_report(
    months: int = Query(6, ge=1, le=24), date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).collections_report(months, date_from, date_to)


@router.get("/outstanding", response_model=OutstandingReportOut)
def outstanding_report(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view"))):
    return ReportsService(db).outstanding_report()


@router.get("/contract-expirations", response_model=ContractExpirationReportOut)
def contract_expiration_report(
    days: int = Query(30, ge=1, le=365), property_id: Optional[int] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).contract_expiration_report(days, property_id)


@router.get("/owner-balance")
def owner_balance_report(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view"))):
    return ReportsService(db).owner_balance_report()


@router.get("/tenant-ledger")
def tenant_ledger_report(tenant_id: Optional[int] = Query(None), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view"))):
    return ReportsService(db).tenant_ledger_report(tenant_id)


@router.get("/security-deposits")
def security_deposit_report(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view"))):
    return ReportsService(db).security_deposit_report()


@router.get("/renewed-contracts")
def renewed_contracts_report(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view"))):
    return ReportsService(db).renewed_contracts_report()


@router.get("/top-tenants")
def top_tenants_report(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view"))):
    return ReportsService(db).top_tenants_report(limit)


@router.get("/repeated-late-payers")
def repeated_late_payers_report(min_late_count: int = Query(2, ge=1), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view"))):
    return ReportsService(db).repeated_late_payers_report(min_late_count)


# ---------------- Generic export (PDF / Excel) — works for all 10 report types ----------------
@router.get("/{report_type}/export")
def export_report(
    report_type: str, format: str = Query("pdf", pattern="^(pdf|excel|csv)$"),
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    property_id: Optional[int] = Query(None), contract_status: Optional[str] = Query(None),
    status: Optional[str] = Query(None), priority: Optional[str] = Query(None),
    months: Optional[int] = Query(None), days: Optional[int] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    """One export endpoint reused by every report type, rather than a
    duplicated export endpoint per report — the report_type path segment
    dispatches to the right existing report method (see
    reports_service.generate_report), and report_to_document() converts
    whichever dict comes back into the same generic shape that
    report_export_service renders to PDF/Excel."""
    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown report_type '{report_type}'. Valid types: {REPORT_TYPES}")

    from app.services.report_export_service import render_pdf, render_excel, render_csv
    filters = {
        "date_from": date_from, "date_to": date_to, "property_id": property_id,
        "contract_status": contract_status, "status": status, "priority": priority,
        "months": months, "days": days,
    }
    service = ReportsService(db)
    data = generate_report(service, report_type, filters)
    doc = report_to_document(report_type, data)

    if format == "excel":
        file_bytes = render_excel(doc)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"{report_type}-report.xlsx"
    elif format == "csv":
        file_bytes = render_csv(doc)
        media_type = "text/csv"
        filename = f"{report_type}-report.csv"
    else:
        file_bytes = render_pdf(doc)
        media_type = "application/pdf"
        filename = f"{report_type}-report.pdf"

    return StreamingResponse(
        BytesIO(file_bytes), media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------- Export Scheduling ----------------
@router.get("/schedules", response_model=list[ReportScheduleOut])
def list_schedules(
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportScheduleService(db).list_schedules(is_active)


@router.post("/schedules", response_model=ReportScheduleOut, status_code=201)
def create_schedule(
    payload: ReportScheduleCreate,
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.create")),
):
    return ReportScheduleService(db).create_schedule(payload.model_dump(), actor_id=current_user.id)


@router.get("/schedules/{schedule_id}", response_model=ReportScheduleOut)
def get_schedule(schedule_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view"))):
    return ReportScheduleService(db).get_schedule(schedule_id)


@router.put("/schedules/{schedule_id}", response_model=ReportScheduleOut)
def update_schedule(
    schedule_id: int, payload: ReportScheduleUpdate,
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.edit")),
):
    return ReportScheduleService(db).update_schedule(schedule_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.delete"))):
    ReportScheduleService(db).delete_schedule(schedule_id, actor_id=current_user.id)
    return {"message": "Report schedule deleted successfully"}


@router.post("/schedules/{schedule_id}/run-now", response_model=ReportScheduleOut)
def run_schedule_now(schedule_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.edit"))):
    return ReportScheduleService(db).run_schedule(schedule_id, actor_id=current_user.id)


@router.post("/schedules/run-due", response_model=list[ReportScheduleOut])
def run_due_schedules(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.edit"))):
    """Runs every schedule whose next_run_at has passed. There is no
    background scheduler process in this codebase (see app/models/
    reports.py) — this endpoint is what an external cron job or manual
    admin action calls to actually execute due schedules."""
    return ReportScheduleService(db).run_due_schedules(actor_id=current_user.id)
