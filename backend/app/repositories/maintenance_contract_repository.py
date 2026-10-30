from datetime import date
from typing import Optional
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload
from app.models.maintenance_contract import MaintenanceContract, MaintenanceContractStatus
from app.models.maintenance import Contractor
from app.models.property import Property
from app.repositories.base import BaseRepository


class MaintenanceContractRepository(BaseRepository[MaintenanceContract]):
    def __init__(self, db: Session):
        super().__init__(MaintenanceContract, db)

    def next_contract_number(self) -> str:
        count = self.db.execute(select(func.count()).select_from(MaintenanceContract)).scalar_one()
        return f"MTC-{count + 1:06d}"

    def get_detail(self, contract_id: int) -> Optional[MaintenanceContract]:
        stmt = (
            select(MaintenanceContract)
            .options(selectinload(MaintenanceContract.property_ref), selectinload(MaintenanceContract.contractor))
            .where(MaintenanceContract.id == contract_id, MaintenanceContract.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_contracts(
        self, page: int, page_size: int, search: Optional[str], contract_status: Optional[str],
        property_id: Optional[int], contractor_id: Optional[int], service_type: Optional[str],
        expiring_soon: Optional[bool], sort_dir: str,
    ) -> tuple[list[MaintenanceContract], int]:
        stmt = (
            select(MaintenanceContract)
            .options(selectinload(MaintenanceContract.property_ref), selectinload(MaintenanceContract.contractor))
            .where(MaintenanceContract.deleted_at.is_(None))
        )
        if contract_status:
            stmt = stmt.where(MaintenanceContract.contract_status == contract_status)
        if property_id:
            stmt = stmt.where(MaintenanceContract.property_id == property_id)
        if contractor_id:
            stmt = stmt.where(MaintenanceContract.contractor_id == contractor_id)
        if service_type:
            stmt = stmt.where(MaintenanceContract.service_type == service_type)
        if search:
            like = f"%{search}%"
            stmt = (
                stmt.join(Property, Property.id == MaintenanceContract.property_id, isouter=True)
                .join(Contractor, Contractor.id == MaintenanceContract.contractor_id, isouter=True)
                .where(or_(
                    MaintenanceContract.contract_number.ilike(like),
                    MaintenanceContract.title.ilike(like),
                    Property.title.ilike(like),
                    Contractor.company_name.ilike(like),
                ))
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        column = MaintenanceContract.end_date
        stmt = stmt.order_by(column.desc() if sort_dir == "desc" else column.asc(), MaintenanceContract.id.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())

        if expiring_soon:
            items = [c for c in items if c.is_expiring_soon]

        return items, total

    def get_expiring_soon(self) -> list[MaintenanceContract]:
        """Active contracts whose end_date falls within their own
        renewal_notice_days window — mirrors LeaseRepository.get_expiring_soon
        (Phase 3) exactly."""
        stmt = (
            select(MaintenanceContract)
            .options(selectinload(MaintenanceContract.property_ref), selectinload(MaintenanceContract.contractor))
            .where(
                MaintenanceContract.deleted_at.is_(None),
                MaintenanceContract.contract_status == MaintenanceContractStatus.ACTIVE,
            )
        )
        all_active = list(self.db.execute(stmt).scalars().all())
        return [c for c in all_active if c.is_expiring_soon]

    def get_service_due_soon(self) -> list[MaintenanceContract]:
        """Active contracts whose *next scheduled visit* (not the contract
        end date) is due within 14 days or already overdue — the elevator/
        AC-specific concern this extension exists for."""
        stmt = (
            select(MaintenanceContract)
            .options(selectinload(MaintenanceContract.property_ref), selectinload(MaintenanceContract.contractor))
            .where(
                MaintenanceContract.deleted_at.is_(None),
                MaintenanceContract.contract_status == MaintenanceContractStatus.ACTIVE,
                MaintenanceContract.next_service_due_date.is_not(None),
            )
        )
        all_active = list(self.db.execute(stmt).scalars().all())
        return [c for c in all_active if c.is_service_due_soon or c.is_service_overdue]

    def auto_expire_overdue_contracts(self) -> int:
        """Flips ACTIVE contracts whose end_date has passed to EXPIRED.
        Idempotent; intended to be called on a schedule or on-demand —
        mirrors LeaseRepository.auto_expire_overdue_leases (Phase 3)."""
        stmt = select(MaintenanceContract).where(
            MaintenanceContract.deleted_at.is_(None),
            MaintenanceContract.contract_status == MaintenanceContractStatus.ACTIVE,
            MaintenanceContract.end_date < date.today(),
        )
        contracts = list(self.db.execute(stmt).scalars().all())
        for contract in contracts:
            contract.contract_status = MaintenanceContractStatus.EXPIRED
        return len(contracts)

    def dashboard_counts(self) -> dict:
        base = select(func.count()).select_from(MaintenanceContract).where(MaintenanceContract.deleted_at.is_(None))
        total = self.db.execute(base).scalar_one()

        def count_status(s):
            return self.db.execute(base.where(MaintenanceContract.contract_status == s)).scalar_one()

        return {
            "total_contracts": total,
            "active_contracts": count_status(MaintenanceContractStatus.ACTIVE),
            "draft_contracts": count_status(MaintenanceContractStatus.DRAFT),
            "expiring_soon": len(self.get_expiring_soon()),
            "service_due_soon": len(self.get_service_due_soon()),
            "terminated_contracts": count_status(MaintenanceContractStatus.TERMINATED),
        }
