"""
Phase 11 report aggregation queries. Everything here reads from existing
tables (Property, Tenant, Owner, RentalContract/LeaseAgreement +
installments, Transaction, MaintenanceRequest + costs) — nothing is
stored. Property-type "building" rows (and, per Phase 2.0,
"commercial_building"/"commercial_complex", which are the same kind of
pure multi-unit container) are excluded from vacancy/occupancy math since
they're parent containers for units (Phase 4/5 design), not directly
leasable space themselves. "villa"/"warehouse"/"land"/"mixed_use" are
NOT excluded — like villa always was, these can equally be leased whole
to one tenant OR subdivided into units, so their own availability_status
is meaningful and should count.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy import select, func, case, extract
from sqlalchemy.orm import Session

from app.models.property import Property
from app.models.tenant import Tenant
from app.models.owner import Owner
from app.models.rental import RentalContract, RentalContractStatus, RentalPaymentInstallment, RentalInstallmentStatus
from app.models.lease import LeaseAgreement, LeaseStatus, LeasePaymentInstallment, InstallmentStatus
from app.models.financial import Transaction, TransactionType, TransactionStatus
from app.models.maintenance import MaintenanceRequest, MaintenanceRequestStatus, MaintenanceMaterial, MaintenanceLaborCost, Contractor
from app.models.reports import ReportSchedule
from app.repositories.base import BaseRepository

# "floor" is the virtual "whole floor, leased as one contract" Property
# row (see PropertyService.get_or_create_floor_unit) — not a real
# building/container, but not a real leasable unit either, since its
# own child units are already counted individually. Left out of this
# list before, which double-counted it in Reports' Properties/Vacancy
# widgets the same way PropertyRepository.dashboard_counts and
# OccupancyStatisticsService._all_unit_ids were double-counting it
# elsewhere (both already fixed) — this is that same bug's third,
# entirely separate implementation in the Reports module.
NON_LEASABLE_TYPES = ["building", "commercial_building", "commercial_complex", "floor"]
INCOME_TYPES = [TransactionType.TENANT_PAYMENT, TransactionType.INCOME]
EXPENSE_TYPES = [TransactionType.OWNER_PAYMENT, TransactionType.EXPENSE]


class ReportsRepository:
    def __init__(self, db: Session):
        self.db = db

    # ---------------- Financial ----------------
    def total_amount(self, types: list[str], date_from: Optional[date], date_to: Optional[date], property_id: Optional[int] = None) -> Decimal:
        if property_id:
            resolved_property_id = func.coalesce(Transaction.property_id, RentalContract.property_id)
            stmt = (
                select(func.coalesce(func.sum(Transaction.amount), 0))
                .select_from(Transaction)
                .outerjoin(RentalContract, RentalContract.id == Transaction.rental_contract_id)
                .where(
                    Transaction.deleted_at.is_(None), Transaction.transaction_status == TransactionStatus.COMPLETED,
                    Transaction.transaction_type.in_(types), resolved_property_id == property_id,
                )
            )
        else:
            stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.deleted_at.is_(None), Transaction.transaction_status == TransactionStatus.COMPLETED,
                Transaction.transaction_type.in_(types),
            )
        if date_from:
            stmt = stmt.where(Transaction.transaction_date >= date_from)
        if date_to:
            stmt = stmt.where(Transaction.transaction_date <= date_to)
        return self.db.execute(stmt).scalar_one()

    def transactions_by_type(self, date_from: Optional[date], date_to: Optional[date]) -> list[dict]:
        stmt = select(
            Transaction.transaction_type,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            func.count().label("cnt"),
        ).where(Transaction.deleted_at.is_(None), Transaction.transaction_status == TransactionStatus.COMPLETED)
        if date_from:
            stmt = stmt.where(Transaction.transaction_date >= date_from)
        if date_to:
            stmt = stmt.where(Transaction.transaction_date <= date_to)
        stmt = stmt.group_by(Transaction.transaction_type).order_by(Transaction.transaction_type)
        rows = self.db.execute(stmt).all()
        return [{"label": r.transaction_type, "total_amount": r.total, "count": r.cnt} for r in rows]

    def tenant_outstanding_total(self) -> Decimal:
        # Only installments actually due as of today — not every future,
        # not-yet-due installment a multi-month contract already created
        # upfront. Same fix applied everywhere this pattern repeats in
        # this file and in financial_repository.py.
        stmt = select(func.coalesce(func.sum(
            RentalPaymentInstallment.amount - RentalPaymentInstallment.discount_amount
            + RentalPaymentInstallment.tax_amount + RentalPaymentInstallment.late_fee_amount
        ), 0)).where(
            RentalPaymentInstallment.payment_status.in_([RentalInstallmentStatus.PENDING, RentalInstallmentStatus.OVERDUE]),
            RentalPaymentInstallment.due_date <= date.today(),
            RentalPaymentInstallment.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one()

    def tenant_outstanding_total_for_property(self, property_id: int) -> Decimal:
        stmt = (
            select(func.coalesce(func.sum(
                RentalPaymentInstallment.amount - RentalPaymentInstallment.discount_amount
                + RentalPaymentInstallment.tax_amount + RentalPaymentInstallment.late_fee_amount
            ), 0))
            .select_from(RentalPaymentInstallment)
            .join(RentalContract, RentalContract.id == RentalPaymentInstallment.contract_id)
            .where(
                RentalPaymentInstallment.payment_status.in_([RentalInstallmentStatus.PENDING, RentalInstallmentStatus.OVERDUE]),
                RentalPaymentInstallment.due_date <= date.today(),
                RentalPaymentInstallment.deleted_at.is_(None), RentalContract.property_id == property_id,
            )
        )
        return self.db.execute(stmt).scalar_one()

    def owner_outstanding_total(self) -> Decimal:
        stmt = select(func.coalesce(func.sum(LeasePaymentInstallment.amount), 0)).where(
            LeasePaymentInstallment.payment_status.in_([InstallmentStatus.PENDING, InstallmentStatus.OVERDUE]),
            LeasePaymentInstallment.due_date <= date.today(),
            LeasePaymentInstallment.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one()

    def collection_rate(self, date_from: Optional[date], date_to: Optional[date]) -> Decimal:
        stmt = select(
            func.coalesce(func.sum(RentalPaymentInstallment.amount), 0),
            func.coalesce(func.sum(case((RentalPaymentInstallment.payment_status == RentalInstallmentStatus.PAID, RentalPaymentInstallment.amount), else_=0)), 0),
        ).where(RentalPaymentInstallment.deleted_at.is_(None))
        if date_from:
            stmt = stmt.where(RentalPaymentInstallment.due_date >= date_from)
        if date_to:
            stmt = stmt.where(RentalPaymentInstallment.due_date <= date_to)
        due, paid = self.db.execute(stmt).one()
        if due == 0:
            return Decimal("0")
        return (paid / due * 100).quantize(Decimal("0.01"))

    # ---------------- Tenant ----------------
    def tenant_counts(self) -> dict:
        total = self.db.execute(select(func.count()).select_from(Tenant).where(Tenant.deleted_at.is_(None))).scalar_one()
        individual = self.db.execute(select(func.count()).select_from(Tenant).where(Tenant.deleted_at.is_(None), Tenant.tenant_type == "individual")).scalar_one()
        company = self.db.execute(select(func.count()).select_from(Tenant).where(Tenant.deleted_at.is_(None), Tenant.tenant_type == "company")).scalar_one()
        blacklisted = self.db.execute(select(func.count()).select_from(Tenant).where(Tenant.deleted_at.is_(None), Tenant.is_blacklisted.is_(True))).scalar_one()
        return {"total": total, "individual": individual, "company": company, "blacklisted": blacklisted}

    def top_tenants_by_payment(self, date_from: Optional[date], date_to: Optional[date], limit: int = 5) -> list[dict]:
        stmt = (
            select(
                Tenant.id, Tenant.first_name, Tenant.last_name, Tenant.company_name, Tenant.tenant_type,
                func.coalesce(func.sum(Transaction.amount), 0).label("total_paid"), func.count().label("cnt"),
            )
            .join(Transaction, Transaction.tenant_id == Tenant.id)
            .where(
                Transaction.deleted_at.is_(None), Transaction.transaction_status == TransactionStatus.COMPLETED,
                Transaction.transaction_type == TransactionType.TENANT_PAYMENT, Tenant.deleted_at.is_(None),
            )
        )
        if date_from:
            stmt = stmt.where(Transaction.transaction_date >= date_from)
        if date_to:
            stmt = stmt.where(Transaction.transaction_date <= date_to)
        stmt = stmt.group_by(Tenant.id, Tenant.first_name, Tenant.last_name, Tenant.company_name, Tenant.tenant_type)
        stmt = stmt.order_by(func.coalesce(func.sum(Transaction.amount), 0).desc()).limit(limit)
        rows = self.db.execute(stmt).all()
        results = []
        for r in rows:
            name = r.company_name if r.tenant_type == "company" else f"{r.first_name or ''} {r.last_name or ''}".strip()
            results.append({"tenant_id": r.id, "display_name": name or f"Tenant #{r.id}", "total_paid": r.total_paid, "payment_count": r.cnt})
        return results

    def tenant_outstanding_list(self, limit: int = 10) -> list[dict]:
        stmt = (
            select(
                Tenant.id, Tenant.first_name, Tenant.last_name, Tenant.company_name, Tenant.tenant_type,
                func.coalesce(func.sum(
                    RentalPaymentInstallment.amount - RentalPaymentInstallment.discount_amount
                    + RentalPaymentInstallment.tax_amount + RentalPaymentInstallment.late_fee_amount
                ), 0).label("outstanding"),
            )
            .join(RentalContract, RentalContract.tenant_id == Tenant.id)
            .join(RentalPaymentInstallment, RentalPaymentInstallment.contract_id == RentalContract.id)
            .where(
                RentalPaymentInstallment.payment_status.in_([RentalInstallmentStatus.PENDING, RentalInstallmentStatus.OVERDUE]),
                RentalPaymentInstallment.due_date <= date.today(),
                RentalPaymentInstallment.deleted_at.is_(None), Tenant.deleted_at.is_(None),
            )
            .group_by(Tenant.id, Tenant.first_name, Tenant.last_name, Tenant.company_name, Tenant.tenant_type)
            .having(func.coalesce(func.sum(
                RentalPaymentInstallment.amount - RentalPaymentInstallment.discount_amount
                + RentalPaymentInstallment.tax_amount + RentalPaymentInstallment.late_fee_amount
            ), 0) > 0)
            .order_by(func.coalesce(func.sum(RentalPaymentInstallment.amount), 0).desc())
            .limit(limit)
        )
        rows = self.db.execute(stmt).all()
        results = []
        for r in rows:
            name = r.company_name if r.tenant_type == "company" else f"{r.first_name or ''} {r.last_name or ''}".strip()
            results.append({"tenant_id": r.id, "display_name": name or f"Tenant #{r.id}", "outstanding_amount": r.outstanding})
        return results

    def contracts_expiring_soon_count(self, days: int = 30) -> int:
        today = date.today()
        stmt = select(func.count()).select_from(RentalContract).where(
            RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE,
            RentalContract.end_date >= today, RentalContract.end_date <= today + timedelta(days=days),
        )
        return self.db.execute(stmt).scalar_one()

    def average_tenant_rating(self) -> Optional[Decimal]:
        from app.models.tenant import TenantRating
        stmt = select(func.avg(TenantRating.rating)).where(TenantRating.deleted_at.is_(None))
        result = self.db.execute(stmt).scalar_one()
        return Decimal(str(round(result, 2))) if result is not None else None

    # ---------------- Owner ----------------
    def owner_counts(self) -> dict:
        total = self.db.execute(select(func.count()).select_from(Owner).where(Owner.deleted_at.is_(None))).scalar_one()
        individual = self.db.execute(select(func.count()).select_from(Owner).where(Owner.deleted_at.is_(None), Owner.owner_type == "individual")).scalar_one()
        company = self.db.execute(select(func.count()).select_from(Owner).where(Owner.deleted_at.is_(None), Owner.owner_type == "company")).scalar_one()
        return {"total": total, "individual": individual, "company": company}

    def top_owners_by_properties(self, limit: int = 5) -> list[dict]:
        stmt = (
            select(
                Owner.id, Owner.first_name, Owner.last_name, Owner.company_name, Owner.owner_type,
                func.count(Property.id).label("cnt"),
            )
            .join(Property, Property.owner_id == Owner.id)
            .where(Owner.deleted_at.is_(None), Property.deleted_at.is_(None))
            .group_by(Owner.id, Owner.first_name, Owner.last_name, Owner.company_name, Owner.owner_type)
            .order_by(func.count(Property.id).desc())
            .limit(limit)
        )
        rows = self.db.execute(stmt).all()
        results = []
        for r in rows:
            name = r.company_name if r.owner_type == "company" else f"{r.first_name or ''} {r.last_name or ''}".strip()
            results.append({"owner_id": r.id, "display_name": name or f"Owner #{r.id}", "property_count": r.cnt})
        return results

    def owner_outstanding_list(self, limit: int = 10) -> list[dict]:
        stmt = (
            select(
                Owner.id, Owner.first_name, Owner.last_name, Owner.company_name, Owner.owner_type,
                func.coalesce(func.sum(LeasePaymentInstallment.amount), 0).label("outstanding"),
            )
            .join(LeaseAgreement, LeaseAgreement.owner_id == Owner.id)
            .join(LeasePaymentInstallment, LeasePaymentInstallment.lease_id == LeaseAgreement.id)
            .where(
                LeasePaymentInstallment.payment_status.in_([InstallmentStatus.PENDING, InstallmentStatus.OVERDUE]),
                LeasePaymentInstallment.due_date <= date.today(),
                LeasePaymentInstallment.deleted_at.is_(None), Owner.deleted_at.is_(None),
            )
            .group_by(Owner.id, Owner.first_name, Owner.last_name, Owner.company_name, Owner.owner_type)
            .having(func.coalesce(func.sum(LeasePaymentInstallment.amount), 0) > 0)
            .order_by(func.coalesce(func.sum(LeasePaymentInstallment.amount), 0).desc())
            .limit(limit)
        )
        rows = self.db.execute(stmt).all()
        results = []
        for r in rows:
            name = r.company_name if r.owner_type == "company" else f"{r.first_name or ''} {r.last_name or ''}".strip()
            results.append({"owner_id": r.id, "display_name": name or f"Owner #{r.id}", "outstanding_amount": r.outstanding})
        return results

    # ---------------- Property ----------------
    def property_counts_by_type(self) -> list[dict]:
        stmt = select(Property.property_type, func.count()).where(Property.deleted_at.is_(None)).group_by(Property.property_type).order_by(Property.property_type)
        return [{"property_type": r[0], "count": r[1]} for r in self.db.execute(stmt).all()]

    def property_counts_by_status(self) -> list[dict]:
        stmt = select(Property.availability_status, func.count()).where(Property.deleted_at.is_(None)).group_by(Property.availability_status).order_by(Property.availability_status)
        return [{"availability_status": r[0], "count": r[1]} for r in self.db.execute(stmt).all()]

    def total_properties(self) -> int:
        # Same FLOOR exclusion as NON_LEASABLE_TYPES above and
        # PropertyRepository.dashboard_counts's "Total Properties" — this
        # widget must match Buildings + Villas + ... + Total Units, which
        # it silently didn't while FLOOR rows were counted here too.
        from app.models.property import PropertyType
        return self.db.execute(
            select(func.count()).select_from(Property).where(
                Property.deleted_at.is_(None), Property.property_type != PropertyType.FLOOR,
            )
        ).scalar_one()

    def top_properties_by_revenue(self, date_from: Optional[date], date_to: Optional[date], limit: int = 5) -> list[dict]:
        return self.amount_by_property(INCOME_TYPES, date_from, date_to, limit)

    # ---------------- Vacancy & Occupancy ----------------
    def vacancy_counts(self) -> dict:
        base = select(func.count()).select_from(Property).where(Property.deleted_at.is_(None), Property.property_type.notin_(NON_LEASABLE_TYPES))
        total = self.db.execute(base).scalar_one()
        vacant = self.db.execute(base.where(Property.availability_status == "available")).scalar_one()
        leased = self.db.execute(base.where(Property.availability_status == "leased")).scalar_one()
        other = total - vacant - leased
        return {"total": total, "vacant": vacant, "leased": leased, "other": other}

    def vacant_properties(self, limit: int = 50) -> list[dict]:
        stmt = select(Property).where(
            Property.deleted_at.is_(None), Property.property_type.notin_(NON_LEASABLE_TYPES), Property.availability_status == "available",
        ).order_by(Property.updated_at.asc()).limit(limit)
        properties = list(self.db.execute(stmt).scalars().all())
        results = []
        today = date.today()
        for p in properties:
            # Was just the max end_date before ("Vacancy Duration" from
            # the brief) — now also pulls that same most-recent
            # contract's own row for "Last Tenant" / "Last Rent Amount"
            # (the brief's other two fields for this report), one query
            # instead of two.
            last_contract_stmt = (
                select(RentalContract)
                .where(RentalContract.property_id == p.id, RentalContract.deleted_at.is_(None))
                .order_by(RentalContract.end_date.desc())
                .limit(1)
            )
            last_contract = self.db.execute(last_contract_stmt).scalar_one_or_none()
            last_end = last_contract.end_date if last_contract else None
            reference_date = last_end if last_end else p.created_at.date()
            days_vacant = max((today - reference_date).days, 0)
            last_tenant = None
            if last_contract:
                tenant = self.db.get(Tenant, last_contract.tenant_id)
                last_tenant = tenant.display_name if tenant else None
            results.append({
                "property_id": p.id, "property_code": p.property_code, "title": p.title, "property_type": p.property_type,
                "days_vacant": days_vacant, "last_tenant": last_tenant,
                "last_rent_amount": last_contract.rent_amount if last_contract else None,
            })
        return results

    def units_report(self, property_id: Optional[int] = None, limit: int = 500) -> dict:
        """Backs the Unit Status/Availability/Building-Units/Villa-Units
        report (Phase 2.0). When property_id is given, scopes to that
        building/villa's direct children (Property.parent_property_id);
        otherwise reports over every leaf unit in the portfolio (same
        NON_LEASABLE_TYPES exclusion as vacancy_counts/occupancy_by_type,
        so pure containers never show up as a "unit" of themselves)."""
        base_filter = [Property.deleted_at.is_(None)]
        scoped_title = None
        if property_id is not None:
            # Same FLOOR exclusion as the portfolio-wide branch below —
            # scoping to one building must not let its own virtual
            # "whole floor" row(s) count as real units either (same bug
            # as PropertyRepository.get_unit_ids, already fixed there).
            base_filter.append(Property.parent_property_id == property_id)
            base_filter.append(Property.property_type != "floor")
            scoped = self.db.execute(select(Property.title).where(Property.id == property_id)).scalar_one_or_none()
            scoped_title = scoped
        else:
            base_filter.append(Property.property_type.notin_(NON_LEASABLE_TYPES))

        status_stmt = select(Property.availability_status, func.count()).where(*base_filter).group_by(Property.availability_status)
        by_status = [{"availability_status": r[0], "count": r[1]} for r in self.db.execute(status_stmt).all()]
        status_counts = {r["availability_status"]: r["count"] for r in by_status}

        type_stmt = select(Property.property_type, func.count()).where(*base_filter).group_by(Property.property_type)
        by_type = [{"property_type": r[0], "count": r[1]} for r in self.db.execute(type_stmt).all()]

        total = sum(status_counts.values())

        items_stmt = (
            select(Property)
            .where(*base_filter)
            .order_by(Property.property_code.asc())
            .limit(limit)
        )
        properties = list(self.db.execute(items_stmt).scalars().all())
        parent_ids = {p.parent_property_id for p in properties if p.parent_property_id}
        parents = {}
        if parent_ids:
            parent_rows = self.db.execute(select(Property.id, Property.title).where(Property.id.in_(parent_ids))).all()
            parents = {r[0]: r[1] for r in parent_rows}

        units = [{
            "property_id": p.id, "property_code": p.property_code, "title": p.title, "property_type": p.property_type,
            "availability_status": p.availability_status,
            "building_title": parents.get(p.parent_property_id) if p.parent_property_id else scoped_title,
            "floor_label": None, "unit_number": p.unit_number, "rent_price": p.rent_price,
        } for p in properties]

        return {
            "scoped_to_property_id": property_id,
            "scoped_to_property_title": scoped_title,
            "total_units": total,
            "vacant_count": status_counts.get("available", 0),
            "occupied_count": status_counts.get("leased", 0),
            "reserved_count": status_counts.get("reserved", 0),
            "under_maintenance_count": status_counts.get("under_maintenance", 0),
            "by_status": by_status,
            "by_type": by_type,
            "units": units,
        }

    def occupancy_by_type(self) -> list[dict]:
        stmt = select(
            Property.property_type, func.count().label("total"),
            func.sum(case((Property.availability_status == "leased", 1), else_=0)).label("occupied"),
        ).where(Property.deleted_at.is_(None), Property.property_type.notin_(NON_LEASABLE_TYPES)).group_by(Property.property_type).order_by(Property.property_type)
        rows = self.db.execute(stmt).all()
        results = []
        for r in rows:
            occupied = r.occupied or 0
            rate = (Decimal(occupied) / Decimal(r.total) * 100).quantize(Decimal("0.01")) if r.total else Decimal("0")
            results.append({"property_type": r.property_type, "total": r.total, "occupied": occupied, "occupancy_rate_percentage": rate})
        return results

    def occupancy_rate_for_month(self, year: int, month: int) -> Decimal:
        """Approximates occupancy for a given month as: distinct leasable
        properties with an active-at-the-time rental contract / total
        leasable properties (current count, since historical property
        counts aren't tracked)."""
        month_start = date(year, month, 1)
        month_end = date(year + 1, 1, 1) - timedelta(days=1) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
        total = self.db.execute(
            select(func.count()).select_from(Property).where(Property.deleted_at.is_(None), Property.property_type.notin_(NON_LEASABLE_TYPES))
        ).scalar_one()
        if total == 0:
            return Decimal("0")
        occupied = self.db.execute(
            select(func.count(func.distinct(RentalContract.property_id))).where(
                RentalContract.deleted_at.is_(None),
                RentalContract.contract_status.in_([RentalContractStatus.ACTIVE, RentalContractStatus.EXPIRED, RentalContractStatus.RENEWED]),
                RentalContract.start_date <= month_end, RentalContract.end_date >= month_start,
            )
        ).scalar_one()
        return (Decimal(occupied) / Decimal(total) * 100).quantize(Decimal("0.01"))

    # ---------------- Income / Expense / Profit by property & trend ----------------
    def amount_by_category(self, types: list[str], date_from: Optional[date], date_to: Optional[date], property_id: Optional[int] = None) -> list[dict]:
        category_key = func.coalesce(Transaction.category, Transaction.transaction_type)
        if property_id:
            resolved_property_id = func.coalesce(Transaction.property_id, RentalContract.property_id)
            stmt = (
                select(category_key.label("cat"), func.coalesce(func.sum(Transaction.amount), 0).label("total"), func.count().label("cnt"))
                .select_from(Transaction)
                .outerjoin(RentalContract, RentalContract.id == Transaction.rental_contract_id)
                .where(
                    Transaction.deleted_at.is_(None), Transaction.transaction_status == TransactionStatus.COMPLETED,
                    Transaction.transaction_type.in_(types), resolved_property_id == property_id,
                )
            )
        else:
            stmt = select(category_key.label("cat"), func.coalesce(func.sum(Transaction.amount), 0).label("total"), func.count().label("cnt")).where(
                Transaction.deleted_at.is_(None), Transaction.transaction_status == TransactionStatus.COMPLETED, Transaction.transaction_type.in_(types),
            )
        if date_from:
            stmt = stmt.where(Transaction.transaction_date >= date_from)
        if date_to:
            stmt = stmt.where(Transaction.transaction_date <= date_to)
        stmt = stmt.group_by("cat").order_by(func.coalesce(func.sum(Transaction.amount), 0).desc())
        rows = self.db.execute(stmt).all()
        return [{"label": r.cat, "total_amount": r.total, "count": r.cnt} for r in rows]

    def amount_by_property(self, types: list[str], date_from: Optional[date], date_to: Optional[date], limit: int = 20, property_id: Optional[int] = None) -> list[dict]:
        resolved_property_id = func.coalesce(Transaction.property_id, RentalContract.property_id)
        stmt = (
            select(resolved_property_id.label("pid"), func.coalesce(func.sum(Transaction.amount), 0).label("total"))
            .select_from(Transaction)
            .outerjoin(RentalContract, RentalContract.id == Transaction.rental_contract_id)
            .where(
                Transaction.deleted_at.is_(None), Transaction.transaction_status == TransactionStatus.COMPLETED,
                Transaction.transaction_type.in_(types), resolved_property_id.isnot(None),
            )
        )
        if property_id:
            stmt = stmt.where(resolved_property_id == property_id)
        if date_from:
            stmt = stmt.where(Transaction.transaction_date >= date_from)
        if date_to:
            stmt = stmt.where(Transaction.transaction_date <= date_to)
        stmt = stmt.group_by("pid").order_by(func.coalesce(func.sum(Transaction.amount), 0).desc()).limit(limit)
        rows = self.db.execute(stmt).all()
        if not rows:
            return []
        # Batch-fetch every property referenced by these rows in one query
        # rather than one db.get() per row (this list is capped at `limit`,
        # so the N+1 here was always bounded, but there's no reason not to
        # make it a single round-trip — found during the production audit).
        pids = [pid for pid, _ in rows]
        properties = {p.id: p for p in self.db.execute(select(Property).where(Property.id.in_(pids))).scalars().all()}
        results = []
        for pid, total in rows:
            prop = properties.get(pid)
            if prop:
                results.append({"property_id": prop.id, "property_code": prop.property_code, "property_title": prop.title, "total_amount": total})
        return results

    def monthly_trend(self, types: list[str], months: int = 6, property_id: Optional[int] = None) -> list[dict]:
        today = date.today()
        results = []
        resolved_property_id = func.coalesce(Transaction.property_id, RentalContract.property_id)
        for i in range(months - 1, -1, -1):
            target_month = today.month - i
            target_year = today.year
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            if property_id:
                stmt = (
                    select(func.coalesce(func.sum(Transaction.amount), 0))
                    .select_from(Transaction)
                    .outerjoin(RentalContract, RentalContract.id == Transaction.rental_contract_id)
                    .where(
                        Transaction.deleted_at.is_(None), Transaction.transaction_status == TransactionStatus.COMPLETED,
                        Transaction.transaction_type.in_(types), resolved_property_id == property_id,
                        extract("year", Transaction.transaction_date) == target_year,
                        extract("month", Transaction.transaction_date) == target_month,
                    )
                )
            else:
                stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.deleted_at.is_(None), Transaction.transaction_status == TransactionStatus.COMPLETED,
                    Transaction.transaction_type.in_(types),
                    extract("year", Transaction.transaction_date) == target_year,
                    extract("month", Transaction.transaction_date) == target_month,
                )
            total = self.db.execute(stmt).scalar_one()
            results.append({"month": f"{target_year:04d}-{target_month:02d}", "total_amount": total})
        return results

    def maintenance_cost_total(self, date_from: Optional[date], date_to: Optional[date], property_id: Optional[int] = None) -> Decimal:
        material_stmt = select(func.coalesce(func.sum(MaintenanceMaterial.quantity * MaintenanceMaterial.unit_cost), 0)).select_from(MaintenanceMaterial).join(
            MaintenanceRequest, MaintenanceRequest.id == MaintenanceMaterial.request_id
        ).where(MaintenanceMaterial.deleted_at.is_(None), MaintenanceRequest.deleted_at.is_(None))
        labor_stmt = select(func.coalesce(func.sum(MaintenanceLaborCost.hours * MaintenanceLaborCost.hourly_rate), 0)).select_from(MaintenanceLaborCost).join(
            MaintenanceRequest, MaintenanceRequest.id == MaintenanceLaborCost.request_id
        ).where(MaintenanceLaborCost.deleted_at.is_(None), MaintenanceRequest.deleted_at.is_(None))
        if property_id:
            material_stmt = material_stmt.where(MaintenanceRequest.property_id == property_id)
            labor_stmt = labor_stmt.where(MaintenanceRequest.property_id == property_id)
        if date_from:
            material_stmt = material_stmt.where(MaintenanceRequest.reported_date >= date_from)
            labor_stmt = labor_stmt.where(MaintenanceRequest.reported_date >= date_from)
        if date_to:
            material_stmt = material_stmt.where(MaintenanceRequest.reported_date <= date_to)
            labor_stmt = labor_stmt.where(MaintenanceRequest.reported_date <= date_to)
        materials = self.db.execute(material_stmt).scalar_one()
        labor = self.db.execute(labor_stmt).scalar_one()
        return materials + labor

    # ---------------- Dashboard Analytics ----------------
    def active_rental_contracts_count(self) -> int:
        return self.db.execute(select(func.count()).select_from(RentalContract).where(
            RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE
        )).scalar_one()

    def active_lease_agreements_count(self) -> int:
        return self.db.execute(select(func.count()).select_from(LeaseAgreement).where(
            LeaseAgreement.deleted_at.is_(None), LeaseAgreement.contract_status == LeaseStatus.ACTIVE
        )).scalar_one()

    def open_maintenance_requests_count(self) -> int:
        return self.db.execute(select(func.count()).select_from(MaintenanceRequest).where(
            MaintenanceRequest.deleted_at.is_(None),
            MaintenanceRequest.maintenance_status.notin_([MaintenanceRequestStatus.COMPLETED, MaintenanceRequestStatus.CANCELLED]),
        )).scalar_one()

    # ---------------- Lease Report (Rental Contracts + Lease Agreements) ----------------
    def contracts_by_status(self, model, status_column) -> list[dict]:
        stmt = select(status_column, func.count(), func.coalesce(func.sum(model.rent_amount), 0)).where(
            model.deleted_at.is_(None)
        ).group_by(status_column)
        rows = self.db.execute(stmt).all()
        return [{"status": r[0], "count": r[1], "total_rent": r[2]} for r in rows]

    def contracts_list(self, model, status_column, contract_status: Optional[str], property_id: Optional[int], date_from: Optional[date], date_to: Optional[date], limit: int = 200) -> list:
        stmt = select(model).where(model.deleted_at.is_(None))
        if contract_status:
            stmt = stmt.where(status_column == contract_status)
        if property_id:
            stmt = stmt.where(model.property_id == property_id)
        if date_from:
            stmt = stmt.where(model.end_date >= date_from)
        if date_to:
            stmt = stmt.where(model.end_date <= date_to)
        stmt = stmt.order_by(model.end_date.asc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    # ---------------- Maintenance Report ----------------
    def maintenance_by_status(self) -> list[dict]:
        stmt = select(MaintenanceRequest.maintenance_status, func.count()).where(
            MaintenanceRequest.deleted_at.is_(None)
        ).group_by(MaintenanceRequest.maintenance_status)
        return [{"status": r[0], "count": r[1]} for r in self.db.execute(stmt).all()]

    def maintenance_by_priority(self) -> list[dict]:
        stmt = select(MaintenanceRequest.priority, func.count()).where(
            MaintenanceRequest.deleted_at.is_(None)
        ).group_by(MaintenanceRequest.priority)
        return [{"priority": r[0], "count": r[1]} for r in self.db.execute(stmt).all()]

    def maintenance_by_category(self) -> list[dict]:
        stmt = select(func.coalesce(MaintenanceRequest.category, "uncategorized"), func.count()).where(
            MaintenanceRequest.deleted_at.is_(None)
        ).group_by(func.coalesce(MaintenanceRequest.category, "uncategorized"))
        return [{"category": r[0], "count": r[1]} for r in self.db.execute(stmt).all()]

    def maintenance_by_contractor(self) -> list[dict]:
        stmt = (
            select(Contractor.id, Contractor.company_name, func.count(MaintenanceRequest.id))
            .select_from(Contractor)
            .join(MaintenanceRequest, MaintenanceRequest.assigned_contractor_id == Contractor.id)
            .where(Contractor.deleted_at.is_(None), MaintenanceRequest.deleted_at.is_(None))
            .group_by(Contractor.id, Contractor.company_name)
            .order_by(func.count(MaintenanceRequest.id).desc())
        )
        return [{"contractor_id": r[0], "contractor_name": r[1], "request_count": r[2]} for r in self.db.execute(stmt).all()]

    def maintenance_average_resolution_days(self) -> Optional[Decimal]:
        """Computed in Python rather than SQL to stay portable across
        database backends — date-subtraction functions differ enough
        between SQLite (dev/tests) and Postgres (production) that a
        dialect-specific SQL expression risks aborting the whole
        transaction on whichever backend it wasn't written for."""
        stmt = select(MaintenanceRequest.reported_date, MaintenanceRequest.completed_date).where(
            MaintenanceRequest.deleted_at.is_(None), MaintenanceRequest.completed_date.isnot(None),
        )
        rows = self.db.execute(stmt).all()
        if not rows:
            return None
        total_days = sum((completed - reported).days for reported, completed in rows)
        return Decimal(str(round(total_days / len(rows), 1)))

    def maintenance_list(self, status: Optional[str], priority: Optional[str], property_id: Optional[int], date_from: Optional[date], date_to: Optional[date], limit: int = 200) -> list[MaintenanceRequest]:
        stmt = select(MaintenanceRequest).where(MaintenanceRequest.deleted_at.is_(None))
        if status:
            stmt = stmt.where(MaintenanceRequest.maintenance_status == status)
        if priority:
            stmt = stmt.where(MaintenanceRequest.priority == priority)
        if property_id:
            stmt = stmt.where(MaintenanceRequest.property_id == property_id)
        if date_from:
            stmt = stmt.where(MaintenanceRequest.reported_date >= date_from)
        if date_to:
            stmt = stmt.where(MaintenanceRequest.reported_date <= date_to)
        stmt = stmt.order_by(MaintenanceRequest.reported_date.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    # ---------------- Collections Report ----------------
    def collections_by_month(self, months: int = 6) -> list[dict]:
        today = date.today()
        results = []
        for i in range(months - 1, -1, -1):
            target_month = today.month - i
            target_year = today.year
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            stmt = select(
                func.coalesce(func.sum(RentalPaymentInstallment.amount), 0),
                func.coalesce(func.sum(case((RentalPaymentInstallment.payment_status == RentalInstallmentStatus.PAID, RentalPaymentInstallment.amount), else_=0)), 0),
            ).where(
                RentalPaymentInstallment.deleted_at.is_(None),
                extract("year", RentalPaymentInstallment.due_date) == target_year,
                extract("month", RentalPaymentInstallment.due_date) == target_month,
            )
            due, collected = self.db.execute(stmt).one()
            rate = (Decimal(collected) / Decimal(due) * 100).quantize(Decimal("0.01")) if due else Decimal("0")
            results.append({"month": f"{target_year:04d}-{target_month:02d}", "due": due, "collected": collected, "collection_rate_percentage": rate})
        return results

    def collections_by_property(self, date_from: Optional[date], date_to: Optional[date], limit: int = 20) -> list[dict]:
        stmt = (
            select(
                Property.id, Property.property_code, Property.title,
                func.coalesce(func.sum(RentalPaymentInstallment.amount), 0).label("due"),
                func.coalesce(func.sum(case((RentalPaymentInstallment.payment_status == RentalInstallmentStatus.PAID, RentalPaymentInstallment.amount), else_=0)), 0).label("collected"),
            )
            .select_from(RentalPaymentInstallment)
            .join(RentalContract, RentalContract.id == RentalPaymentInstallment.contract_id)
            .join(Property, Property.id == RentalContract.property_id)
            .where(RentalPaymentInstallment.deleted_at.is_(None), Property.deleted_at.is_(None))
        )
        if date_from:
            stmt = stmt.where(RentalPaymentInstallment.due_date >= date_from)
        if date_to:
            stmt = stmt.where(RentalPaymentInstallment.due_date <= date_to)
        stmt = stmt.group_by(Property.id, Property.property_code, Property.title).order_by(func.coalesce(func.sum(RentalPaymentInstallment.amount), 0).desc()).limit(limit)
        rows = self.db.execute(stmt).all()
        results = []
        for pid, code, title, due, collected in rows:
            rate = (Decimal(collected) / Decimal(due) * 100).quantize(Decimal("0.01")) if due else Decimal("0")
            results.append({"property_id": pid, "property_code": code, "property_title": title, "due": due, "collected": collected, "collection_rate_percentage": rate})
        return results

    # ---------------- Outstanding Report (with aging) ----------------
    def tenant_outstanding_aging(self) -> dict:
        today = date.today()
        buckets = {"current": Decimal("0"), "days_1_30": Decimal("0"), "days_31_60": Decimal("0"), "days_61_90": Decimal("0"), "days_90_plus": Decimal("0")}
        # due_date <= today: a future, not-yet-due installment isn't
        # "outstanding" yet at all, so it shouldn't even reach the
        # "current" bucket — same fix as the totals above, applied here
        # too since this loop was pulling every pending installment
        # regardless of whether its due date had actually arrived.
        stmt = select(RentalPaymentInstallment).where(
            RentalPaymentInstallment.payment_status.in_([RentalInstallmentStatus.PENDING, RentalInstallmentStatus.OVERDUE]),
            RentalPaymentInstallment.due_date <= today,
            RentalPaymentInstallment.deleted_at.is_(None),
        )
        installments = self.db.execute(stmt).scalars().all()
        for inst in installments:
            net = inst.amount - inst.discount_amount + inst.tax_amount + inst.late_fee_amount
            days_overdue = (today - inst.due_date).days
            if days_overdue <= 0:
                buckets["current"] += net
            elif days_overdue <= 30:
                buckets["days_1_30"] += net
            elif days_overdue <= 60:
                buckets["days_31_60"] += net
            elif days_overdue <= 90:
                buckets["days_61_90"] += net
            else:
                buckets["days_90_plus"] += net
        return buckets

    def owner_outstanding_aging(self) -> dict:
        today = date.today()
        buckets = {"current": Decimal("0"), "days_1_30": Decimal("0"), "days_31_60": Decimal("0"), "days_61_90": Decimal("0"), "days_90_plus": Decimal("0")}
        stmt = select(LeasePaymentInstallment).where(
            LeasePaymentInstallment.payment_status.in_([InstallmentStatus.PENDING, InstallmentStatus.OVERDUE]),
            LeasePaymentInstallment.due_date <= today,
            LeasePaymentInstallment.deleted_at.is_(None),
        )
        installments = self.db.execute(stmt).scalars().all()
        for inst in installments:
            days_overdue = (today - inst.due_date).days
            if days_overdue <= 0:
                buckets["current"] += inst.amount
            elif days_overdue <= 30:
                buckets["days_1_30"] += inst.amount
            elif days_overdue <= 60:
                buckets["days_31_60"] += inst.amount
            elif days_overdue <= 90:
                buckets["days_61_90"] += inst.amount
            else:
                buckets["days_90_plus"] += inst.amount
        return buckets

    # ---------------- Contract Expiration Report ----------------
    def expiring_rental_contracts(self, days: int, property_id: Optional[int] = None) -> list[RentalContract]:
        today = date.today()
        stmt = select(RentalContract).where(
            RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE,
            RentalContract.end_date >= today, RentalContract.end_date <= today + timedelta(days=days),
        )
        if property_id:
            stmt = stmt.where(RentalContract.property_id == property_id)
        stmt = stmt.order_by(RentalContract.end_date.asc())
        return list(self.db.execute(stmt).scalars().all())

    def expiring_lease_agreements(self, days: int, property_id: Optional[int] = None) -> list[LeaseAgreement]:
        today = date.today()
        stmt = select(LeaseAgreement).where(
            LeaseAgreement.deleted_at.is_(None), LeaseAgreement.contract_status == LeaseStatus.ACTIVE,
            LeaseAgreement.end_date >= today, LeaseAgreement.end_date <= today + timedelta(days=days),
        )
        if property_id:
            stmt = stmt.where(LeaseAgreement.property_id == property_id)
        stmt = stmt.order_by(LeaseAgreement.end_date.asc())
        return list(self.db.execute(stmt).scalars().all())


class ReportScheduleRepository(BaseRepository[ReportSchedule]):
    def __init__(self, db: Session):
        super().__init__(ReportSchedule, db)

    def list_all(self, is_active: Optional[bool] = None) -> list[ReportSchedule]:
        stmt = select(ReportSchedule).where(ReportSchedule.deleted_at.is_(None))
        if is_active is not None:
            stmt = stmt.where(ReportSchedule.is_active == is_active)
        stmt = stmt.order_by(ReportSchedule.next_run_at.asc())
        return list(self.db.execute(stmt).scalars().all())

    def list_due(self, as_of: Optional[datetime] = None) -> list[ReportSchedule]:
        as_of = as_of or datetime.utcnow()
        stmt = select(ReportSchedule).where(
            ReportSchedule.deleted_at.is_(None), ReportSchedule.is_active.is_(True),
            ReportSchedule.next_run_at <= as_of,
        )
        return list(self.db.execute(stmt).scalars().all())
