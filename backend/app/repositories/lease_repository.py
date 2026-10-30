from datetime import date
from typing import Optional
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload
from app.models.lease import LeaseAgreement, LeasePaymentInstallment, LeaseStatus, InstallmentStatus
from app.models.owner import Owner
from app.models.base import RecordStatus
from app.repositories.base import BaseRepository


class LeaseRepository(BaseRepository[LeaseAgreement]):
    def __init__(self, db: Session):
        super().__init__(LeaseAgreement, db)

    def get_detail(self, lease_id: int) -> Optional[LeaseAgreement]:
        stmt = (
            select(LeaseAgreement)
            .options(selectinload(LeaseAgreement.installments), selectinload(LeaseAgreement.owner), selectinload(LeaseAgreement.property_ref))
            .where(LeaseAgreement.id == lease_id, LeaseAgreement.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def next_contract_number(self) -> str:
        stmt = select(func.count()).select_from(LeaseAgreement)
        count = self.db.execute(stmt).scalar_one()
        return f"LSE-{count + 1:06d}"

    def list_leases(
        self, page: int, page_size: int, search: Optional[str], contract_status: Optional[str],
        owner_id: Optional[int], branch_id: Optional[int], expiring_soon: Optional[bool],
        sort_by: Optional[str], sort_dir: str, include_archived: bool = False,
    ) -> tuple[list[LeaseAgreement], int]:
        stmt = (
            select(LeaseAgreement)
            .options(selectinload(LeaseAgreement.owner), selectinload(LeaseAgreement.property_ref))
            .where(LeaseAgreement.deleted_at.is_(None))
        )
        if not include_archived:
            stmt = stmt.where(LeaseAgreement.status != RecordStatus.ARCHIVED)

        if contract_status:
            stmt = stmt.where(LeaseAgreement.contract_status == contract_status)
        if owner_id:
            stmt = stmt.where(LeaseAgreement.owner_id == owner_id)
        if branch_id:
            stmt = stmt.where(LeaseAgreement.branch_id == branch_id)
        if search:
            like = f"%{search}%"
            stmt = stmt.join(Owner, Owner.id == LeaseAgreement.owner_id, isouter=True).where(or_(
                LeaseAgreement.contract_number.ilike(like),
                LeaseAgreement.property_reference.ilike(like),
                Owner.first_name.ilike(like),
                Owner.last_name.ilike(like),
                Owner.company_name.ilike(like),
            ))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        sort_column_map = {
            "created_at": LeaseAgreement.created_at,
            "contract_number": LeaseAgreement.contract_number,
            "start_date": LeaseAgreement.start_date,
            "end_date": LeaseAgreement.end_date,
        }
        column = sort_column_map.get(sort_by, LeaseAgreement.created_at)
        stmt = stmt.order_by(column.desc() if sort_dir == "desc" else column.asc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        items = list(self.db.execute(stmt).scalars().all())

        if expiring_soon:
            items = [i for i in items if i.is_expiring_soon]

        return items, total

    def get_expiring_soon(self) -> list[LeaseAgreement]:
        """Active leases whose end_date falls within their own renewal_notice_days window."""
        stmt = (
            select(LeaseAgreement)
            .options(selectinload(LeaseAgreement.owner))
            .where(
                LeaseAgreement.deleted_at.is_(None),
                LeaseAgreement.contract_status == LeaseStatus.ACTIVE,
            )
        )
        all_active = list(self.db.execute(stmt).scalars().all())
        return [lease for lease in all_active if lease.is_expiring_soon]

    def dashboard_counts(self) -> dict:
        base = select(func.count()).select_from(LeaseAgreement).where(LeaseAgreement.deleted_at.is_(None))
        total = self.db.execute(base).scalar_one()
        active = self.db.execute(base.where(LeaseAgreement.contract_status == LeaseStatus.ACTIVE)).scalar_one()
        draft = self.db.execute(base.where(LeaseAgreement.contract_status == LeaseStatus.DRAFT)).scalar_one()
        terminated = self.db.execute(base.where(LeaseAgreement.contract_status == LeaseStatus.TERMINATED)).scalar_one()

        expiring = self.get_expiring_soon()

        # Same fix as RentalContractRepository.dashboard_counts(): only
        # installments actually due as of today, not the whole
        # remaining contract's worth of future, not-yet-due installments.
        from datetime import date as _date
        outstanding_stmt = select(func.coalesce(func.sum(LeasePaymentInstallment.amount), 0)).where(
            LeasePaymentInstallment.payment_status.in_([InstallmentStatus.PENDING, InstallmentStatus.OVERDUE]),
            LeasePaymentInstallment.due_date <= _date.today(),
            LeasePaymentInstallment.deleted_at.is_(None),
        )
        outstanding = self.db.execute(outstanding_stmt).scalar_one()

        return {
            "total_leases": total,
            "active_leases": active,
            "draft_leases": draft,
            "expiring_soon": len(expiring),
            "terminated_leases": terminated,
            "total_outstanding_amount": outstanding,
            "upcoming_renewals": expiring[:10],
        }

    def auto_expire_overdue_leases(self) -> int:
        """Flips ACTIVE leases whose end_date has passed to EXPIRED. Idempotent;
        intended to be called on a schedule (see docs/phase3-*) or on-demand."""
        stmt = select(LeaseAgreement).where(
            LeaseAgreement.deleted_at.is_(None),
            LeaseAgreement.contract_status == LeaseStatus.ACTIVE,
            LeaseAgreement.end_date < date.today(),
        )
        leases = list(self.db.execute(stmt).scalars().all())
        for lease in leases:
            lease.contract_status = LeaseStatus.EXPIRED
        return len(leases)


class LeasePaymentInstallmentRepository(BaseRepository[LeasePaymentInstallment]):
    def __init__(self, db: Session):
        super().__init__(LeasePaymentInstallment, db)

    def list_for_lease(self, lease_id: int) -> list[LeasePaymentInstallment]:
        stmt = select(LeasePaymentInstallment).where(
            LeasePaymentInstallment.lease_id == lease_id, LeasePaymentInstallment.deleted_at.is_(None)
        ).order_by(LeasePaymentInstallment.due_date.asc())
        return list(self.db.execute(stmt).scalars().all())

    def next_installment_number(self, lease_id: int) -> int:
        stmt = select(func.count()).select_from(LeasePaymentInstallment).where(LeasePaymentInstallment.lease_id == lease_id)
        return self.db.execute(stmt).scalar_one() + 1

    def mark_overdue_past_due(self) -> int:
        stmt = select(LeasePaymentInstallment).where(
            LeasePaymentInstallment.deleted_at.is_(None),
            LeasePaymentInstallment.payment_status == InstallmentStatus.PENDING,
            LeasePaymentInstallment.due_date < date.today(),
        )
        items = list(self.db.execute(stmt).scalars().all())
        for i in items:
            i.payment_status = InstallmentStatus.OVERDUE
        return len(items)
