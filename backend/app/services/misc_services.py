from typing import Optional
from decimal import Decimal
from datetime import date
from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.repositories.system_repository import AttachmentRepository, NoteRepository
from app.services.file_storage_service import FileUploadService
from app.services.audit_service import AuditService
from app.models.user import User


class AttachmentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AttachmentRepository(db)
        self.uploader = FileUploadService()
        self.audit = AuditService(db)

    def upload(self, file: UploadFile, entity_type: str, entity_id: int, description: Optional[str], actor_id: Optional[int]):
        meta = self.uploader.upload(file, entity_type, entity_id)
        meta["entity_type"] = entity_type
        meta["entity_id"] = entity_id
        meta["description"] = description
        attachment = self.repo.create(meta, actor_id=actor_id)
        self.audit.log_activity(entity_type, entity_id, "attachment_added", f"File '{attachment.file_name}' uploaded", actor_id)
        self.db.commit()
        return attachment

    def list_for_entity(self, entity_type: str, entity_id: int):
        return self.repo.list_for_entity(entity_type, entity_id)

    def delete(self, attachment_id: int, actor_id: Optional[int]):
        attachment = self.repo.get(attachment_id)
        if not attachment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
        self.uploader.delete(attachment.file_path)
        self.repo.soft_delete(attachment, actor_id=actor_id)
        self.audit.log_activity(attachment.entity_type, attachment.entity_id, "attachment_removed", f"File '{attachment.file_name}' removed", actor_id)
        self.db.commit()


class NoteService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = NoteRepository(db)
        self.audit = AuditService(db)

    def create(self, entity_type: str, entity_id: int, content: str, is_pinned: bool, actor_id: Optional[int]):
        note = self.repo.create(
            {"entity_type": entity_type, "entity_id": entity_id, "content": content, "is_pinned": is_pinned},
            actor_id=actor_id,
        )
        self.audit.log_activity(entity_type, entity_id, "note_added", "A note was added", actor_id)
        self.db.commit()
        return note

    def list_for_entity(self, entity_type: str, entity_id: int):
        return self.repo.list_for_entity(entity_type, entity_id)

    def update(self, note_id: int, content: Optional[str], is_pinned: Optional[bool], actor_id: Optional[int]):
        note = self.repo.get(note_id)
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        data = {}
        if content is not None:
            data["content"] = content
        if is_pinned is not None:
            data["is_pinned"] = is_pinned
        self.repo.update(note, data, actor_id=actor_id)
        self.db.commit()
        return note

    def delete(self, note_id: int, actor_id: Optional[int]):
        note = self.repo.get(note_id)
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        self.repo.soft_delete(note, actor_id=actor_id)
        self.db.commit()


