from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from app.repositories.reports_repository import ReportsRepository, INCOME_TYPES, EXPENSE_TYPES
from app.models.financial import TransactionType


def _default_range(date_from: Optional[date], date_to: Optional[date]) -> tuple[date, date]:
    today = date.today()
    return (date_from or today.replace(day=1)), (date_to or today)


class ReportsService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReportsRepository(db)

    # ---------------- Financial ----------------
    def financial_report(self, date_from: Optional[date], date_to: Optional[date]) -> dict:
        d_from, d_to = _default_range(date_from, date_to)
        total_income = self.repo.total_amount(INCOME_TYPES, d_from, d_to)
        total_expense = self.repo.total_amount(EXPENSE_TYPES, d_from, d_to)
        return {
            "date_from": d_from, "date_to": d_to,
            "total_income": total_income, "total_expense": total_expense,
            "net_cash_flow": total_income - total_expense,
            "total_outstanding_tenant": self.repo.tenant_outstanding_total(),
            "total_outstanding_owner": self.repo.owner_outstanding_total(),
            "collection_rate_percentage": self.repo.collection_rate(d_from, d_to),
            "transactions_by_type": self.repo.transactions_by_type(d_from, d_to),
        }

    # ---------------- Tenant ----------------
    def tenant_report(self, date_from: Optional[date], date_to: Optional[date]) -> dict:
        counts = self.repo.tenant_counts()
        return {
            "total_tenants": counts["total"], "individual_tenants": counts["individual"],
            "company_tenants": counts["company"], "blacklisted_tenants": counts["blacklisted"],
            "average_rating": self.repo.average_tenant_rating(),
            "contracts_expiring_soon": self.repo.contracts_expiring_soon_count(30),
            "top_tenants_by_payment": self.repo.top_tenants_by_payment(date_from, date_to),
            "outstanding_tenants": self.repo.tenant_outstanding_list(),
        }

    # ---------------- Owner ----------------
    def owner_report(self, date_from: Optional[date], date_to: Optional[date]) -> dict:
        d_from, d_to = _default_range(date_from, date_to)
        counts = self.repo.owner_counts()
        return {
            "total_owners": counts["total"], "individual_owners": counts["individual"], "company_owners": counts["company"],
            "total_paid_to_owners": self.repo.total_amount([TransactionType.OWNER_PAYMENT], d_from, d_to),
            "top_owners_by_properties": self.repo.top_owners_by_properties(),
            "outstanding_owners": self.repo.owner_outstanding_list(),
        }

    # ---------------- Property ----------------
    def property_report(self, date_from: Optional[date], date_to: Optional[date]) -> dict:
        return {
            "total_properties": self.repo.total_properties(),
            "by_type": self.repo.property_counts_by_type(),
            "by_availability": self.repo.property_counts_by_status(),
            "top_properties_by_revenue": self.repo.top_properties_by_revenue(date_from, date_to),
        }

    # ---------------- Vacancy ----------------
    def vacancy_report(self) -> dict:
        counts = self.repo.vacancy_counts()
        rate = (Decimal(counts["vacant"]) / Decimal(counts["total"]) * 100).quantize(Decimal("0.01")) if counts["total"] else Decimal("0")
        return {
            "as_of_date": date.today(), "total_properties": counts["total"], "vacant_count": counts["vacant"],
            "leased_count": counts["leased"], "other_count": counts["other"], "vacancy_rate_percentage": rate,
            "vacant_properties": self.repo.vacant_properties(),
        }

    # ---------------- Occupancy ----------------
    def occupancy_report(self, months: int = 6) -> dict:
        counts = self.repo.vacancy_counts()
        overall_rate = (Decimal(counts["leased"]) / Decimal(counts["total"]) * 100).quantize(Decimal("0.01")) if counts["total"] else Decimal("0")

        today = date.today()
        trend = []
        for i in range(months - 1, -1, -1):
            target_month = today.month - i
            target_year = today.year
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            rate = self.repo.occupancy_rate_for_month(target_year, target_month)
            trend.append({"month": f"{target_year:04d}-{target_month:02d}", "occupancy_rate_percentage": rate})

        return {
            "as_of_date": today, "overall_occupancy_rate_percentage": overall_rate,
            "by_property_type": self.repo.occupancy_by_type(), "trend": trend,
        }

    # ---------------- Units (Phase 2.0) ----------------
    def units_report(self, property_id: Optional[int] = None) -> dict:
        data = self.repo.units_report(property_id)
        return {"as_of_date": date.today(), **data}

    # ---------------- Income ----------------
    def income_report(self, date_from: Optional[date], date_to: Optional[date], property_id: Optional[int] = None) -> dict:
        d_from, d_to = _default_range(date_from, date_to)
        return {
            "date_from": d_from, "date_to": d_to,
            "total_income": self.repo.total_amount(INCOME_TYPES, d_from, d_to, property_id),
            "by_category": self.repo.amount_by_category(INCOME_TYPES, d_from, d_to, property_id),
            "by_property": self.repo.amount_by_property(INCOME_TYPES, d_from, d_to, property_id=property_id),
            "trend": self.repo.monthly_trend(INCOME_TYPES, 6, property_id),
        }

    # ---------------- Expense ----------------
    def expense_report(self, date_from: Optional[date], date_to: Optional[date], property_id: Optional[int] = None) -> dict:
        d_from, d_to = _default_range(date_from, date_to)
        return {
            "date_from": d_from, "date_to": d_to,
            "total_expense": self.repo.total_amount(EXPENSE_TYPES, d_from, d_to, property_id),
            "total_maintenance_cost": self.repo.maintenance_cost_total(d_from, d_to, property_id),
            "by_category": self.repo.amount_by_category(EXPENSE_TYPES, d_from, d_to, property_id),
            "by_property": self.repo.amount_by_property(EXPENSE_TYPES, d_from, d_to, property_id=property_id),
            "trend": self.repo.monthly_trend(EXPENSE_TYPES, 6, property_id),
        }

    # ---------------- Profit ----------------
    def profit_report(self, date_from: Optional[date], date_to: Optional[date]) -> dict:
        d_from, d_to = _default_range(date_from, date_to)
        total_income = self.repo.total_amount(INCOME_TYPES, d_from, d_to)
        total_expense = self.repo.total_amount(EXPENSE_TYPES, d_from, d_to)
        net_profit = total_income - total_expense
        margin = (net_profit / total_income * 100).quantize(Decimal("0.01")) if total_income else Decimal("0")

        income_by_property = {p["property_id"]: p for p in self.repo.amount_by_property(INCOME_TYPES, d_from, d_to)}
        expense_by_property = {p["property_id"]: p for p in self.repo.amount_by_property(EXPENSE_TYPES, d_from, d_to)}
        property_ids = set(income_by_property) | set(expense_by_property)
        by_property = []
        for pid in property_ids:
            income = income_by_property.get(pid, {}).get("total_amount", Decimal("0"))
            expense = expense_by_property.get(pid, {}).get("total_amount", Decimal("0"))
            source = income_by_property.get(pid) or expense_by_property.get(pid)
            by_property.append({
                "property_id": pid, "property_code": source["property_code"], "property_title": source["property_title"],
                "income": income, "expense": expense, "profit": income - expense,
            })
        by_property.sort(key=lambda x: x["profit"], reverse=True)

        income_trend = {t["month"]: t["total_amount"] for t in self.repo.monthly_trend(INCOME_TYPES, 6)}
        expense_trend = {t["month"]: t["total_amount"] for t in self.repo.monthly_trend(EXPENSE_TYPES, 6)}
        trend = []
        for month in sorted(set(income_trend) | set(expense_trend)):
            inc = income_trend.get(month, Decimal("0"))
            exp = expense_trend.get(month, Decimal("0"))
            trend.append({"month": month, "income": inc, "expense": exp, "profit": inc - exp})

        return {
            "date_from": d_from, "date_to": d_to, "total_income": total_income, "total_expense": total_expense,
            "net_profit": net_profit, "profit_margin_percentage": margin, "by_property": by_property, "trend": trend,
            "best_performing_property": by_property[0] if by_property else None,
            "lowest_performing_property": by_property[-1] if by_property else None,
        }

    def property_profit_and_loss(self, property_id: int, date_from: Optional[date], date_to: Optional[date]) -> dict:
        """Single-property P&L. Reuses the same total_amount/amount_by_
        category/monthly_trend calls as the portfolio profit_report above,
        just property_id-scoped — broken down by category (income and
        expense) instead of by property, since property is already fixed."""
        from app.repositories.property_repository import PropertyRepository
        prop = PropertyRepository(self.db).get(property_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

        d_from, d_to = _default_range(date_from, date_to)
        total_income = self.repo.total_amount(INCOME_TYPES, d_from, d_to, property_id)
        total_expense = self.repo.total_amount(EXPENSE_TYPES, d_from, d_to, property_id)
        net_profit = total_income - total_expense
        margin = (net_profit / total_income * 100).quantize(Decimal("0.01")) if total_income else Decimal("0")

        income_trend = {t["month"]: t["total_amount"] for t in self.repo.monthly_trend(INCOME_TYPES, 6, property_id)}
        expense_trend = {t["month"]: t["total_amount"] for t in self.repo.monthly_trend(EXPENSE_TYPES, 6, property_id)}
        trend = []
        for month in sorted(set(income_trend) | set(expense_trend)):
            inc = income_trend.get(month, Decimal("0"))
            exp = expense_trend.get(month, Decimal("0"))
            trend.append({"month": month, "income": inc, "expense": exp, "profit": inc - exp})

        return {
            "property_id": property_id, "property_code": prop.property_code, "property_title": prop.title,
            "date_from": d_from, "date_to": d_to, "total_income": total_income, "total_expense": total_expense,
            "net_profit": net_profit, "profit_margin_percentage": margin,
            "income_by_category": self.repo.amount_by_category(INCOME_TYPES, d_from, d_to, property_id),
            "expense_by_category": self.repo.amount_by_category(EXPENSE_TYPES, d_from, d_to, property_id),
            "trend": trend,
        }

    # ---------------- Dashboard Analytics ----------------
    def dashboard_analytics(self, date_from: Optional[date] = None, date_to: Optional[date] = None) -> dict:
        """Enterprise Dashboard extension: date_from/date_to are optional
        and default to "this month to date" exactly as before — existing
        callers that pass no arguments get identical behavior."""
        today = date.today()
        month_start = today.replace(day=1)
        period_from = date_from or month_start
        period_to = date_to or today

        total_properties = self.repo.total_properties()
        vacancy_counts = self.repo.vacancy_counts()
        vacancy_rate = (Decimal(vacancy_counts["vacant"]) / Decimal(vacancy_counts["total"]) * 100).quantize(Decimal("0.01")) if vacancy_counts["total"] else Decimal("0")
        occupancy_rate = (Decimal("100") - vacancy_rate) if vacancy_counts["total"] else Decimal("0")

        income_mtd = self.repo.total_amount(INCOME_TYPES, period_from, period_to)
        expense_mtd = self.repo.total_amount(EXPENSE_TYPES, period_from, period_to)

        kpis = {
            "total_properties": total_properties,
            "occupied_properties": vacancy_counts["leased"],
            "vacancy_rate_percentage": vacancy_rate,
            "total_tenants": self.repo.tenant_counts()["total"],
            "total_owners": self.repo.owner_counts()["total"],
            "active_rental_contracts": self.repo.active_rental_contracts_count(),
            "active_lease_agreements": self.repo.active_lease_agreements_count(),
            "open_maintenance_requests": self.repo.open_maintenance_requests_count(),
            "total_income_this_month": income_mtd,
            "total_expense_this_month": expense_mtd,
            "net_profit_this_month": income_mtd - expense_mtd,
            "total_outstanding_tenant": self.repo.tenant_outstanding_total(),
            "total_outstanding_owner": self.repo.owner_outstanding_total(),
            "total_units": vacancy_counts["total"],
            "occupied_units": vacancy_counts["leased"],
            "vacant_units": vacancy_counts["vacant"],
            "occupancy_rate_percentage": occupancy_rate,
            "contracts_expiring_soon": self.repo.contracts_expiring_soon_count(30),
        }

        income_trend = {t["month"]: t["total_amount"] for t in self.repo.monthly_trend(INCOME_TYPES, 6)}
        expense_trend = {t["month"]: t["total_amount"] for t in self.repo.monthly_trend(EXPENSE_TYPES, 6)}
        monthly_trend = []
        for month in sorted(set(income_trend) | set(expense_trend)):
            inc = income_trend.get(month, Decimal("0"))
            exp = expense_trend.get(month, Decimal("0"))
            monthly_trend.append({"month": month, "income": inc, "expense": exp, "profit": inc - exp})

        # Cash flow by transaction type reuses Phase 10's own
        # AccountingReportRepository method rather than duplicating it.
        from app.repositories.accounting_repository import AccountingReportRepository
        cash_flow_rows = AccountingReportRepository(self.db).cash_flow_by_transaction_type(period_from, period_to)
        cash_flow_by_type = [{"label": r["transaction_type"], "total_amount": r["total_amount"], "count": 0} for r in cash_flow_rows]

        six_months_ago = today - timedelta(days=180)
        return {
            "generated_at": today, "kpis": kpis, "monthly_trend": monthly_trend,
            "top_properties_by_revenue": self.repo.top_properties_by_revenue(six_months_ago, today),
            "properties_by_type": self.repo.property_counts_by_type(),
            "properties_by_availability": self.repo.property_counts_by_status(),
            "occupancy_by_type": self.repo.occupancy_by_type(),
            "cash_flow_by_type": cash_flow_by_type,
        }

    def property_financial_dashboard(self, property_id: int) -> dict:
        """The single-property version of dashboard_analytics above —
        same KPI shape and 6-month trend concept, scoped to one profit
        center. Reuses the building-management-aware RentalContract/
        MaintenanceRequest repository methods (property_id passed as a
        one-item list) rather than duplicating that counting logic."""
        from app.repositories.property_repository import PropertyRepository
        from app.repositories.rental_repository import RentalContractRepository
        from app.repositories.maintenance_repository import MaintenanceRequestRepository
        from app.models.rental import RentalContractStatus

        prop = PropertyRepository(self.db).get(property_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

        today = date.today()
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)

        income_mtd = self.repo.total_amount(INCOME_TYPES, month_start, today, property_id)
        expense_mtd = self.repo.total_amount(EXPENSE_TYPES, month_start, today, property_id)
        income_ytd = self.repo.total_amount(INCOME_TYPES, year_start, today, property_id)
        expense_ytd = self.repo.total_amount(EXPENSE_TYPES, year_start, today, property_id)

        rental_repo = RentalContractRepository(self.db)
        maintenance_repo = MaintenanceRequestRepository(self.db)

        kpis = {
            "availability_status": prop.availability_status,
            "active_leases_count": rental_repo.count_by_property_ids_and_status([property_id], RentalContractStatus.ACTIVE),
            "open_maintenance_requests": maintenance_repo.count_open_by_property_ids([property_id]),
            "total_income_this_month": income_mtd,
            "total_expense_this_month": expense_mtd,
            "net_profit_this_month": income_mtd - expense_mtd,
            "total_income_ytd": income_ytd,
            "total_expense_ytd": expense_ytd,
            "net_profit_ytd": income_ytd - expense_ytd,
            "total_outstanding_tenant": self.repo.tenant_outstanding_total_for_property(property_id),
        }

        income_trend = {t["month"]: t["total_amount"] for t in self.repo.monthly_trend(INCOME_TYPES, 6, property_id)}
        expense_trend = {t["month"]: t["total_amount"] for t in self.repo.monthly_trend(EXPENSE_TYPES, 6, property_id)}
        monthly_trend = []
        for month in sorted(set(income_trend) | set(expense_trend)):
            inc = income_trend.get(month, Decimal("0"))
            exp = expense_trend.get(month, Decimal("0"))
            monthly_trend.append({"month": month, "income": inc, "expense": exp, "profit": inc - exp})

        return {
            "property_id": property_id, "property_code": prop.property_code, "property_title": prop.title,
            "generated_at": today, "kpis": kpis, "monthly_trend": monthly_trend,
        }

    # ---------------- Lease Report ----------------
    def lease_report(self, contract_status: Optional[str] = None, property_id: Optional[int] = None, date_from: Optional[date] = None, date_to: Optional[date] = None) -> dict:
        """Covers both contract types this system models: Rental
        Contracts (company → tenant) and Lease Agreements (owner →
        company) — reusing both existing models directly rather than
        introducing a third unified "lease" entity."""
        from app.models.rental import RentalContract, RentalContractStatus
        from app.models.lease import LeaseAgreement

        rental_by_status = self.repo.contracts_by_status(RentalContract, RentalContract.contract_status)
        lease_by_status = self.repo.contracts_by_status(LeaseAgreement, LeaseAgreement.contract_status)
        rental_list = self.repo.contracts_list(RentalContract, RentalContract.contract_status, contract_status, property_id, date_from, date_to)
        lease_list = self.repo.contracts_list(LeaseAgreement, LeaseAgreement.contract_status, contract_status, property_id, date_from, date_to)

        return {
            "rental_contracts_by_status": rental_by_status,
            "lease_agreements_by_status": lease_by_status,
            "rental_contracts": [{
                "id": c.id, "contract_number": c.contract_number, "tenant_display_name": c.tenant_display_name,
                "property_id": c.property_id, "property_title": c.property_title, "unit_number": c.unit_number,
                "start_date": c.start_date, "end_date": c.end_date, "rent_amount": c.rent_amount, "contract_status": c.contract_status,
            } for c in rental_list],
            "lease_agreements": [{
                "id": c.id, "contract_number": c.contract_number, "owner_display_name": c.owner_display_name,
                "property_id": c.property_id, "property_title": c.property_title, "unit_number": c.unit_number,
                "start_date": c.start_date, "end_date": c.end_date, "rent_amount": c.rent_amount, "contract_status": c.contract_status,
            } for c in lease_list],
        }

    # ---------------- Maintenance Report ----------------
    def maintenance_report(self, status: Optional[str] = None, priority: Optional[str] = None, property_id: Optional[int] = None, date_from: Optional[date] = None, date_to: Optional[date] = None) -> dict:
        d_from, d_to = _default_range(date_from, date_to)
        requests = self.repo.maintenance_list(status, priority, property_id, d_from, d_to)
        return {
            "date_from": d_from, "date_to": d_to,
            "total_requests": len(requests),
            "by_status": self.repo.maintenance_by_status(),
            "by_priority": self.repo.maintenance_by_priority(),
            "by_category": self.repo.maintenance_by_category(),
            "by_contractor": self.repo.maintenance_by_contractor(),
            "total_cost": self.repo.maintenance_cost_total(d_from, d_to, property_id),
            "average_resolution_days": self.repo.maintenance_average_resolution_days(),
            "requests": [{
                "id": r.id, "request_number": r.request_number, "title": r.title, "property_title": r.property_title,
                "category": r.category, "priority": r.priority, "maintenance_status": r.maintenance_status,
                "reported_date": r.reported_date, "completed_date": r.completed_date,
                "total_actual_cost": r.total_actual_cost, "contractor_name": r.contractor_name,
            } for r in requests],
        }

    # ---------------- Collections Report ----------------
    def collections_report(self, months: int = 6, date_from: Optional[date] = None, date_to: Optional[date] = None) -> dict:
        d_from, d_to = _default_range(date_from, date_to)
        monthly = self.repo.collections_by_month(months)
        total_due = sum((m["due"] for m in monthly), Decimal("0"))
        total_collected = sum((m["collected"] for m in monthly), Decimal("0"))
        overall_rate = (total_collected / total_due * 100).quantize(Decimal("0.01")) if total_due else Decimal("0")
        return {
            "date_from": d_from, "date_to": d_to,
            "total_due": total_due, "total_collected": total_collected, "collection_rate_percentage": overall_rate,
            "monthly_trend": monthly,
            "by_property": self.repo.collections_by_property(d_from, d_to),
        }

    # ---------------- Outstanding Report ----------------
    def outstanding_report(self) -> dict:
        """Consolidates both sides of what's owed — tenants owing the
        company, and the company owing owners — reusing the same
        outstanding-list methods that already power the Tenant/Owner
        reports (Phase 11), plus new aging buckets (current, 1-30,
        31-60, 61-90, 90+ days overdue) for each side."""
        tenant_aging = self.repo.tenant_outstanding_aging()
        owner_aging = self.repo.owner_outstanding_aging()
        return {
            "as_of_date": date.today(),
            "tenant_outstanding_total": sum(tenant_aging.values(), Decimal("0")),
            "tenant_aging": tenant_aging,
            "tenant_outstanding_list": self.repo.tenant_outstanding_list(limit=50),
            "owner_outstanding_total": sum(owner_aging.values(), Decimal("0")),
            "owner_aging": owner_aging,
            "owner_outstanding_list": self.repo.owner_outstanding_list(limit=50),
        }

    # ---------------- Contract Expiration Report ----------------
    def contract_expiration_report(self, days: int = 30, property_id: Optional[int] = None) -> dict:
        rental = self.repo.expiring_rental_contracts(days, property_id)
        lease = self.repo.expiring_lease_agreements(days, property_id)
        today = date.today()
        return {
            "as_of_date": today, "window_days": days,
            "total_expiring": len(rental) + len(lease),
            "expiring_rental_contracts": [{
                "id": c.id, "contract_number": c.contract_number, "tenant_display_name": c.tenant_display_name,
                "property_id": c.property_id, "property_title": c.property_title, "unit_number": c.unit_number,
                "end_date": c.end_date, "days_remaining": (c.end_date - today).days, "rent_amount": c.rent_amount,
            } for c in rental],
            "expiring_lease_agreements": [{
                "id": c.id, "contract_number": c.contract_number, "owner_display_name": c.owner_display_name,
                "property_id": c.property_id, "property_title": c.property_title, "unit_number": c.unit_number,
                "end_date": c.end_date, "days_remaining": (c.end_date - today).days, "rent_amount": c.rent_amount,
            } for c in lease],
        }

    # ---------------- Rent Billing Engine reports ----------------
    # "Building Collection Report" / "Owner Collection Report" reuse
    # collections_report() above (already accepts a date range and
    # returns a by_property breakdown — filtering that breakdown to one
    # building/owner's properties is a frontend concern, not a reason to
    # duplicate the query). "Tenant Statement" reuses tenant_report()'s
    # existing per-tenant outstanding/payment data the same way. Only
    # the genuinely new report shapes are added here.
    def invoice_register(self, date_from: Optional[date], date_to: Optional[date], invoice_status: Optional[str] = None) -> dict:
        from app.models.financial import Invoice
        from sqlalchemy import select
        d_from, d_to = _default_range(date_from, date_to)
        stmt = select(Invoice).where(Invoice.deleted_at.is_(None), Invoice.issue_date >= d_from, Invoice.issue_date <= d_to)
        if invoice_status:
            stmt = stmt.where(Invoice.invoice_status == invoice_status)
        invoices = list(self.db.execute(stmt.order_by(Invoice.issue_date.asc())).scalars().all())
        return {
            "date_from": d_from, "date_to": d_to, "total_invoices": len(invoices),
            "total_amount": sum((i.amount for i in invoices), Decimal("0")),
            "total_outstanding": sum((i.outstanding_amount for i in invoices), Decimal("0")),
            "invoices": [{
                "id": i.id, "invoice_number": i.invoice_number, "tenant_display_name": i.tenant_display_name,
                "property_title": i.property_title, "unit_number": i.unit_number, "issue_date": i.issue_date, "due_date": i.due_date,
                "amount": i.amount, "amount_paid": i.amount_paid, "invoice_status": i.invoice_status,
            } for i in invoices],
        }

    def payment_register(self, date_from: Optional[date], date_to: Optional[date]) -> dict:
        from app.models.financial import Transaction, TransactionType
        from sqlalchemy import select
        d_from, d_to = _default_range(date_from, date_to)
        stmt = select(Transaction).where(
            Transaction.deleted_at.is_(None), Transaction.transaction_type == TransactionType.TENANT_PAYMENT,
            Transaction.transaction_date >= d_from, Transaction.transaction_date <= d_to,
        ).order_by(Transaction.transaction_date.asc())
        payments = list(self.db.execute(stmt).scalars().all())
        return {
            "date_from": d_from, "date_to": d_to, "total_payments": len(payments),
            "total_collected": sum((p.amount for p in payments), Decimal("0")),
            "payments": [{
                "id": p.id, "transaction_number": p.transaction_number, "tenant_id": p.tenant_id,
                "amount": p.amount, "payment_method": p.payment_method, "reference_number": p.reference_number,
                "transaction_date": p.transaction_date,
            } for p in payments],
        }

    def overdue_invoice_report(self) -> dict:
        from app.models.financial import Invoice, InvoiceStatus
        from sqlalchemy import select
        today = date.today()
        stmt = select(Invoice).where(
            Invoice.deleted_at.is_(None), Invoice.invoice_status.in_([InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
            Invoice.due_date < today,
        ).order_by(Invoice.due_date.asc())
        invoices = list(self.db.execute(stmt).scalars().all())
        return {
            "as_of_date": today, "total_overdue": len(invoices),
            "total_overdue_amount": sum((i.outstanding_amount for i in invoices), Decimal("0")),
            "invoices": [{
                "id": i.id, "invoice_number": i.invoice_number, "tenant_display_name": i.tenant_display_name,
                "property_title": i.property_title, "unit_number": i.unit_number, "due_date": i.due_date, "days_overdue": (today - i.due_date).days,
                "outstanding_amount": i.outstanding_amount,
            } for i in invoices],
        }

    # ---------------- Executive Reporting Center: genuinely missing reports ----------------
    def owner_balance_report(self) -> dict:
        """Owner Balance Report — every owner's current Owner Ledger
        balance in one list (the per-owner version already exists as
        Owner Statement, reached from an owner's own Ledger tab; this is
        the portfolio-wide list version that was missing). Reuses
        OwnerBalanceService.get_current_balance() as-is."""
        from app.models.owner import Owner
        from app.business_workflows.owner_ledger.owner_balance_service import OwnerBalanceService

        balance_service = OwnerBalanceService(self.db)
        owners = self.db.execute(select(Owner).where(Owner.deleted_at.is_(None))).scalars().all()
        rows = [{"id": o.id, "owner_code": o.owner_code, "display_name": o.display_name, "balance": balance_service.get_current_balance(o.id)} for o in owners]
        rows.sort(key=lambda r: r["balance"], reverse=True)
        return {
            "total_owners": len(rows),
            "total_balance": sum((r["balance"] for r in rows), Decimal("0")),
            "owners_owed_money": len([r for r in rows if r["balance"] > 0]),
            "owners_negative_balance": len([r for r in rows if r["balance"] < 0]),
            "rows": rows,
        }

    def tenant_ledger_report(self, tenant_id: Optional[int] = None) -> dict:
        """Tenant Ledger / Payment History / Statement — a tenant's full
        payment trail (or every tenant's, unfiltered) built directly from
        Transaction rows already in the ledger; no separate
        tenant-ledger table needed, same "the Transaction table IS the
        ledger" principle the rest of financial reporting in this
        codebase already follows."""
        from app.models.financial import Transaction
        from app.models.tenant import Tenant

        stmt = select(Transaction, Tenant).join(Tenant, Tenant.id == Transaction.tenant_id).where(
            Transaction.deleted_at.is_(None), Transaction.tenant_id.isnot(None),
        )
        if tenant_id:
            stmt = stmt.where(Transaction.tenant_id == tenant_id)
        stmt = stmt.order_by(Transaction.transaction_date.desc()).limit(500)
        rows = self.db.execute(stmt).all()
        total_paid = sum((t.amount for t, _ in rows if t.transaction_type == TransactionType.TENANT_PAYMENT), Decimal("0"))
        return {
            "scoped_to_tenant_id": tenant_id,
            "total_transactions": len(rows),
            "total_paid": total_paid,
            "rows": [
                {
                    "transaction_number": t.transaction_number, "date": t.transaction_date.isoformat(), "type": t.transaction_type,
                    "tenant_display_name": tenant.display_name, "amount": t.amount, "payment_method": t.payment_method, "description": t.description,
                }
                for t, tenant in rows
            ],
        }

    def security_deposit_report(self) -> dict:
        """Security Deposit Report — every active contract's deposit
        amount and status, straight from RentalContract (no separate
        deposit ledger to reconcile against — the field already lives
        on the contract)."""
        from app.models.rental import RentalContract, RentalContractStatus

        contracts = self.db.execute(
            select(RentalContract).where(RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE)
        ).scalars().all()
        rows = [
            {
                "contract_number": c.contract_number, "tenant_id": c.tenant_id, "property_id": c.property_id,
                "deposit_amount": c.security_deposit_amount, "deposit_status": c.security_deposit_status,
            }
            for c in contracts if c.security_deposit_amount
        ]
        return {
            "total_contracts_with_deposit": len(rows),
            "total_held": sum((r["deposit_amount"] for r in rows if r["deposit_status"] == "held"), Decimal("0")),
            "total_returned": sum((r["deposit_amount"] for r in rows if r["deposit_status"] == "returned"), Decimal("0")),
            "rows": rows,
        }

    def top_tenants_report(self, limit: int = 20) -> dict:
        """Ranks tenants by total paid (this calendar year) — "Payment
        Discipline" and "Contract Duration" from the brief need
        per-tenant on-time-vs-late history and contract date ranges,
        which the Tenant Ledger report (immediately above) already
        exposes per-tenant; ranking by revenue here keeps this report
        answering one clear question rather than conflating three
        different rankings into one ambiguous list."""
        from app.models.financial import Transaction, TransactionType
        from app.models.tenant import Tenant

        year_start = date(date.today().year, 1, 1)
        rows = self.db.execute(
            select(Tenant.id, Tenant.tenant_code, Tenant.first_name, Tenant.last_name, Tenant.company_name, func.coalesce(func.sum(Transaction.amount), 0).label("total_paid"), func.count(Transaction.id).label("payment_count"))
            .join(Transaction, Transaction.tenant_id == Tenant.id)
            .where(Transaction.transaction_type == TransactionType.TENANT_PAYMENT, Transaction.deleted_at.is_(None), Transaction.transaction_date >= year_start)
            .group_by(Tenant.id)
            .order_by(func.sum(Transaction.amount).desc())
            .limit(limit)
        ).all()
        return {
            "year": date.today().year,
            "rows": [
                {"id": r.id, "tenant_code": r.tenant_code, "display_name": r.company_name or f"{r.first_name or ''} {r.last_name or ''}".strip(), "total_paid": r.total_paid, "payment_count": r.payment_count}
                for r in rows
            ],
        }

    def repeated_late_payers_report(self, min_late_count: int = 2) -> dict:
        """Every tenant with 2+ installments that were ever marked
        overdue (regardless of whether they've since caught up) —
        answers "who has a pattern," not just "who owes right now"
        (that's the Outstanding report's job, immediately above)."""
        from app.models.rental import RentalPaymentInstallment, RentalContract, RentalInstallmentStatus
        from app.models.tenant import Tenant

        rows = self.db.execute(
            select(
                Tenant.id, Tenant.tenant_code, Tenant.first_name, Tenant.last_name, Tenant.company_name,
                func.count(RentalPaymentInstallment.id).label("late_count"),
                func.coalesce(func.sum(RentalPaymentInstallment.late_fee_amount), 0).label("total_late_fees"),
            )
            .select_from(RentalPaymentInstallment)
            .join(RentalContract, RentalContract.id == RentalPaymentInstallment.contract_id)
            .join(Tenant, Tenant.id == RentalContract.tenant_id)
            .where(
                RentalPaymentInstallment.deleted_at.is_(None),
                or_(RentalPaymentInstallment.payment_status == RentalInstallmentStatus.OVERDUE, RentalPaymentInstallment.late_fee_amount > 0),
            )
            .group_by(Tenant.id)
            .having(func.count(RentalPaymentInstallment.id) >= min_late_count)
            .order_by(func.count(RentalPaymentInstallment.id).desc())
        ).all()
        return {
            "min_late_count": min_late_count,
            "total_tenants": len(rows),
            "rows": [
                {"id": r.id, "tenant_code": r.tenant_code, "display_name": r.company_name or f"{r.first_name or ''} {r.last_name or ''}".strip(), "late_count": r.late_count, "total_late_fees": r.total_late_fees}
                for r in rows
            ],
        }

    def renewed_contracts_report(self) -> dict:
        """Renewed Contracts — every contract that was itself a renewal
        of an earlier one, via the existing renewed_from_contract_id
        link (Rent Cycle Engine's renewal flow already sets this; no new
        field needed)."""
        from app.models.rental import RentalContract

        renewed = self.db.execute(
            select(RentalContract).where(RentalContract.deleted_at.is_(None), RentalContract.renewed_from_contract_id.isnot(None))
        ).scalars().all()
        rows = [
            {
                "contract_number": c.contract_number, "renewed_from_contract_id": c.renewed_from_contract_id,
                "tenant_id": c.tenant_id, "start_date": c.start_date.isoformat(), "end_date": c.end_date.isoformat(), "rent_amount": c.rent_amount,
            }
            for c in renewed
        ]
        return {"total_renewed": len(rows), "rows": rows}


# ---------------- Enterprise Reporting extension: generic dispatch + export ----------------
# The 10 report categories this phase requires, mapped to the methods
# above (5 of which already existed from Phase 11; 5 are new — see
# lease_report/maintenance_report/collections_report/outstanding_report/
# contract_expiration_report). This registry is what lets a single
# generic export endpoint and a single ReportSchedule entity serve every
# report type without one export endpoint per report.
REPORT_TYPES = [
    "property", "owner", "tenant", "lease", "occupancy", "units",
    "financial", "maintenance", "collections", "outstanding", "contract_expiration",
    "owner_balance", "tenant_ledger", "security_deposit", "renewed_contracts",
    "top_tenants", "repeated_late_payers",
]


def generate_report(service: "ReportsService", report_type: str, filters: dict) -> dict:
    """Dispatches to the correct existing report method by name. `filters`
    keys are passed through as keyword arguments where the target method
    accepts them; unrecognized filter keys are ignored rather than
    raising, so a schedule's saved filters remain valid even if a future
    change adds/removes a parameter on one report method."""
    import inspect

    method_map = {
        "property": service.property_report,
        "owner": service.owner_report,
        "tenant": service.tenant_report,
        "lease": service.lease_report,
        "occupancy": service.occupancy_report,
        "units": service.units_report,
        "financial": service.financial_report,
        "maintenance": service.maintenance_report,
        "collections": service.collections_report,
        "outstanding": service.outstanding_report,
        "contract_expiration": service.contract_expiration_report,
        "owner_balance": service.owner_balance_report,
        "tenant_ledger": service.tenant_ledger_report,
        "security_deposit": service.security_deposit_report,
        "renewed_contracts": service.renewed_contracts_report,
        "top_tenants": service.top_tenants_report,
        "repeated_late_payers": service.repeated_late_payers_report,
    }
    if report_type not in method_map:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown report_type '{report_type}'. Valid types: {REPORT_TYPES}")
    method = method_map[report_type]
    accepted = set(inspect.signature(method).parameters.keys())
    kwargs = {k: v for k, v in (filters or {}).items() if k in accepted and v is not None}
    return method(**kwargs)


def report_title(report_type: str) -> str:
    return {
        "property": "Property Report", "owner": "Owner Report", "tenant": "Tenant Report",
        "lease": "Lease Report", "occupancy": "Occupancy Report", "units": "Unit Status & Availability Report", "financial": "Financial Report",
        "maintenance": "Maintenance Report", "collections": "Collections Report",
        "outstanding": "Outstanding Report", "contract_expiration": "Contract Expiration Report",
        "owner_balance": "Owner Balance Report", "tenant_ledger": "Tenant Ledger Report",
        "security_deposit": "Security Deposit Report", "renewed_contracts": "Renewed Contracts Report",
        "top_tenants": "Top Tenants Report", "repeated_late_payers": "Repeated Late Payers Report",
    }.get(report_type, report_type.replace("_", " ").title())


def report_to_document(report_type: str, data: dict):
    """Converts one of the 10 report dicts above into the generic
    ReportDocument shape that report_export_service renders to PDF/
    Excel. This is the only place that needs to know both "what a
    Property Report contains" and "what ReportDocument looks like" —
    report_export_service itself stays completely report-agnostic."""
    from app.services.report_export_service import ReportDocument, ReportSummary, ReportTable

    title = report_title(report_type)
    doc = ReportDocument(title=title)

    if report_type == "property":
        doc.summaries.append(ReportSummary("Overview", [("Total Properties", data["total_properties"])]))
        doc.tables.append(ReportTable("By Type", ["Property Type", "Count"], [[t["property_type"], t["count"]] for t in data["by_type"]]))
        doc.tables.append(ReportTable("By Availability", ["Status", "Count"], [[a["availability_status"], a["count"]] for a in data["by_availability"]]))
        doc.tables.append(ReportTable("Top Properties by Revenue", ["Code", "Property", "Revenue"], [[p["property_code"], p["property_title"], p["total_amount"]] for p in data["top_properties_by_revenue"]]))

    elif report_type == "owner":
        doc.summaries.append(ReportSummary("Overview", [
            ("Total Owners", data["total_owners"]), ("Individual", data["individual_owners"]), ("Company", data["company_owners"]),
            ("Paid to Owners", data["total_paid_to_owners"]),
        ]))
        doc.tables.append(ReportTable("Top Owners by Properties", ["Owner", "Properties"], [[o["display_name"], o["property_count"]] for o in data["top_owners_by_properties"]]))
        doc.tables.append(ReportTable("Outstanding Payables", ["Owner", "Outstanding"], [[o["display_name"], o["outstanding_amount"]] for o in data["outstanding_owners"]]))

    elif report_type == "tenant":
        doc.summaries.append(ReportSummary("Overview", [
            ("Total Tenants", data["total_tenants"]), ("Individual", data["individual_tenants"]), ("Company", data["company_tenants"]),
            ("Blacklisted", data["blacklisted_tenants"]), ("Contracts Expiring Soon", data["contracts_expiring_soon"]),
        ]))
        doc.tables.append(ReportTable("Top Tenants by Payment", ["Tenant", "Total Paid", "Payments"], [[t["display_name"], t["total_paid"], t["payment_count"]] for t in data["top_tenants_by_payment"]]))
        doc.tables.append(ReportTable("Outstanding Balances", ["Tenant", "Outstanding"], [[t["display_name"], t["outstanding_amount"]] for t in data["outstanding_tenants"]]))

    elif report_type == "lease":
        doc.tables.append(ReportTable("Rental Contracts by Status", ["Status", "Count", "Total Rent"], [[s["status"], s["count"], s["total_rent"]] for s in data["rental_contracts_by_status"]]))
        doc.tables.append(ReportTable("Lease Agreements by Status", ["Status", "Count", "Total Rent"], [[s["status"], s["count"], s["total_rent"]] for s in data["lease_agreements_by_status"]]))
        doc.tables.append(ReportTable("Rental Contracts", ["Contract #", "Tenant", "Property", "End Date", "Rent", "Status"],
                                       [[c["contract_number"], c["tenant_display_name"], c["property_title"], c["end_date"], c["rent_amount"], c["contract_status"]] for c in data["rental_contracts"]]))
        doc.tables.append(ReportTable("Lease Agreements", ["Contract #", "Owner", "Property", "End Date", "Rent", "Status"],
                                       [[c["contract_number"], c["owner_display_name"], c["property_title"], c["end_date"], c["rent_amount"], c["contract_status"]] for c in data["lease_agreements"]]))

    elif report_type == "occupancy":
        doc.summaries.append(ReportSummary("Overview", [("Overall Occupancy Rate", f"{data['overall_occupancy_rate_percentage']}%"), ("As Of", data["as_of_date"])]))
        doc.tables.append(ReportTable("By Property Type", ["Type", "Total", "Occupied", "Rate %"], [[t["property_type"], t["total"], t["occupied"], t["occupancy_rate_percentage"]] for t in data["by_property_type"]]))
        doc.tables.append(ReportTable("6-Month Trend", ["Month", "Occupancy Rate %"], [[t["month"], t["occupancy_rate_percentage"]] for t in data["trend"]]))

    elif report_type == "units":
        doc.summaries.append(ReportSummary("Overview", [
            ("Scope", data["scoped_to_property_title"] or "All Properties"), ("Total Units", data["total_units"]),
            ("Vacant", data["vacant_count"]), ("Occupied", data["occupied_count"]),
            ("Reserved", data["reserved_count"]), ("Under Maintenance", data["under_maintenance_count"]),
        ]))
        doc.tables.append(ReportTable("By Status", ["Status", "Count"], [[s["availability_status"], s["count"]] for s in data["by_status"]]))
        doc.tables.append(ReportTable("By Type", ["Type", "Count"], [[t["property_type"], t["count"]] for t in data["by_type"]]))
        doc.tables.append(ReportTable(
            "Units", ["Code", "Title", "Type", "Status", "Building/Villa", "Unit #", "Rent Price"],
            [[u["property_code"], u["title"], u["property_type"], u["availability_status"], u["building_title"] or "—", u["unit_number"] or "—", u["rent_price"]] for u in data["units"]],
        ))

    elif report_type == "financial":
        doc.summaries.append(ReportSummary("Overview", [
            ("Total Income", data["total_income"]), ("Total Expense", data["total_expense"]), ("Net Cash Flow", data["net_cash_flow"]),
            ("Outstanding (Tenant)", data["total_outstanding_tenant"]), ("Outstanding (Owner)", data["total_outstanding_owner"]),
            ("Collection Rate", f"{data['collection_rate_percentage']}%"),
        ]))
        doc.tables.append(ReportTable("Transactions by Type", ["Type", "Total", "Count"], [[t["label"], t["total_amount"], t["count"]] for t in data["transactions_by_type"]]))

    elif report_type == "maintenance":
        doc.summaries.append(ReportSummary("Overview", [
            ("Total Requests", data["total_requests"]), ("Total Cost", data["total_cost"]),
            ("Avg. Resolution (days)", data["average_resolution_days"]),
        ]))
        doc.tables.append(ReportTable("By Status", ["Status", "Count"], [[s["status"], s["count"]] for s in data["by_status"]]))
        doc.tables.append(ReportTable("By Priority", ["Priority", "Count"], [[p["priority"], p["count"]] for p in data["by_priority"]]))
        doc.tables.append(ReportTable("Requests", ["Request #", "Title", "Property", "Priority", "Status", "Reported", "Cost"],
                                       [[r["request_number"], r["title"], r["property_title"], r["priority"], r["maintenance_status"], r["reported_date"], r["total_actual_cost"]] for r in data["requests"]]))

    elif report_type == "collections":
        doc.summaries.append(ReportSummary("Overview", [
            ("Total Due", data["total_due"]), ("Total Collected", data["total_collected"]), ("Collection Rate", f"{data['collection_rate_percentage']}%"),
        ]))
        doc.tables.append(ReportTable("Monthly Trend", ["Month", "Due", "Collected", "Rate %"], [[m["month"], m["due"], m["collected"], m["collection_rate_percentage"]] for m in data["monthly_trend"]]))
        doc.tables.append(ReportTable("By Property", ["Property", "Due", "Collected", "Rate %"], [[p["property_title"], p["due"], p["collected"], p["collection_rate_percentage"]] for p in data["by_property"]]))

    elif report_type == "outstanding":
        doc.summaries.append(ReportSummary("Overview", [
            ("Tenant Outstanding", data["tenant_outstanding_total"]), ("Owner Outstanding", data["owner_outstanding_total"]), ("As Of", data["as_of_date"]),
        ]))
        aging_rows_t = [[k.replace("_", " "), v] for k, v in data["tenant_aging"].items()]
        aging_rows_o = [[k.replace("_", " "), v] for k, v in data["owner_aging"].items()]
        doc.tables.append(ReportTable("Tenant Aging", ["Bucket", "Amount"], aging_rows_t))
        doc.tables.append(ReportTable("Owner Aging", ["Bucket", "Amount"], aging_rows_o))
        doc.tables.append(ReportTable("Outstanding Tenants", ["Tenant", "Outstanding"], [[t["display_name"], t["outstanding_amount"]] for t in data["tenant_outstanding_list"]]))
        doc.tables.append(ReportTable("Outstanding Owners", ["Owner", "Outstanding"], [[o["display_name"], o["outstanding_amount"]] for o in data["owner_outstanding_list"]]))

    elif report_type == "contract_expiration":
        doc.summaries.append(ReportSummary("Overview", [("Total Expiring", data["total_expiring"]), ("Window (days)", data["window_days"]), ("As Of", data["as_of_date"])]))
        doc.tables.append(ReportTable("Expiring Rental Contracts", ["Contract #", "Tenant", "Property", "End Date", "Days Left", "Rent"],
                                       [[c["contract_number"], c["tenant_display_name"], c["property_title"], c["end_date"], c["days_remaining"], c["rent_amount"]] for c in data["expiring_rental_contracts"]]))
        doc.tables.append(ReportTable("Expiring Lease Agreements", ["Contract #", "Owner", "Property", "End Date", "Days Left", "Rent"],
                                       [[c["contract_number"], c["owner_display_name"], c["property_title"], c["end_date"], c["days_remaining"], c["rent_amount"]] for c in data["expiring_lease_agreements"]]))

    elif report_type == "owner_balance":
        doc.summaries.append(ReportSummary("Overview", [
            ("Total Owners", data["total_owners"]), ("Total Balance", data["total_balance"]),
            ("Owed Money", data["owners_owed_money"]), ("Negative Balance", data["owners_negative_balance"]),
        ]))
        doc.tables.append(ReportTable("Owner Balances", ["Code", "Owner", "Balance"], [[r["owner_code"], r["display_name"], r["balance"]] for r in data["rows"]]))

    elif report_type == "tenant_ledger":
        doc.summaries.append(ReportSummary("Overview", [("Transactions", data["total_transactions"]), ("Total Paid", data["total_paid"])]))
        doc.tables.append(ReportTable("Transactions", ["Date", "Transaction #", "Type", "Tenant", "Amount", "Method"],
                                       [[r["date"], r["transaction_number"], r["type"], r["tenant_display_name"], r["amount"], r["payment_method"] or "—"] for r in data["rows"]]))

    elif report_type == "security_deposit":
        doc.summaries.append(ReportSummary("Overview", [
            ("Contracts With Deposit", data["total_contracts_with_deposit"]), ("Total Held", data["total_held"]), ("Total Returned", data["total_returned"]),
        ]))
        doc.tables.append(ReportTable("Deposits", ["Contract #", "Amount", "Status"], [[r["contract_number"], r["deposit_amount"], r["deposit_status"]] for r in data["rows"]]))

    elif report_type == "renewed_contracts":
        doc.summaries.append(ReportSummary("Overview", [("Total Renewed", data["total_renewed"])]))
        doc.tables.append(ReportTable("Renewed Contracts", ["Contract #", "Start", "End", "Rent"], [[r["contract_number"], r["start_date"], r["end_date"], r["rent_amount"]] for r in data["rows"]]))

    elif report_type == "top_tenants":
        doc.summaries.append(ReportSummary("Overview", [("Year", data["year"])]))
        doc.tables.append(ReportTable("Top Tenants by Revenue", ["Code", "Tenant", "Total Paid", "Payments"], [[r["tenant_code"], r["display_name"], r["total_paid"], r["payment_count"]] for r in data["rows"]]))

    elif report_type == "repeated_late_payers":
        doc.summaries.append(ReportSummary("Overview", [("Tenants Flagged", data["total_tenants"]), ("Threshold", f"{data['min_late_count']}+ late installments")]))
        doc.tables.append(ReportTable("Repeated Late Payers", ["Code", "Tenant", "Late Count", "Total Late Fees"], [[r["tenant_code"], r["display_name"], r["late_count"], r["total_late_fees"]] for r in data["rows"]]))

    return doc


# ---------------- Export Scheduling ----------------
class ReportScheduleService:
    """CRUD for saved recurring report configurations, plus running one
    on demand — reuses generate_report()/report_to_document() above and
    the existing Attachment/FileUploadService machinery for storing the
    generated file (the exact same pattern AttachmentService already
    uses for uploads, just with generated bytes instead of an UploadFile).

    No SMTP integration exists in this codebase, so "running" a schedule
    does not email anyone — it generates and stores the export for
    download, and stamps last_run_at/next_run_at. See app/models/reports.py
    for the full honest scope note.
    """
    def __init__(self, db: Session):
        self.db = db
        from app.repositories.reports_repository import ReportScheduleRepository
        self.repo = ReportScheduleRepository(db)

    def _compute_next_run(self, frequency: str, from_time: Optional["datetime"] = None) -> "datetime":
        from datetime import datetime, timedelta as _timedelta
        from app.models.reports import ReportFrequency
        base = from_time or datetime.utcnow()
        if frequency == ReportFrequency.DAILY:
            return base + _timedelta(days=1)
        if frequency == ReportFrequency.WEEKLY:
            return base + _timedelta(weeks=1)
        return base + _timedelta(days=30)  # monthly, approximated as 30 days (no calendar-month library dependency needed)

    def list_schedules(self, is_active: Optional[bool] = None):
        return self.repo.list_all(is_active)

    def get_schedule(self, schedule_id: int):
        schedule = self.repo.get(schedule_id)
        if not schedule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report schedule not found")
        return schedule

    def create_schedule(self, data: dict, actor_id: Optional[int]):
        if data["report_type"] not in REPORT_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid report_type. Valid types: {REPORT_TYPES}")
        payload = dict(data)
        payload.setdefault("next_run_at", self._compute_next_run(data.get("frequency", "monthly")))
        schedule = self.repo.create(payload, actor_id=actor_id)
        self.db.commit()
        return schedule

    def update_schedule(self, schedule_id: int, data: dict, actor_id: Optional[int]):
        schedule = self.get_schedule(schedule_id)
        if data.get("report_type") and data["report_type"] not in REPORT_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid report_type. Valid types: {REPORT_TYPES}")
        self.repo.update(schedule, data, actor_id=actor_id)
        self.db.commit()
        return schedule

    def delete_schedule(self, schedule_id: int, actor_id: Optional[int]):
        schedule = self.get_schedule(schedule_id)
        self.repo.soft_delete(schedule, actor_id=actor_id)
        self.db.commit()

    def run_schedule(self, schedule_id: int, actor_id: Optional[int]):
        schedule = self.get_schedule(schedule_id)
        return self._execute(schedule, actor_id)

    def run_due_schedules(self, actor_id: Optional[int] = None) -> list:
        due = self.repo.list_due()
        return [self._execute(s, actor_id) for s in due]

    def _execute(self, schedule, actor_id: Optional[int]):
        from datetime import datetime
        from app.models.reports import ReportExportFormat
        from app.repositories.system_repository import AttachmentRepository
        from app.services.file_storage_service import FileUploadService
        from app.services.report_export_service import render_pdf, render_excel

        service = ReportsService(self.db)
        data = generate_report(service, schedule.report_type, schedule.filters or {})
        doc = report_to_document(schedule.report_type, data)

        if schedule.export_format == ReportExportFormat.EXCEL:
            file_bytes = render_excel(doc)
            file_name = f"{schedule.report_type}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.xlsx"
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            file_bytes = render_pdf(doc)
            file_name = f"{schedule.report_type}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.pdf"
            mime_type = "application/pdf"

        uploader = FileUploadService()
        meta = uploader.save_generated_bytes(file_bytes, file_name, mime_type, "report_schedule", schedule.id)
        meta["entity_type"] = "report_schedule"
        meta["entity_id"] = schedule.id
        meta["description"] = f"Scheduled export: {report_title(schedule.report_type)} ({schedule.export_format})"
        attachment = AttachmentRepository(self.db).create(meta, actor_id=actor_id)
        self.db.flush()

        schedule.last_run_at = datetime.utcnow()
        schedule.next_run_at = self._compute_next_run(schedule.frequency, schedule.last_run_at)
        schedule.last_export_attachment_id = attachment.id
        self.db.commit()
        return schedule
