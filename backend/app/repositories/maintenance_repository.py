from datetime import date
from typing import Optional
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload
from app.models.maintenance import (
    Contractor, Technician, MaintenanceRequest, MaintenanceRequestStatus,
    MaintenanceMaterial, MaintenanceLaborCost, MaintenancePhoto,
)
from app.models.property import Property
from app.models.tenant import Tenant
from app.repositories.base import BaseRepository


class ContractorRepository(BaseRepository[Contractor]):
    def __init__(self, db: Session):
        super().__init__(Contractor, db)

    def next_contractor_code(self) -> str:
        count = self.db.execute(select(func.count()).select_from(Contractor)).scalar_one()
        return f"CON-{count + 1:06d}"

    def technician_count(self, contractor_id: int) -> int:
        stmt = select(func.count()).select_from(Technician).where(
            Technician.contractor_id == contractor_id, Technician.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one()

    def list_active(self) -> list[Contractor]:
        stmt = select(Contractor).where(Contractor.deleted_at.is_(None)).order_by(Contractor.company_name)
        return list(self.db.execute(stmt).scalars().all())


class TechnicianRepository(BaseRepository[Technician]):
    def __init__(self, db: Session):
        super().__init__(Technician, db)

    def next_technician_code(self) -> str:
        count = self.db.execute(select(func.count()).select_from(Technician)).scalar_one()
        return f"TEC-{count + 1:06d}"

    def get_detail(self, technician_id: int) -> Optional[Technician]:
        stmt = select(Technician).options(selectinload(Technician.contractor)).where(
            Technician.id == technician_id, Technician.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_with_contractor(self, page: int, page_size: int, search: Optional[str]) -> tuple[list[Technician], int]:
        stmt = select(Technician).options(selectinload(Technician.contractor)).where(Technician.deleted_at.is_(None))
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(Technician.first_name.ilike(like), Technician.last_name.ilike(like), Technician.technician_code.ilike(like)))
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(Technician.first_name).offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def list_active(self) -> list[Technician]:
        stmt = select(Technician).options(selectinload(Technician.contractor)).where(Technician.deleted_at.is_(None)).order_by(Technician.first_name)
        return list(self.db.execute(stmt).scalars().all())


class MaintenanceRequestRepository(BaseRepository[MaintenanceRequest]):
    def __init__(self, db: Session):
        super().__init__(MaintenanceRequest, db)

    def list_by_property_ids(self, property_ids: list[int], page: int, page_size: int) -> tuple[list[MaintenanceRequest], int]:
        """Building Management: maintenance requests across a building AND
        its units (property_ids = [building_id] + unit ids), reusing the
        same MaintenanceRequest table and list schema as the existing
        Maintenance module — no new entity."""
        if not property_ids:
            return [], 0
        stmt = (
            select(MaintenanceRequest)
            .options(
                selectinload(MaintenanceRequest.property_ref), selectinload(MaintenanceRequest.tenant),
                selectinload(MaintenanceRequest.assigned_contractor), selectinload(MaintenanceRequest.assigned_technician),
                selectinload(MaintenanceRequest.materials), selectinload(MaintenanceRequest.labor_entries),
            )
            .where(MaintenanceRequest.deleted_at.is_(None), MaintenanceRequest.property_id.in_(property_ids))
        )
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(MaintenanceRequest.reported_date.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def count_open_by_property_ids(self, property_ids: list[int]) -> int:
        if not property_ids:
            return 0
        stmt = select(func.count()).select_from(MaintenanceRequest).where(
            MaintenanceRequest.deleted_at.is_(None), MaintenanceRequest.property_id.in_(property_ids),
            MaintenanceRequest.maintenance_status.notin_([MaintenanceRequestStatus.COMPLETED, MaintenanceRequestStatus.CANCELLED]),
        )
        return self.db.execute(stmt).scalar_one()

    def get_detail(self, request_id: int) -> Optional[MaintenanceRequest]:
        stmt = (
            select(MaintenanceRequest)
            .options(
                selectinload(MaintenanceRequest.property_ref), selectinload(MaintenanceRequest.tenant),
                selectinload(MaintenanceRequest.assigned_contractor), selectinload(MaintenanceRequest.assigned_technician),
                selectinload(MaintenanceRequest.materials), selectinload(MaintenanceRequest.labor_entries).selectinload(MaintenanceLaborCost.technician),
                selectinload(MaintenanceRequest.photos),
            )
            .where(MaintenanceRequest.id == request_id, MaintenanceRequest.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def next_request_number(self) -> str:
        count = self.db.execute(select(func.count()).select_from(MaintenanceRequest)).scalar_one()
        return f"MNT-{count + 1:06d}"

    def list_requests(
        self, page: int, page_size: int, search: Optional[str], maintenance_status: Optional[str],
        priority: Optional[str], property_id: Optional[int], category: Optional[str], sort_dir: str,
        maintenance_contract_id: Optional[int] = None,
    ) -> tuple[list[MaintenanceRequest], int]:
        stmt = (
            select(MaintenanceRequest)
            .options(
                selectinload(MaintenanceRequest.property_ref), selectinload(MaintenanceRequest.tenant),
                selectinload(MaintenanceRequest.assigned_contractor), selectinload(MaintenanceRequest.assigned_technician),
                selectinload(MaintenanceRequest.materials), selectinload(MaintenanceRequest.labor_entries),
            )
            .where(MaintenanceRequest.deleted_at.is_(None))
        )
        if maintenance_status:
            stmt = stmt.where(MaintenanceRequest.maintenance_status == maintenance_status)
        if priority:
            stmt = stmt.where(MaintenanceRequest.priority == priority)
        if property_id:
            stmt = stmt.where(MaintenanceRequest.property_id == property_id)
        if category:
            stmt = stmt.where(MaintenanceRequest.category == category)
        if maintenance_contract_id:
            stmt = stmt.where(MaintenanceRequest.maintenance_contract_id == maintenance_contract_id)
        if search:
            like = f"%{search}%"
            stmt = (
                stmt.join(Property, Property.id == MaintenanceRequest.property_id, isouter=True)
                .join(Tenant, Tenant.id == MaintenanceRequest.tenant_id, isouter=True)
                .where(or_(
                    MaintenanceRequest.request_number.ilike(like),
                    MaintenanceRequest.title.ilike(like),
                    Property.title.ilike(like),
                    Tenant.first_name.ilike(like), Tenant.last_name.ilike(like), Tenant.company_name.ilike(like),
                ))
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        column = MaintenanceRequest.reported_date
        stmt = stmt.order_by(column.desc() if sort_dir == "desc" else column.asc(), MaintenanceRequest.id.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def dashboard_counts(self) -> dict:
        base = select(func.count()).select_from(MaintenanceRequest).where(MaintenanceRequest.deleted_at.is_(None))
        total = self.db.execute(base).scalar_one()

        def count_status(s):
            return self.db.execute(base.where(MaintenanceRequest.maintenance_status == s)).scalar_one()

        reported = count_status(MaintenanceRequestStatus.REPORTED)
        assigned = count_status(MaintenanceRequestStatus.ASSIGNED)
        in_progress = count_status(MaintenanceRequestStatus.IN_PROGRESS)
        on_hold = count_status(MaintenanceRequestStatus.ON_HOLD)
        completed = count_status(MaintenanceRequestStatus.COMPLETED)
        cancelled = count_status(MaintenanceRequestStatus.CANCELLED)

        open_stmt = select(MaintenanceRequest).where(
            MaintenanceRequest.deleted_at.is_(None),
            MaintenanceRequest.maintenance_status.notin_([MaintenanceRequestStatus.COMPLETED, MaintenanceRequestStatus.CANCELLED]),
        )
        open_requests = list(self.db.execute(open_stmt).scalars().all())
        overdue_count = sum(1 for r in open_requests if r.is_overdue)
        urgent_open_count = sum(1 for r in open_requests if r.priority == "urgent")

        this_month_stmt = (
            select(MaintenanceRequest)
            .options(selectinload(MaintenanceRequest.materials), selectinload(MaintenanceRequest.labor_entries))
            .where(
                MaintenanceRequest.deleted_at.is_(None),
                MaintenanceRequest.maintenance_status == MaintenanceRequestStatus.COMPLETED,
                func.extract("year", MaintenanceRequest.completed_date) == date.today().year,
                func.extract("month", MaintenanceRequest.completed_date) == date.today().month,
            )
        )
        completed_this_month = list(self.db.execute(this_month_stmt).scalars().all())
        total_cost_this_month = sum((r.total_actual_cost for r in completed_this_month), 0)

        return {
            "total_requests": total, "reported_count": reported, "assigned_count": assigned,
            "in_progress_count": in_progress, "on_hold_count": on_hold, "completed_count": completed,
            "cancelled_count": cancelled, "overdue_count": overdue_count, "urgent_open_count": urgent_open_count,
            "total_actual_cost_this_month": total_cost_this_month,
        }


class MaintenanceMaterialRepository(BaseRepository[MaintenanceMaterial]):
    def __init__(self, db: Session):
        super().__init__(MaintenanceMaterial, db)

    def list_for_request(self, request_id: int) -> list[MaintenanceMaterial]:
        stmt = select(MaintenanceMaterial).where(
            MaintenanceMaterial.request_id == request_id, MaintenanceMaterial.deleted_at.is_(None)
        ).order_by(MaintenanceMaterial.created_at.asc())
        return list(self.db.execute(stmt).scalars().all())


class MaintenanceLaborCostRepository(BaseRepository[MaintenanceLaborCost]):
    def __init__(self, db: Session):
        super().__init__(MaintenanceLaborCost, db)

    def list_for_request(self, request_id: int) -> list[MaintenanceLaborCost]:
        stmt = (
            select(MaintenanceLaborCost)
            .options(selectinload(MaintenanceLaborCost.technician))
            .where(MaintenanceLaborCost.request_id == request_id, MaintenanceLaborCost.deleted_at.is_(None))
            .order_by(MaintenanceLaborCost.work_date.asc())
        )
        return list(self.db.execute(stmt).scalars().all())


class MaintenancePhotoRepository(BaseRepository[MaintenancePhoto]):
    def __init__(self, db: Session):
        super().__init__(MaintenancePhoto, db)

    def list_for_request(self, request_id: int) -> list[MaintenancePhoto]:
        stmt = select(MaintenancePhoto).where(
            MaintenancePhoto.request_id == request_id, MaintenancePhoto.deleted_at.is_(None)
        ).order_by(MaintenancePhoto.created_at.asc())
        return list(self.db.execute(stmt).scalars().all())