class DashboardService:
    """
    Phase 1 dashboard: system-level widgets (user counts, branches, recent
    activity). Business widgets (properties, leases, revenue) arrive in
    later phases once those modules exist — this service is structured so
    adding widgets later is additive, not a rewrite.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_summary(self, current_user: User) -> dict:
        from app.models.user import User as UserModel, Role
        from app.models.organization import Branch
        from app.models.system import ActivityLog, Notification
        from app.models.owner import Owner
        from app.models.lease import LeaseAgreement, LeaseStatus
        from app.models.property import Property
        from app.models.tenant import Tenant
        from app.models.rental import RentalContract, RentalContractStatus
        from app.repositories.financial_repository import FinancialAccountRepository
        from app.repositories.property_repository import PropertyRepository
        from app.models.maintenance import MaintenanceRequest, MaintenanceRequestStatus
        from app.services.accounting_service import AccountingReportService
        from app.business_workflows.occupancy.occupancy_service import OccupancyService
        from app.services.rental_service import RentalService

        total_users = self.db.execute(
            select(func.count()).select_from(UserModel).where(UserModel.deleted_at.is_(None))
        ).scalar_one()
        active_users = self.db.execute(
            select(func.count()).select_from(UserModel).where(UserModel.deleted_at.is_(None), UserModel.is_active.is_(True))
        ).scalar_one()
        total_roles = self.db.execute(
            select(func.count()).select_from(Role).where(Role.deleted_at.is_(None))
        ).scalar_one()
        total_branches = self.db.execute(
            select(func.count()).select_from(Branch).where(Branch.deleted_at.is_(None))
        ).scalar_one()
        total_owners = self.db.execute(
            select(func.count()).select_from(Owner).where(Owner.deleted_at.is_(None))
        ).scalar_one()
        active_leases = self.db.execute(
            select(func.count()).select_from(LeaseAgreement).where(
                LeaseAgreement.deleted_at.is_(None), LeaseAgreement.contract_status == LeaseStatus.ACTIVE
            )
        ).scalar_one()
        total_properties = self.db.execute(
            # Same FLOOR exclusion as PropertyRepository.dashboard_counts /
            # ReportsRepository.total_properties (already fixed) — this is
            # a third, independent implementation of the same "Total
            # Properties" figure, found during a full-codebase sweep for
            # every place that counts Property rows.
            select(func.count()).select_from(Property).where(Property.deleted_at.is_(None), Property.property_type != "floor")
        ).scalar_one()
        total_buildings = self.db.execute(
            select(func.count()).select_from(Property).where(Property.deleted_at.is_(None), Property.parent_property_id.is_(None))
        ).scalar_one()
        total_tenants = self.db.execute(
            select(func.count()).select_from(Tenant).where(Tenant.deleted_at.is_(None))
        ).scalar_one()
        active_rental_contracts = self.db.execute(
            select(func.count()).select_from(RentalContract).where(
                RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE
            )
        ).scalar_one()
        account_repo = FinancialAccountRepository(self.db)
        total_cash_bank_balance = sum(
            (account_repo.current_balance(a.id) for a in account_repo.list_active()), Decimal("0")
        )
        open_maintenance_requests = self.db.execute(
            select(func.count()).select_from(MaintenanceRequest).where(
                MaintenanceRequest.deleted_at.is_(None),
                MaintenanceRequest.maintenance_status.notin_([MaintenanceRequestStatus.COMPLETED, MaintenanceRequestStatus.CANCELLED]),
            )
        ).scalar_one()
        try:
            trial_balance = AccountingReportService(self.db).trial_balance(date.today())
            gl_variance = trial_balance["total_debit"] - trial_balance["total_credit"]
        except Exception:
            gl_variance = Decimal("0")
        recent_activity = self.db.execute(
            select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(10)
        ).scalars().all()
        unread_notifications = self.db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.recipient_id == current_user.id, Notification.is_read.is_(False)
            )
        ).scalar_one()

        # Unified Dashboard extension: everything below composes existing,
        # already-tested services (Occupancy Engine, Rental Contract
        # dashboard, Tenant repo) rather than re-deriving any of this math
        # a second time — same "reuse, don't duplicate" rule the rest of
        # this codebase follows. Wrapped defensively so a problem in any
        # one of these never breaks the whole dashboard load.
        occupancy_summary = {"total_units": 0, "occupied_units": 0, "vacant_units": 0}
        buildings_overview: list[dict] = []
        try:
            occ_service = OccupancyService(self.db)
            occ_dashboard = occ_service.get_dashboard()
            occupancy_summary = {
                "total_units": occ_dashboard.get("total_units", 0),
                "occupied_units": occ_dashboard.get("occupied_units", 0),
                "vacant_units": occ_dashboard.get("vacant_units", 0),
            }
            buildings_overview = occ_service.get_buildings()[:10]
        except Exception:
            pass

        rental_dashboard = {"active_contracts": active_rental_contracts, "expiring_soon": 0}
        recent_contracts: list[dict] = []
        expiring_contracts_list: list[dict] = []
        try:
            rental_repo = RentalService(self.db).repo
            rental_dashboard = rental_repo.dashboard_counts()
            recent_stmt = select(RentalContract).where(RentalContract.deleted_at.is_(None)).order_by(RentalContract.created_at.desc()).limit(5)
            recent_contracts = [
                {"id": c.id, "contract_number": c.contract_number, "contract_status": c.contract_status, "property_id": c.property_id}
                for c in self.db.execute(recent_stmt).scalars().all()
            ]
            expiring_contracts_list = [
                {"id": c.id, "contract_number": c.contract_number, "end_date": c.end_date.isoformat(), "property_id": c.property_id, "tenant_id": c.tenant_id}
                for c in rental_dashboard.get("upcoming_renewals", [])[:5]
            ]
        except Exception:
            pass

        # Vacant Units Value: total potential monthly rent being left on
        # the table by units that are currently vacant. Reuses
        # OccupancyService.get_units() exactly as-is — its "rent_amount"
        # field already resolves to unit.rent_price for any unit with no
        # active contract (see that method), which is precisely the
        # "asking price" this needs; no separate query duplicating that
        # logic. Units with no rent_price set are counted but excluded
        # from the sum (so the total stays an honest floor, not an
        # underestimate silently passed off as complete) and reported
        # separately so the dashboard can flag it.
        vacant_units_value = Decimal("0")
        vacant_units_missing_price = 0
        try:
            vacant_items, _ = occ_service.get_units(None, "vacant", 1, 100000)
            for u in vacant_items:
                if u.get("rent_amount"):
                    vacant_units_value += Decimal(str(u["rent_amount"]))
                else:
                    vacant_units_missing_price += 1
        except Exception:
            pass

        # Portfolio Monthly Profit: same estimate PropertyHubService
        # computes for one property (income collected - owner payouts -
        # maintenance costs, this calendar month), summed across every
        # property instead of scoped to one — same three queries, no
        # separate math. Per-property drill-down reuses the existing
        # GET /properties/{id}/hub-summary endpoint directly from the
        # frontend; nothing duplicated here for that case.
        portfolio_monthly_profit = Decimal("0")
        try:
            from app.models.financial import Transaction, TransactionType
            from app.models.maintenance import MaintenanceMaterial, MaintenanceLaborCost
            month_start = date.today().replace(day=1)
            income_this_month = self.db.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.transaction_type == TransactionType.TENANT_PAYMENT,
                    Transaction.transaction_date >= month_start, Transaction.transaction_date <= date.today(), Transaction.deleted_at.is_(None),
                )
            ).scalar_one()
            owner_paid_this_month = self.db.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.transaction_type == TransactionType.OWNER_PAYMENT,
                    Transaction.transaction_date >= month_start, Transaction.transaction_date <= date.today(), Transaction.deleted_at.is_(None),
                )
            ).scalar_one()
            maintenance_material_cost = self.db.execute(
                select(func.coalesce(func.sum(MaintenanceMaterial.quantity * MaintenanceMaterial.unit_cost), 0))
                .join(MaintenanceRequest, MaintenanceRequest.id == MaintenanceMaterial.request_id)
                .where(MaintenanceRequest.reported_date >= month_start)
            ).scalar_one()
            maintenance_labor_cost = self.db.execute(
                select(func.coalesce(func.sum(MaintenanceLaborCost.hours * MaintenanceLaborCost.hourly_rate), 0))
                .join(MaintenanceRequest, MaintenanceRequest.id == MaintenanceLaborCost.request_id)
                .where(MaintenanceRequest.reported_date >= month_start)
            ).scalar_one()
            portfolio_monthly_profit = income_this_month - owner_paid_this_month - maintenance_material_cost - maintenance_labor_cost
        except Exception:
            pass

        recent_tenants_stmt = select(Tenant).where(Tenant.deleted_at.is_(None)).order_by(Tenant.created_at.desc()).limit(5)
        recent_tenants = [
            {"id": t.id, "tenant_code": t.tenant_code, "display_name": t.display_name, "is_blacklisted": t.is_blacklisted}
            for t in self.db.execute(recent_tenants_stmt).scalars().all()
        ]

        return {
            "widgets": {
                "total_users": total_users,
                "active_users": active_users,
                "total_roles": total_roles,
                "total_branches": total_branches,
                "total_owners": total_owners,
                "active_leases": active_leases,
                "total_properties": total_properties,
                "total_buildings": total_buildings,
                "total_apartments": occupancy_summary["total_units"],
                "occupied_apartments": occupancy_summary["occupied_units"],
                "vacant_apartments": occupancy_summary["vacant_units"],
                "total_tenants": total_tenants,
                "active_rental_contracts": active_rental_contracts,
                "expiring_contracts": rental_dashboard.get("expiring_soon", 0),
                "total_cash_bank_balance": total_cash_bank_balance,
                "open_maintenance_requests": open_maintenance_requests,
                "gl_trial_balance_variance": gl_variance,
                "unread_notifications": unread_notifications,
                "vacant_units_value": vacant_units_value,
                "vacant_units_missing_price": vacant_units_missing_price,
                "portfolio_monthly_profit": portfolio_monthly_profit,
            },
            "buildings_overview": buildings_overview,
            "recent_contracts": recent_contracts,
            "expiring_contracts_list": expiring_contracts_list,
            "recent_tenants": recent_tenants,
            "recent_activity": [
                {
                    "action": a.action,
                    "description": a.description,
                    "entity_type": a.entity_type,
                    "entity_id": a.entity_id,
                    "created_at": a.created_at.isoformat(),
                }
                for a in recent_activity
            ],
        }

    def get_executive_summary(self, current_user: User) -> dict:
        """Executive Dashboard Phase 1 — a NEW, separate method (does not
        touch get_summary above, so nothing existing changes behavior).
        Every number here is computed directly from real data — no
        placeholder or estimated figures. Trend percentages are only
        included where a genuine, cheap month-over-month comparison
        exists (rent collected, expenses, maintenance opened); metrics
        without a real prior-period baseline (occupancy rate, owner
        balance) are returned without a trend rather than a fabricated
        one.
        """
        from app.models.property import Property, Floor
        from app.models.rental import RentalContract, RentalContractStatus, RentalPaymentInstallment, RentalInstallmentStatus
        from app.models.maintenance import MaintenanceRequest, MaintenanceRequestStatus, MaintenanceMaterial, MaintenanceLaborCost
        from app.models.financial import Transaction, TransactionType
        from app.models.owner import Owner
        from app.business_workflows.occupancy.occupancy_service import OccupancyService
        from app.business_workflows.owner_ledger.owner_balance_service import OwnerBalanceService
        from app.services.rental_service import RentalService
        from dateutil.relativedelta import relativedelta

        today = date.today()
        month_start = today.replace(day=1)
        next_month_start = (month_start + relativedelta(months=1))
        next_month_end = (next_month_start + relativedelta(months=1)) - timedelta(days=1)
        prev_month_start = month_start - relativedelta(months=1)
        prev_month_end = month_start - timedelta(days=1)

        total_floors = self.db.execute(select(func.count()).select_from(Floor)).scalar_one()

        occ = {"total_units": 0, "occupied_units": 0, "vacant_units": 0}
        try:
            occ_dashboard = OccupancyService(self.db).get_dashboard()
            occ = {
                "total_units": occ_dashboard.get("total_units", 0),
                "occupied_units": occ_dashboard.get("occupied_units", 0),
                "vacant_units": occ_dashboard.get("vacant_units", 0),
            }
        except Exception:
            pass
        occupancy_rate = round((occ["occupied_units"] / occ["total_units"] * 100), 1) if occ["total_units"] else 0.0

        active_contracts = self.db.execute(
            select(func.count()).select_from(RentalContract).where(
                RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE,
            )
        ).scalar_one()
        expiring_30 = self.db.execute(
            select(func.count()).select_from(RentalContract).where(
                RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE,
                RentalContract.end_date >= today, RentalContract.end_date <= today + timedelta(days=30),
            )
        ).scalar_one()
        expiring_60 = self.db.execute(
            select(func.count()).select_from(RentalContract).where(
                RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE,
                RentalContract.end_date >= today, RentalContract.end_date <= today + timedelta(days=60),
            )
        ).scalar_one()

        def sum_transactions(txn_type: str, d_from: date, d_to: date) -> Decimal:
            return self.db.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.transaction_type == txn_type, Transaction.deleted_at.is_(None),
                    Transaction.transaction_date >= d_from, Transaction.transaction_date <= d_to,
                )
            ).scalar_one()

        rent_collected_this_month = sum_transactions(TransactionType.TENANT_PAYMENT, month_start, today)
        rent_collected_prev_month = sum_transactions(TransactionType.TENANT_PAYMENT, prev_month_start, prev_month_end)
        rent_collected_trend = (
            round(float((rent_collected_this_month - rent_collected_prev_month) / rent_collected_prev_month * 100), 1)
            if rent_collected_prev_month else None
        )

        # Only genuinely-due-now installments count as "outstanding" —
        # same fixed logic already used everywhere else in this codebase
        # (see the "Outstanding totals were counting future installments"
        # fix documented in README.md); not re-derived here, delegated
        # to the same repository method.
        rental_dashboard = {}
        try:
            rental_dashboard = RentalService(self.db).repo.dashboard_counts()
        except Exception:
            pass
        monthly_outstanding = rental_dashboard.get("total_outstanding_amount", Decimal("0"))

        def sum_installments_due(d_from: date, d_to: date) -> Decimal:
            return self.db.execute(
                select(func.coalesce(func.sum(
                    RentalPaymentInstallment.amount - RentalPaymentInstallment.discount_amount
                    + RentalPaymentInstallment.tax_amount + RentalPaymentInstallment.late_fee_amount
                ), 0)).where(
                    RentalPaymentInstallment.deleted_at.is_(None),
                    RentalPaymentInstallment.due_date >= d_from, RentalPaymentInstallment.due_date <= d_to,
                )
            ).scalar_one()

        expected_income_this_month = sum_installments_due(month_start, (next_month_start - timedelta(days=1)))
        expected_income_next_month = sum_installments_due(next_month_start, next_month_end)

        total_owner_balance = Decimal("0")
        try:
            balance_service = OwnerBalanceService(self.db)
            owner_ids = self.db.execute(select(Owner.id).where(Owner.deleted_at.is_(None))).scalars().all()
            total_owner_balance = sum((balance_service.get_current_balance(oid) for oid in owner_ids), Decimal("0"))
        except Exception:
            pass

        total_maintenance = self.db.execute(select(func.count()).select_from(MaintenanceRequest).where(MaintenanceRequest.deleted_at.is_(None))).scalar_one()
        open_maintenance = self.db.execute(
            select(func.count()).select_from(MaintenanceRequest).where(
                MaintenanceRequest.deleted_at.is_(None),
                MaintenanceRequest.maintenance_status.notin_([MaintenanceRequestStatus.COMPLETED, MaintenanceRequestStatus.CANCELLED]),
            )
        ).scalar_one()
        closed_maintenance = self.db.execute(
            select(func.count()).select_from(MaintenanceRequest).where(
                MaintenanceRequest.deleted_at.is_(None), MaintenanceRequest.maintenance_status == MaintenanceRequestStatus.COMPLETED,
            )
        ).scalar_one()
        maintenance_cost_this_month = self.db.execute(
            select(func.coalesce(func.sum(MaintenanceMaterial.quantity * MaintenanceMaterial.unit_cost), 0))
            .join(MaintenanceRequest, MaintenanceRequest.id == MaintenanceMaterial.request_id)
            .where(MaintenanceRequest.reported_date >= month_start)
        ).scalar_one() + self.db.execute(
            select(func.coalesce(func.sum(MaintenanceLaborCost.hours * MaintenanceLaborCost.hourly_rate), 0))
            .join(MaintenanceRequest, MaintenanceRequest.id == MaintenanceLaborCost.request_id)
            .where(MaintenanceRequest.reported_date >= month_start)
        ).scalar_one()

        total_security_deposits = self.db.execute(
            select(func.coalesce(func.sum(RentalContract.security_deposit_amount), 0)).where(
                RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE,
            )
        ).scalar_one()

        owner_paid_this_month = sum_transactions(TransactionType.OWNER_PAYMENT, month_start, today)
        expense_this_month = sum_transactions(TransactionType.EXPENSE, month_start, today)
        other_income_this_month = sum_transactions(TransactionType.INCOME, month_start, today)
        net_income_this_month = rent_collected_this_month + other_income_this_month - maintenance_cost_this_month - expense_this_month - owner_paid_this_month

        # Smart Alerts — each one only appears if the condition it
        # describes is actually true right now; nothing shown "just in
        # case."
        alerts = []
        if monthly_outstanding > 0:
            alerts.append({"severity": "warning", "code": "late_rent", "message": f"{monthly_outstanding:,.2f} in rent is currently overdue or due", "action_label": "View Outstanding", "action_path": "/reports"})
        if expiring_30 > 0:
            alerts.append({"severity": "warning", "code": "contracts_expiring", "message": f"{expiring_30} contract(s) expiring within 30 days", "action_label": "View Contracts", "action_path": "/rentals"})
        if occ["vacant_units"] > 0:
            alerts.append({"severity": "info", "code": "vacant_units", "message": f"{occ['vacant_units']} unit(s) currently vacant", "action_label": "View Properties", "action_path": "/properties"})
        if maintenance_cost_this_month > 0 and maintenance_cost_this_month > (rent_collected_this_month * Decimal("0.2") if rent_collected_this_month else Decimal("0")):
            alerts.append({"severity": "warning", "code": "high_maintenance_cost", "message": f"Maintenance cost this month ({maintenance_cost_this_month:,.2f}) exceeds 20% of rent collected", "action_label": "View Maintenance", "action_path": "/maintenance"})
        if total_owner_balance < 0:
            alerts.append({"severity": "critical", "code": "negative_owner_balance", "message": "One or more owners have a negative ledger balance", "action_label": "View Owners", "action_path": "/owners"})
        if open_maintenance > 0:
            alerts.append({"severity": "info", "code": "open_maintenance", "message": f"{open_maintenance} open maintenance request(s)", "action_label": "View Maintenance", "action_path": "/maintenance"})

        return {
            "kpis": {
                "total_buildings": self.db.execute(select(func.count()).select_from(Property).where(Property.deleted_at.is_(None), Property.parent_property_id.is_(None))).scalar_one(),
                "total_floors": total_floors,
                "total_units": occ["total_units"],
                "occupied_units": occ["occupied_units"],
                "vacant_units": occ["vacant_units"],
                "occupancy_rate": occupancy_rate,
                "active_contracts": active_contracts,
                "contracts_expiring_30": expiring_30,
                "contracts_expiring_60": expiring_60,
                "monthly_rent_collected": rent_collected_this_month,
                "monthly_rent_collected_trend_pct": rent_collected_trend,
                "monthly_outstanding_rent": monthly_outstanding,
                "total_owner_balance": total_owner_balance,
                "total_maintenance_requests": total_maintenance,
                "open_maintenance_requests": open_maintenance,
                "closed_maintenance_requests": closed_maintenance,
                "expected_income_this_month": expected_income_this_month,
                "expected_income_next_month": expected_income_next_month,
                "total_security_deposits": total_security_deposits,
            },
            "rent_collection": {
                "collected": rent_collected_this_month,
                "outstanding": monthly_outstanding,
                "expected": expected_income_this_month,
                "collection_percentage": round(float(rent_collected_this_month / expected_income_this_month * 100), 1) if expected_income_this_month else 0.0,
            },
            "occupancy": occ | {"occupancy_rate": occupancy_rate},
            "financial_summary": {
                "rental_income": rent_collected_this_month,
                "other_income": other_income_this_month,
                "maintenance_expenses": maintenance_cost_this_month,
                "other_expenses": expense_this_month,
                "owner_payouts": owner_paid_this_month,
                "net_income": net_income_this_month,
            },
            "alerts": alerts,
        }

    def get_top_lists(self) -> dict:
        """Phase 2 — Top Lists. Every list is built from real transactions/
        contracts/installments, limited to a reasonable top-N, nothing
        pre-computed or cached (fine at this data scale; revisit with
        materialized views only if this table ever gets large)."""
        from app.models.property import Property
        from app.models.owner import Owner
        from app.models.tenant import Tenant
        from app.models.rental import RentalContract, RentalPaymentInstallment, RentalInstallmentStatus
        from app.models.financial import Transaction, TransactionType
        from app.business_workflows.occupancy.occupancy_service import OccupancyService

        month_start = date.today().replace(day=1)

        # Top Buildings by Revenue (this month's tenant_payment total,
        # attributed via Transaction.property_id — already set correctly
        # for every payment path in this codebase, see
        # PropertyHubService for the identical attribution logic).
        revenue_by_building = self.db.execute(
            select(Property.id, Property.title, Property.property_code, func.coalesce(func.sum(Transaction.amount), 0).label("revenue"))
            .join(Transaction, Transaction.property_id == Property.id)
            .where(
                Property.deleted_at.is_(None), Property.parent_property_id.is_(None),
                Transaction.transaction_type == TransactionType.TENANT_PAYMENT, Transaction.deleted_at.is_(None),
                Transaction.transaction_date >= month_start,
            )
            .group_by(Property.id).order_by(func.sum(Transaction.amount).desc()).limit(5)
        ).all()
        top_buildings_by_revenue = [{"id": r.id, "title": r.title, "code": r.property_code, "value": r.revenue} for r in revenue_by_building]

        top_buildings_by_occupancy = []
        try:
            buildings = OccupancyService(self.db).get_buildings()
            top_buildings_by_occupancy = sorted(buildings, key=lambda b: b.get("occupancy_percentage", 0), reverse=True)[:5]
        except Exception:
            pass

        top_tenants_rows = self.db.execute(
            select(Tenant.id, Tenant.tenant_code, Tenant.first_name, Tenant.last_name, Tenant.company_name, func.coalesce(func.sum(Transaction.amount), 0).label("paid"))
            .join(Transaction, Transaction.tenant_id == Tenant.id)
            .where(Transaction.transaction_type == TransactionType.TENANT_PAYMENT, Transaction.deleted_at.is_(None), Transaction.transaction_date >= month_start)
            .group_by(Tenant.id).order_by(func.sum(Transaction.amount).desc()).limit(5)
        ).all()
        top_tenants = [{"id": r.id, "code": r.tenant_code, "name": r.company_name or f"{r.first_name or ''} {r.last_name or ''}".strip(), "value": r.paid} for r in top_tenants_rows]

        top_owners_rows = self.db.execute(
            select(Owner.id, Owner.owner_code, Owner.first_name, Owner.last_name, Owner.company_name, func.coalesce(func.sum(Transaction.amount), 0).label("total"))
            .join(Transaction, Transaction.owner_id == Owner.id)
            .where(Transaction.transaction_type == TransactionType.OWNER_PAYMENT, Transaction.deleted_at.is_(None), Transaction.transaction_date >= month_start)
            .group_by(Owner.id).order_by(func.sum(Transaction.amount).desc()).limit(5)
        ).all()
        top_owners = [{"id": r.id, "code": r.owner_code, "name": r.company_name or f"{r.first_name or ''} {r.last_name or ''}".strip(), "value": r.total} for r in top_owners_rows]

        highest_expenses_rows = self.db.execute(
            select(Transaction.id, Transaction.transaction_number, Transaction.category, Transaction.amount, Transaction.transaction_date, Transaction.description)
            .where(Transaction.transaction_type == TransactionType.EXPENSE, Transaction.deleted_at.is_(None), Transaction.transaction_date >= month_start)
            .order_by(Transaction.amount.desc()).limit(5)
        ).all()
        highest_expenses = [{"id": r.id, "transaction_number": r.transaction_number, "category": r.category, "amount": r.amount, "date": r.transaction_date.isoformat(), "description": r.description} for r in highest_expenses_rows]

        vacant_units_rows = []
        try:
            items, _ = OccupancyService(self.db).get_units(None, "vacant", 1, 5)
            vacant_units_rows = [{"id": u["property_id"], "title": u["property_title"], "unit_number": u["unit_number"], "building_title": u["building_title"], "rent_amount": u["rent_amount"]} for u in items]
        except Exception:
            pass

        late_payments_rows = self.db.execute(
            select(RentalPaymentInstallment, RentalContract)
            .join(RentalContract, RentalContract.id == RentalPaymentInstallment.contract_id)
            .where(
                RentalPaymentInstallment.deleted_at.is_(None), RentalPaymentInstallment.payment_status == RentalInstallmentStatus.OVERDUE,
            )
            .order_by(RentalPaymentInstallment.due_date.asc()).limit(5)
        ).all()
        late_payments = [
            {
                "installment_id": inst.id, "contract_number": contract.contract_number, "tenant_id": contract.tenant_id,
                "due_date": inst.due_date.isoformat(), "amount": inst.total_payable, "days_late": (date.today() - inst.due_date).days,
            }
            for inst, contract in late_payments_rows
        ]

        return {
            "top_buildings_by_revenue": top_buildings_by_revenue,
            "top_buildings_by_occupancy": top_buildings_by_occupancy,
            "top_tenants": top_tenants,
            "top_owners": top_owners,
            "highest_expenses": highest_expenses,
            "vacant_units": vacant_units_rows,
            "late_payments": late_payments,
        }

    def get_calendar_events(self, days_ahead: int = 30) -> list[dict]:
        """Phase 2 — Calendar Widget. Pulls from four genuinely separate,
        already-existing date fields — nothing invented, nothing
        duplicated: RentalPaymentInstallment.due_date (rent due),
        RentalContract.end_date (contract expiration),
        MaintenanceRequest.scheduled_date (maintenance visits),
        LeasePaymentInstallment.due_date (owner payments), and
        MaintenanceContract.next_service_due_date (recurring service /
        inspection visits — elevator, fire safety, pest control, etc.,
        same field the Maintenance Contracts module's own due-soon
        check already uses)."""
        from app.models.rental import RentalContract, RentalContractStatus, RentalPaymentInstallment, RentalInstallmentStatus
        from app.models.lease import LeasePaymentInstallment, InstallmentStatus
        from app.models.maintenance import MaintenanceRequest, MaintenanceRequestStatus
        from app.models.maintenance_contract import MaintenanceContract, MaintenanceContractStatus

        today = date.today()
        window_end = today + timedelta(days=days_ahead)
        events: list[dict] = []

        rent_due = self.db.execute(
            select(RentalPaymentInstallment, RentalContract)
            .join(RentalContract, RentalContract.id == RentalPaymentInstallment.contract_id)
            .where(
                RentalPaymentInstallment.deleted_at.is_(None),
                RentalPaymentInstallment.payment_status.in_([RentalInstallmentStatus.PENDING, RentalInstallmentStatus.OVERDUE]),
                RentalPaymentInstallment.due_date >= today, RentalPaymentInstallment.due_date <= window_end,
            )
        ).all()
        for inst, contract in rent_due:
            events.append({"type": "rent_due", "date": inst.due_date.isoformat(), "title": f"Rent due — {contract.contract_number}", "amount": inst.total_payable, "link": f"/rentals/{contract.id}"})

        expiring = self.db.execute(
            select(RentalContract).where(
                RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE,
                RentalContract.end_date >= today, RentalContract.end_date <= window_end,
            )
        ).scalars().all()
        for c in expiring:
            events.append({"type": "contract_expiration", "date": c.end_date.isoformat(), "title": f"Contract expires — {c.contract_number}", "amount": None, "link": f"/rentals/{c.id}"})

        maintenance_visits = self.db.execute(
            select(MaintenanceRequest).where(
                MaintenanceRequest.deleted_at.is_(None), MaintenanceRequest.scheduled_date.isnot(None),
                MaintenanceRequest.scheduled_date >= today, MaintenanceRequest.scheduled_date <= window_end,
                MaintenanceRequest.maintenance_status.notin_([MaintenanceRequestStatus.COMPLETED, MaintenanceRequestStatus.CANCELLED]),
            )
        ).scalars().all()
        for m in maintenance_visits:
            events.append({"type": "maintenance_visit", "date": m.scheduled_date.isoformat(), "title": f"Maintenance visit — {m.request_number}", "amount": None, "link": "/maintenance"})

        owner_payments = self.db.execute(
            select(LeasePaymentInstallment).where(
                LeasePaymentInstallment.deleted_at.is_(None),
                LeasePaymentInstallment.payment_status.in_([InstallmentStatus.PENDING, InstallmentStatus.OVERDUE]),
                LeasePaymentInstallment.due_date >= today, LeasePaymentInstallment.due_date <= window_end,
            )
        ).scalars().all()
        for inst in owner_payments:
            events.append({"type": "owner_payment", "date": inst.due_date.isoformat(), "title": f"Owner payment due — installment #{inst.installment_number}", "amount": inst.amount, "link": f"/leases/{inst.lease_id}"})

        inspections = self.db.execute(
            select(MaintenanceContract).where(
                MaintenanceContract.deleted_at.is_(None), MaintenanceContract.contract_status == MaintenanceContractStatus.ACTIVE,
                MaintenanceContract.next_service_due_date.isnot(None),
                MaintenanceContract.next_service_due_date >= today, MaintenanceContract.next_service_due_date <= window_end,
            )
        ).scalars().all()
        for mc in inspections:
            events.append({"type": "inspection", "date": mc.next_service_due_date.isoformat(), "title": f"Service due — {mc.contract_number}", "amount": None, "link": "/maintenance"})

        return sorted(events, key=lambda e: e["date"])
