"""
Property Hub Summary — "everything about this property, on one screen."

Composes entirely from existing, already-tested services and
repositories (Occupancy Engine's per-building summary, Financial
transactions, Maintenance requests, the Owner Ledger, Lease/Rental
installments) — nothing here re-derives math that already exists
elsewhere. This is a read-only aggregation layer, same pattern as
DashboardService.get_summary() and PropertyHierarchyService.
"""
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.property import Property
from app.models.lease import LeaseAgreement, LeaseStatus, LeasePaymentInstallment, InstallmentStatus
from app.models.rental import RentalContract, RentalContractStatus, RentalPaymentInstallment, RentalInstallmentStatus
from app.models.financial import Transaction, TransactionType
from app.models.maintenance import MaintenanceRequest, MaintenanceRequestStatus, MaintenanceMaterial, MaintenanceLaborCost
from app.models.system import ActivityLog
from app.repositories.property_repository import PropertyRepository
from app.business_workflows.occupancy.occupancy_service import OccupancyService

UPCOMING_WINDOW_DAYS = 14


class PropertyHubService:
    def __init__(self, db: Session):
        self.db = db
        self.property_repo = PropertyRepository(db)

    def get_summary(self, property_id: int) -> dict:
        building = self.property_repo.get(property_id)
        unit_ids = self.property_repo.get_unit_ids(property_id)
        all_ids = [property_id] + unit_ids

        occupancy = OccupancyService(self.db).get_buildings(property_id)[0]

        today = date.today()
        window_end = today + timedelta(days=UPCOMING_WINDOW_DAYS)

        # Upcoming rent due (tenant -> company) within the window, across
        # this building and all its units.
        upcoming_rent = self.db.execute(
            select(func.coalesce(func.sum(RentalPaymentInstallment.amount + RentalPaymentInstallment.late_fee_amount + RentalPaymentInstallment.tax_amount - RentalPaymentInstallment.discount_amount), 0))
            .join(RentalContract, RentalContract.id == RentalPaymentInstallment.contract_id)
            .where(
                RentalContract.property_id.in_(all_ids),
                RentalPaymentInstallment.payment_status.in_([RentalInstallmentStatus.PENDING, RentalInstallmentStatus.OVERDUE]),
                RentalPaymentInstallment.due_date <= window_end,
            )
        ).scalar_one()

        # This building's own Master Lease (Owner -> Company), if any —
        # a building rented from its owner is expected to have exactly
        # one active one, per the confirmed business model.
        master_lease = self.db.execute(
            select(LeaseAgreement).where(LeaseAgreement.property_id == property_id, LeaseAgreement.deleted_at.is_(None), LeaseAgreement.contract_status == LeaseStatus.ACTIVE)
        ).scalars().first()

        upcoming_owner_payment = Decimal("0")
        if master_lease:
            upcoming_owner_payment = self.db.execute(
                select(func.coalesce(func.sum(LeasePaymentInstallment.amount), 0))
                .where(
                    LeasePaymentInstallment.lease_id == master_lease.id,
                    LeasePaymentInstallment.payment_status.in_([InstallmentStatus.PENDING, InstallmentStatus.OVERDUE]),
                    LeasePaymentInstallment.due_date <= window_end,
                )
            ).scalar_one()

        # This month's rough profit estimate: rent actually collected,
        # minus maintenance costs actually incurred, minus owner
        # payments actually made — all for this building this calendar
        # month. Deliberately labelled an ESTIMATE in the response: real
        # accounting profit would also need depreciation, non-rent
        # income, etc., which is out of scope for a one-screen snapshot.
        month_start = today.replace(day=1)
        income_this_month = self.db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.property_id.in_(all_ids), Transaction.transaction_type == TransactionType.TENANT_PAYMENT,
                Transaction.transaction_date >= month_start, Transaction.transaction_date <= today, Transaction.deleted_at.is_(None),
            )
        ).scalar_one()
        owner_paid_this_month = self.db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.property_id.in_(all_ids), Transaction.transaction_type == TransactionType.OWNER_PAYMENT,
                Transaction.transaction_date >= month_start, Transaction.transaction_date <= today, Transaction.deleted_at.is_(None),
            )
        ).scalar_one()
        maintenance_material_cost = self.db.execute(
            select(func.coalesce(func.sum(MaintenanceMaterial.quantity * MaintenanceMaterial.unit_cost), 0))
            .join(MaintenanceRequest, MaintenanceRequest.id == MaintenanceMaterial.request_id)
            .where(MaintenanceRequest.property_id.in_(all_ids), MaintenanceRequest.reported_date >= month_start)
        ).scalar_one()
        maintenance_labor_cost = self.db.execute(
            select(func.coalesce(func.sum(MaintenanceLaborCost.hours * MaintenanceLaborCost.hourly_rate), 0))
            .join(MaintenanceRequest, MaintenanceRequest.id == MaintenanceLaborCost.request_id)
            .where(MaintenanceRequest.property_id.in_(all_ids), MaintenanceRequest.reported_date >= month_start)
        ).scalar_one()
        maintenance_cost_this_month = maintenance_material_cost + maintenance_labor_cost
        estimated_profit_this_month = income_this_month - owner_paid_this_month - maintenance_cost_this_month

        open_maintenance_count = self.db.execute(
            select(func.count()).select_from(MaintenanceRequest).where(
                MaintenanceRequest.property_id.in_(all_ids), MaintenanceRequest.deleted_at.is_(None),
                MaintenanceRequest.maintenance_status.notin_([MaintenanceRequestStatus.COMPLETED, MaintenanceRequestStatus.CANCELLED]),
            )
        ).scalar_one()

        recent_activity = self.db.execute(
            select(ActivityLog).where(ActivityLog.entity_type == "property", ActivityLog.entity_id == property_id)
            .order_by(ActivityLog.created_at.desc()).limit(8)
        ).scalars().all()

        alerts = []
        if occupancy["vacant_units"] > 0:
            alerts.append({"severity": "info", "message": f"{occupancy['vacant_units']} vacant unit(s)"})
        if occupancy["expiring_contracts"] > 0:
            alerts.append({"severity": "warning", "message": f"{occupancy['expiring_contracts']} contract(s) expiring soon"})
        if open_maintenance_count > 0:
            alerts.append({"severity": "warning", "message": f"{open_maintenance_count} open maintenance request(s)"})
        if upcoming_rent > 0:
            alerts.append({"severity": "info", "message": f"{upcoming_rent} due from tenants in the next {UPCOMING_WINDOW_DAYS} days"})
        if upcoming_owner_payment > 0:
            alerts.append({"severity": "info", "message": f"{upcoming_owner_payment} owed to owner in the next {UPCOMING_WINDOW_DAYS} days"})

        return {
            "property_id": property_id,
            "owner_id": building.owner_id if building else None,
            "owner_display_name": building.owner.display_name if building and building.owner else None,
            "master_lease_id": master_lease.id if master_lease else None,
            "master_lease_contract_number": master_lease.contract_number if master_lease else None,
            "occupied_units": occupancy["occupied_units"],
            "vacant_units": occupancy["vacant_units"],
            "occupancy_percentage": occupancy["occupancy_percentage"],
            "active_contracts": occupancy["active_contracts"],
            "expiring_contracts": occupancy["expiring_contracts"],
            "upcoming_rent_due": upcoming_rent,
            "upcoming_owner_payment_due": upcoming_owner_payment,
            "upcoming_window_days": UPCOMING_WINDOW_DAYS,
            "income_this_month": income_this_month,
            "owner_paid_this_month": owner_paid_this_month,
            "maintenance_cost_this_month": maintenance_cost_this_month,
            "estimated_profit_this_month": estimated_profit_this_month,
            "open_maintenance_count": open_maintenance_count,
            "alerts": alerts,
            "recent_activity": [
                {"action": a.action, "description": a.description, "created_at": a.created_at.isoformat()}
                for a in recent_activity
            ],
        }
