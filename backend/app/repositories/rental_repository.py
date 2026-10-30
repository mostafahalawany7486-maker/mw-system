from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload
from app.models.rental import RentalContract, RentalPaymentInstallment, RentalContractStatus, RentalInstallmentStatus
from app.models.tenant import Tenant
from app.models.property import Property
from app.models.base import RecordStatus
from app.repositories.base import BaseRepository


class RentalContractRepository(BaseRepository[RentalContract]):
    def __init__(self, db: Session):
        super().__init__(RentalContract, db)

    def list_by_property_ids(self, property_ids: list[int], contract_status: Optional[str], page: int, page_size: int) -> tuple[list[RentalContract], int]:
        """Building Management: leases across a building AND its units
        (property_ids = [building_id] + unit ids), reusing the same
        RentalContract table and RentalContractListItemOut schema as the
        existing Rental Contracts module — no new entity."""
        if not property_ids:
            return [], 0
        stmt = (
            select(RentalContract)
            .options(selectinload(RentalContract.tenant), selectinload(RentalContract.property_ref))
            .where(RentalContract.deleted_at.is_(None), RentalContract.property_id.in_(property_ids))
        )
        if contract_status:
            stmt = stmt.where(RentalContract.contract_status == contract_status)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(RentalContract.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def list_active_for_billing(self, property_ids: Optional[list[int]] = None, as_of: Optional[date] = None) -> list[RentalContract]:
        """Rent Billing Engine: every active contract whose term covers
        `as_of` (defaults to today), optionally scoped to a set of
        property ids (building/property/owner-level bulk generation all
        reduce to "a set of property ids" the same way Building
        Management's tenant/lease/maintenance rollups already do)."""
        as_of = as_of or date.today()
        stmt = (
            select(RentalContract)
            .options(selectinload(RentalContract.tenant), selectinload(RentalContract.property_ref))
            .where(
                RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE,
                RentalContract.start_date <= as_of, RentalContract.end_date >= as_of,
            )
        )
        if property_ids:
            stmt = stmt.where(RentalContract.property_id.in_(property_ids))
        return list(self.db.execute(stmt).scalars().all())

    def count_by_property_ids_and_status(self, property_ids: list[int], contract_status: str) -> int:
        if not property_ids:
            return 0
        stmt = select(func.count()).select_from(RentalContract).where(
            RentalContract.deleted_at.is_(None), RentalContract.property_id.in_(property_ids), RentalContract.contract_status == contract_status,
        )
        return self.db.execute(stmt).scalar_one()

    def list_active_by_property_ids(self, property_ids: list[int]) -> list[RentalContract]:
        """Every ACTIVE contract for this set of units, by status alone
        — deliberately not date-range-narrowed like
        list_active_for_billing() above (that method additionally
        requires today to fall within start_date/end_date, which is the
        right check for billing but would silently disagree with
        OccupancyDataRepository.get_active_contract's own active-contract
        definition, which is status-only — see
        business_workflows/occupancy/occupancy_engine.py). Used by the
        Occupancy Engine's unit listing so the displayed tenant/contract
        details always match the status the engine actually computed."""
        if not property_ids:
            return []
        stmt = select(RentalContract).options(selectinload(RentalContract.tenant)).where(
            RentalContract.deleted_at.is_(None), RentalContract.property_id.in_(property_ids), RentalContract.contract_status == RentalContractStatus.ACTIVE,
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_expiring_soon_by_property_ids(self, property_ids: list[int]) -> int:
        """Same `is_expiring_soon` computed property used by get_expiring_soon()
        (per-contract renewal_notice_days window, not a fixed constant) —
        scoped to a building/villa and its units, for the Property Summary."""
        if not property_ids:
            return 0
        stmt = select(RentalContract).where(
            RentalContract.deleted_at.is_(None),
            RentalContract.property_id.in_(property_ids),
            RentalContract.contract_status == RentalContractStatus.ACTIVE,
        )
        contracts = self.db.execute(stmt).scalars().all()
        return sum(1 for c in contracts if c.is_expiring_soon)

    def distinct_tenant_ids_by_property_ids(self, property_ids: list[int]) -> list[int]:
        if not property_ids:
            return []
        stmt = select(func.distinct(RentalContract.tenant_id)).where(
            RentalContract.deleted_at.is_(None), RentalContract.property_id.in_(property_ids),
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_detail(self, contract_id: int) -> Optional[RentalContract]:
        stmt = (
            select(RentalContract)
            .options(selectinload(RentalContract.installments), selectinload(RentalContract.tenant), selectinload(RentalContract.property_ref))
            .where(RentalContract.id == contract_id, RentalContract.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def next_contract_number(self) -> str:
        stmt = select(func.count()).select_from(RentalContract)
        count = self.db.execute(stmt).scalar_one()
        return f"RNT-{count + 1:06d}"

    def list_contracts(
        self, page: int, page_size: int, search: Optional[str], contract_status: Optional[str],
        tenant_id: Optional[int], property_id: Optional[int], branch_id: Optional[int], expiring_soon: Optional[bool],
        sort_by: Optional[str], sort_dir: str, include_archived: bool = False, building_id: Optional[int] = None,
    ) -> tuple[list[RentalContract], int]:
        stmt = (
            select(RentalContract)
            .options(selectinload(RentalContract.tenant), selectinload(RentalContract.property_ref))
            .where(RentalContract.deleted_at.is_(None))
        )
        if not include_archived:
            stmt = stmt.where(RentalContract.status != RecordStatus.ARCHIVED)

        if contract_status:
            stmt = stmt.where(RentalContract.contract_status == contract_status)
        if tenant_id:
            stmt = stmt.where(RentalContract.tenant_id == tenant_id)
        if property_id:
            stmt = stmt.where(RentalContract.property_id == property_id)
        if building_id:
            # Cascading Property Selector follow-up: "show every contract
            # under this building" — a contract's property_id is usually a
            # specific unit (child of the building), not the building row
            # itself, so a plain property_id == building_id match would
            # wrongly return zero rows. Matches the building itself (for
            # the rare case a contract is against the whole building) OR
            # any of its child units, via the same parent_property_id
            # relationship the rest of the hierarchy already uses.
            unit_ids_subq = select(Property.id).where(Property.parent_property_id == building_id)
            stmt = stmt.where(or_(RentalContract.property_id == building_id, RentalContract.property_id.in_(unit_ids_subq)))
        if branch_id:
            stmt = stmt.where(RentalContract.branch_id == branch_id)
        if search:
            like = f"%{search}%"
            stmt = (
                stmt.join(Tenant, Tenant.id == RentalContract.tenant_id, isouter=True)
                .join(Property, Property.id == RentalContract.property_id, isouter=True)
                .where(or_(
                    RentalContract.contract_number.ilike(like),
                    Tenant.first_name.ilike(like),
                    Tenant.last_name.ilike(like),
                    Tenant.company_name.ilike(like),
                    Property.title.ilike(like),
                    Property.property_code.ilike(like),
                ))
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        sort_column_map = {
            "created_at": RentalContract.created_at,
            "contract_number": RentalContract.contract_number,
            "start_date": RentalContract.start_date,
            "end_date": RentalContract.end_date,
        }
        column = sort_column_map.get(sort_by, RentalContract.created_at)
        stmt = stmt.order_by(column.desc() if sort_dir == "desc" else column.asc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def get_expiring_soon(self) -> list[RentalContract]:
        stmt = (
            select(RentalContract)
            .options(selectinload(RentalContract.tenant), selectinload(RentalContract.property_ref))
            .where(
                RentalContract.deleted_at.is_(None),
                RentalContract.contract_status == RentalContractStatus.ACTIVE,
            )
        )
        all_active = list(self.db.execute(stmt).scalars().all())
        return [c for c in all_active if c.is_expiring_soon]

    def dashboard_counts(self) -> dict:
        base = select(func.count()).select_from(RentalContract).where(RentalContract.deleted_at.is_(None))
        total = self.db.execute(base).scalar_one()
        active = self.db.execute(base.where(RentalContract.contract_status == RentalContractStatus.ACTIVE)).scalar_one()
        draft = self.db.execute(base.where(RentalContract.contract_status == RentalContractStatus.DRAFT)).scalar_one()
        terminated = self.db.execute(base.where(RentalContract.contract_status == RentalContractStatus.TERMINATED)).scalar_one()

        expiring = self.get_expiring_soon()

        # Outstanding = what's actually due right now, not the whole
        # remaining contract. A 12-month contract creates 12 pending
        # installments upfront (one per month) — without the due_date
        # filter below, this summed all 12 immediately, showing a full
        # year's rent as "outstanding" the day the contract was signed,
        # long before 11 of those installments have even come due.
        from datetime import date as _date
        outstanding_stmt = select(func.coalesce(func.sum(
            RentalPaymentInstallment.amount - RentalPaymentInstallment.discount_amount
            + RentalPaymentInstallment.tax_amount + RentalPaymentInstallment.late_fee_amount
        ), 0)).where(
            RentalPaymentInstallment.payment_status.in_([RentalInstallmentStatus.PENDING, RentalInstallmentStatus.OVERDUE]),
            RentalPaymentInstallment.due_date <= _date.today(),
            RentalPaymentInstallment.deleted_at.is_(None),
        )
        outstanding = self.db.execute(outstanding_stmt).scalar_one()

        return {
            "total_contracts": total,
            "active_contracts": active,
            "draft_contracts": draft,
            "expiring_soon": len(expiring),
            "terminated_contracts": terminated,
            "total_outstanding_amount": outstanding,
            "upcoming_renewals": expiring[:10],
        }

    def auto_expire_overdue_contracts(self) -> int:
        stmt = select(RentalContract).where(
            RentalContract.deleted_at.is_(None),
            RentalContract.contract_status == RentalContractStatus.ACTIVE,
            RentalContract.end_date < date.today(),
        )
        contracts = list(self.db.execute(stmt).scalars().all())
        for c in contracts:
            c.contract_status = RentalContractStatus.EXPIRED
        return len(contracts)


class RentalInstallmentRepository(BaseRepository[RentalPaymentInstallment]):
    def __init__(self, db: Session):
        super().__init__(RentalPaymentInstallment, db)

    def list_for_contract(self, contract_id: int) -> list[RentalPaymentInstallment]:
        stmt = select(RentalPaymentInstallment).where(
            RentalPaymentInstallment.contract_id == contract_id, RentalPaymentInstallment.deleted_at.is_(None)
        ).order_by(RentalPaymentInstallment.due_date.asc())
        return list(self.db.execute(stmt).scalars().all())

    def next_installment_number(self, contract_id: int) -> int:
        stmt = select(func.count()).select_from(RentalPaymentInstallment).where(RentalPaymentInstallment.contract_id == contract_id)
        return self.db.execute(stmt).scalar_one() + 1

    def assess_late_fees_and_mark_overdue(self) -> tuple[int, int]:
        """For pending installments past due_date: mark overdue, and — once
        also past the contract's grace period — assess a late fee (only
        once; re-running the sweep won't stack fees)."""
        stmt = (
            select(RentalPaymentInstallment)
            .options(selectinload(RentalPaymentInstallment.contract))
            .where(
                RentalPaymentInstallment.deleted_at.is_(None),
                RentalPaymentInstallment.payment_status == RentalInstallmentStatus.PENDING,
                RentalPaymentInstallment.due_date < date.today(),
            )
        )
        items = list(self.db.execute(stmt).scalars().all())
        overdue_count = 0
        late_fee_count = 0
        for inst in items:
            inst.payment_status = RentalInstallmentStatus.OVERDUE
            overdue_count += 1
            contract = inst.contract
            if not contract:
                continue
            days_overdue = (date.today() - inst.due_date).days
            if days_overdue > contract.late_fee_grace_period_days and inst.late_fee_amount == 0:
                if contract.late_fee_type == "percentage":
                    inst.late_fee_amount = (inst.amount * contract.late_fee_value / Decimal("100")).quantize(Decimal("0.01"))
                else:
                    inst.late_fee_amount = contract.late_fee_value
                late_fee_count += 1
        return overdue_count, late_fee_count

    # ---------------- Rental Receipt Module ----------------
    def next_receipt_number(self) -> str:
        stmt = select(func.count()).select_from(RentalPaymentInstallment).where(RentalPaymentInstallment.receipt_number.isnot(None))
        return f"RR-{self.db.execute(stmt).scalar_one() + 1:06d}"

    def due_this_month_for_active_contracts(self, year: int, month: int) -> list[RentalPaymentInstallment]:
        """Installments due in the given month, for contracts that are
        currently active — this is what "beginning of the month, prepare
        receipts for active leases" resolves to: the schedule already
        exists (generated when the lease started), so "generating a
        receipt" means assigning a receipt_number to the row that's
        already there, not creating a new one."""
        stmt = (
            select(RentalPaymentInstallment)
            .join(RentalContract, RentalContract.id == RentalPaymentInstallment.contract_id)
            .options(selectinload(RentalPaymentInstallment.contract))
            .where(
                RentalPaymentInstallment.deleted_at.is_(None), RentalContract.deleted_at.is_(None),
                RentalContract.contract_status == RentalContractStatus.ACTIVE,
                func.extract("year", RentalPaymentInstallment.due_date) == year,
                func.extract("month", RentalPaymentInstallment.due_date) == month,
            )
            .order_by(RentalPaymentInstallment.due_date.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_with_context(self, installment_id: int) -> Optional[RentalPaymentInstallment]:
        """Eager-loads everything the printable receipt needs in one
        query: contract -> tenant, contract -> property (-> parent
        building)."""
        stmt = (
            select(RentalPaymentInstallment)
            .options(
                selectinload(RentalPaymentInstallment.contract).selectinload(RentalContract.tenant),
                selectinload(RentalPaymentInstallment.contract).selectinload(RentalContract.property_ref).selectinload(Property.parent),
            )
            .where(RentalPaymentInstallment.id == installment_id, RentalPaymentInstallment.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def search_receipts(
        self, page: int, page_size: int, receipt_number: Optional[str], tenant_id: Optional[int],
        property_id: Optional[int], rental_month: Optional[str], date_from: Optional[date], date_to: Optional[date],
        payment_method: Optional[str], reference_number: Optional[str],
    ) -> tuple[list[RentalPaymentInstallment], int]:
        stmt = (
            select(RentalPaymentInstallment)
            .join(RentalContract, RentalContract.id == RentalPaymentInstallment.contract_id)
            .options(
                selectinload(RentalPaymentInstallment.contract).selectinload(RentalContract.tenant),
                selectinload(RentalPaymentInstallment.contract).selectinload(RentalContract.property_ref),
            )
            .where(RentalPaymentInstallment.deleted_at.is_(None), RentalPaymentInstallment.receipt_number.isnot(None))
        )
        if receipt_number:
            stmt = stmt.where(RentalPaymentInstallment.receipt_number.ilike(f"%{receipt_number}%"))
        if tenant_id:
            stmt = stmt.where(RentalContract.tenant_id == tenant_id)
        if property_id:
            stmt = stmt.where(RentalContract.property_id == property_id)
        if rental_month:
            year, month = int(rental_month[:4]), int(rental_month[5:7])
            stmt = stmt.where(func.extract("year", RentalPaymentInstallment.due_date) == year, func.extract("month", RentalPaymentInstallment.due_date) == month)
        if date_from:
            stmt = stmt.where(RentalPaymentInstallment.due_date >= date_from)
        if date_to:
            stmt = stmt.where(RentalPaymentInstallment.due_date <= date_to)
        if payment_method:
            stmt = stmt.where(RentalPaymentInstallment.payment_method == payment_method)
        if reference_number:
            stmt = stmt.where(RentalPaymentInstallment.reference_number.ilike(f"%{reference_number}%"))

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(RentalPaymentInstallment.due_date.desc()).offset((page - 1) * page_size).limit(page_size)
        return list(self.db.execute(stmt).scalars().all()), total
