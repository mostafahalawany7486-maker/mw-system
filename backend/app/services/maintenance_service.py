"""
Maintenance business logic. MaintenanceRequest follows the same
status-machine pattern established in Phases 3/7 (explicit action
endpoints per transition rather than a generic "set status" call, for
better audit logging and UX). Materials and Labor Cost are per-request
line items; "actual cost" is always their live sum, never a manually
entered total that can drift.
"""
from datetime import date
from typing import Optional
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.repositories.maintenance_repository import (
    ContractorRepository, TechnicianRepository, MaintenanceRequestRepository,
    MaintenanceMaterialRepository, MaintenanceLaborCostRepository, MaintenancePhotoRepository,
)
from app.repositories.maintenance_contract_repository import MaintenanceContractRepository
from app.repositories.property_repository import PropertyRepository
from app.repositories.tenant_repository import TenantRepository
from app.models.maintenance import MaintenanceRequestStatus, PhotoType
from app.schemas.common import PaginationParams
from app.services.audit_service import AuditService
from app.services.file_storage_service import FileUploadService

ENTITY_TYPE = "maintenance_request"

ALLOWED_TRANSITIONS = {
    MaintenanceRequestStatus.REPORTED: {MaintenanceRequestStatus.ASSIGNED, MaintenanceRequestStatus.CANCELLED},
    MaintenanceRequestStatus.ASSIGNED: {MaintenanceRequestStatus.IN_PROGRESS, MaintenanceRequestStatus.ON_HOLD, MaintenanceRequestStatus.CANCELLED},
    MaintenanceRequestStatus.IN_PROGRESS: {MaintenanceRequestStatus.ON_HOLD, MaintenanceRequestStatus.COMPLETED, MaintenanceRequestStatus.CANCELLED},
    MaintenanceRequestStatus.ON_HOLD: {MaintenanceRequestStatus.IN_PROGRESS, MaintenanceRequestStatus.CANCELLED},
    MaintenanceRequestStatus.COMPLETED: set(),
    MaintenanceRequestStatus.CANCELLED: set(),
}


class ContractorService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ContractorRepository(db)
        self.audit = AuditService(db)

    def _attach_count(self, contractor):
        contractor.technician_count = self.repo.technician_count(contractor.id)
        return contractor

    def list_contractors(self, params: PaginationParams):
        items, total = self.repo.list(page=params.page, page_size=params.page_size, search=params.search, search_fields=["company_name", "contractor_code", "specialty"])
        items = [self._attach_count(c) for c in items]
        return items, total

    def get_contractor(self, contractor_id: int):
        contractor = self.repo.get(contractor_id)
        if not contractor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found")
        return self._attach_count(contractor)

    def create_contractor(self, data: dict, actor_id: Optional[int]):
        payload = dict(data)
        payload["contractor_code"] = self.repo.next_contractor_code()
        contractor = self.repo.create(payload, actor_id=actor_id)
        self.audit.log_activity("contractor", contractor.id, "created", f"Contractor {contractor.contractor_code} ({contractor.company_name}) created", actor_id)
        self.db.commit()
        return self._attach_count(contractor)

    def update_contractor(self, contractor_id: int, data: dict, actor_id: Optional[int]):
        contractor = self.repo.get(contractor_id)
        if not contractor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found")
        self.repo.update(contractor, data, actor_id=actor_id)
        self.db.commit()
        return self._attach_count(contractor)

    def delete_contractor(self, contractor_id: int, actor_id: Optional[int]):
        contractor = self.repo.get(contractor_id)
        if not contractor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor not found")
        if self.repo.technician_count(contractor_id) > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete a contractor with technicians still assigned to them. Reassign or remove those technicians first.")
        self.repo.soft_delete(contractor, actor_id=actor_id)
        self.db.commit()


class TechnicianService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TechnicianRepository(db)
        self.contractor_repo = ContractorRepository(db)
        self.audit = AuditService(db)

    def _attach_extras(self, technician):
        technician.full_name = f"{technician.first_name} {technician.last_name}"
        technician.contractor_name = technician.contractor.company_name if technician.contractor else None
        technician.is_in_house = technician.contractor_id is None
        return technician

    def list_technicians(self, params: PaginationParams):
        items, total = self.repo.list_with_contractor(page=params.page, page_size=params.page_size, search=params.search)
        items = [self._attach_extras(t) for t in items]
        return items, total

    def get_technician(self, technician_id: int):
        technician = self.repo.get_detail(technician_id)
        if not technician:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found")
        return self._attach_extras(technician)

    def create_technician(self, data: dict, actor_id: Optional[int]):
        if data.get("contractor_id") and not self.contractor_repo.get(data["contractor_id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid contractor_id")
        payload = dict(data)
        payload["technician_code"] = self.repo.next_technician_code()
        technician = self.repo.create(payload, actor_id=actor_id)
        self.audit.log_activity("technician", technician.id, "created", f"Technician {technician.technician_code} ({technician.first_name} {technician.last_name}) created", actor_id)
        self.db.commit()
        return self._attach_extras(self.repo.get_detail(technician.id))

    def update_technician(self, technician_id: int, data: dict, actor_id: Optional[int]):
        technician = self.repo.get(technician_id)
        if not technician:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found")
        if data.get("contractor_id") and not self.contractor_repo.get(data["contractor_id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid contractor_id")
        self.repo.update(technician, data, actor_id=actor_id)
        self.db.commit()
        return self._attach_extras(self.repo.get_detail(technician.id))

    def delete_technician(self, technician_id: int, actor_id: Optional[int]):
        technician = self.repo.get(technician_id)
        if not technician:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found")
        self.repo.soft_delete(technician, actor_id=actor_id)
        self.db.commit()


class MaintenanceService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = MaintenanceRequestRepository(db)
        self.material_repo = MaintenanceMaterialRepository(db)
        self.labor_repo = MaintenanceLaborCostRepository(db)
        self.photo_repo = MaintenancePhotoRepository(db)
        self.property_repo = PropertyRepository(db)
        self.tenant_repo = TenantRepository(db)
        self.contractor_repo = ContractorRepository(db)
        self.technician_repo = TechnicianRepository(db)
        self.contract_repo = MaintenanceContractRepository(db)
        self.audit = AuditService(db)
        self.uploader = FileUploadService()

    # ---------------- CRUD ----------------
    def list_requests(self, params: PaginationParams, maintenance_status, priority, property_id, category, maintenance_contract_id=None):
        items, total = self.repo.list_requests(
            page=params.page, page_size=params.page_size, search=params.search, maintenance_status=maintenance_status,
            priority=priority, property_id=property_id, category=category, sort_dir=params.sort_dir or "desc",
            maintenance_contract_id=maintenance_contract_id,
        )
        return items, total

    def get_request(self, request_id: int):
        req = self.repo.get_detail(request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")
        return req

    def create_request(self, data: dict, actor_id: Optional[int]):
        if not self.property_repo.get(data["property_id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid property_id")
        if data.get("tenant_id") and not self.tenant_repo.get(data["tenant_id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant_id")
        if data.get("maintenance_contract_id") and not self.contract_repo.get(data["maintenance_contract_id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid maintenance_contract_id")

        payload = dict(data)
        payload["request_number"] = self.repo.next_request_number()
        payload["maintenance_status"] = MaintenanceRequestStatus.REPORTED
        req = self.repo.create(payload, actor_id=actor_id)

        self.audit.log_activity(ENTITY_TYPE, req.id, "created", f"Maintenance request {req.request_number} reported: {req.title}", actor_id)
        self.db.commit()
        return self.get_request(req.id)

    def update_request(self, request_id: int, data: dict, actor_id: Optional[int]):
        req = self.repo.get(request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")
        if req.maintenance_status in (MaintenanceRequestStatus.COMPLETED, MaintenanceRequestStatus.CANCELLED):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot edit a {req.maintenance_status} request")
        if data.get("maintenance_contract_id") and not self.contract_repo.get(data["maintenance_contract_id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid maintenance_contract_id")
        self.repo.update(req, data, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, req.id, "updated", f"Maintenance request {req.request_number} updated", actor_id)
        self.db.commit()
        return self.get_request(req.id)

    def delete_request(self, request_id: int, actor_id: Optional[int]):
        req = self.repo.get(request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")
        self.repo.soft_delete(req, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, req.id, "deleted", f"Maintenance request {req.request_number} deleted", actor_id)
        self.db.commit()

    # ---------------- Status transitions ----------------
    def _ensure_transition_allowed(self, current_status: str, new_status: str):
        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot move from '{current_status}' to '{new_status}'. Allowed next steps: {sorted(allowed) or 'none (terminal state)'}",
            )

    def assign_request(self, request_id: int, contractor_id: Optional[int], technician_id: Optional[int], scheduled_date: Optional[date], actor_id: Optional[int]):
        req = self.repo.get(request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")
        if contractor_id and not self.contractor_repo.get(contractor_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid contractor_id")
        if technician_id and not self.technician_repo.get(technician_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid technician_id")

        if req.maintenance_status == MaintenanceRequestStatus.REPORTED:
            self._ensure_transition_allowed(req.maintenance_status, MaintenanceRequestStatus.ASSIGNED)
            req.maintenance_status = MaintenanceRequestStatus.ASSIGNED
        elif req.maintenance_status not in (MaintenanceRequestStatus.ASSIGNED, MaintenanceRequestStatus.IN_PROGRESS, MaintenanceRequestStatus.ON_HOLD):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot (re)assign a request that is '{req.maintenance_status}'")

        if contractor_id:
            req.assigned_contractor_id = contractor_id
        if technician_id:
            req.assigned_technician_id = technician_id
        if scheduled_date:
            req.scheduled_date = scheduled_date

        self.audit.log_activity(ENTITY_TYPE, req.id, "assigned", f"Maintenance request {req.request_number} assigned", actor_id)
        self.db.commit()
        return self.get_request(req.id)

    def start_request(self, request_id: int, actor_id: Optional[int]):
        req = self.repo.get(request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")
        self._ensure_transition_allowed(req.maintenance_status, MaintenanceRequestStatus.IN_PROGRESS)
        req.maintenance_status = MaintenanceRequestStatus.IN_PROGRESS
        self.audit.log_activity(ENTITY_TYPE, req.id, "started", f"Work started on {req.request_number}", actor_id)
        self.db.commit()
        return self.get_request(req.id)

    def hold_request(self, request_id: int, reason: str, actor_id: Optional[int]):
        req = self.repo.get(request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")
        self._ensure_transition_allowed(req.maintenance_status, MaintenanceRequestStatus.ON_HOLD)
        req.maintenance_status = MaintenanceRequestStatus.ON_HOLD
        req.on_hold_reason = reason
        self.audit.log_activity(ENTITY_TYPE, req.id, "on_hold", f"Maintenance request {req.request_number} put on hold: {reason}", actor_id)
        self.db.commit()
        return self.get_request(req.id)

    def resume_request(self, request_id: int, actor_id: Optional[int]):
        req = self.repo.get(request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")
        self._ensure_transition_allowed(req.maintenance_status, MaintenanceRequestStatus.IN_PROGRESS)
        req.maintenance_status = MaintenanceRequestStatus.IN_PROGRESS
        self.audit.log_activity(ENTITY_TYPE, req.id, "resumed", f"Maintenance request {req.request_number} resumed", actor_id)
        self.db.commit()
        return self.get_request(req.id)

    def complete_request(self, request_id: int, completed_date: date, actor_id: Optional[int]):
        req = self.repo.get(request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")
        self._ensure_transition_allowed(req.maintenance_status, MaintenanceRequestStatus.COMPLETED)
        req.maintenance_status = MaintenanceRequestStatus.COMPLETED
        req.completed_date = completed_date
        self.audit.log_activity(ENTITY_TYPE, req.id, "completed", f"Maintenance request {req.request_number} completed", actor_id)
        self.db.commit()
        return self.get_request(req.id)

    def cancel_request(self, request_id: int, reason: str, actor_id: Optional[int]):
        req = self.repo.get(request_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance request not found")
        self._ensure_transition_allowed(req.maintenance_status, MaintenanceRequestStatus.CANCELLED)
        req.maintenance_status = MaintenanceRequestStatus.CANCELLED
        req.cancellation_reason = reason
        self.audit.log_activity(ENTITY_TYPE, req.id, "cancelled", f"Maintenance request {req.request_number} cancelled: {reason}", actor_id)
        self.db.commit()
        return self.get_request(req.id)

    # ---------------- Materials ----------------
    def add_material(self, request_id: int, data: dict, actor_id: Optional[int]):
        self.get_request(request_id)
        data["request_id"] = request_id
        material = self.material_repo.create(data, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, request_id, "material_added", f"Material '{material.name}' added ({material.quantity} x {material.unit_cost})", actor_id)
        self.db.commit()
        return material

    def delete_material(self, request_id: int, material_id: int, actor_id: Optional[int]):
        material = self.material_repo.get(material_id)
        if not material or material.request_id != request_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
        self.material_repo.soft_delete(material, actor_id=actor_id)
        self.db.commit()

    # ---------------- Labor Costs ----------------
    def add_labor_cost(self, request_id: int, data: dict, actor_id: Optional[int]):
        self.get_request(request_id)
        if data.get("technician_id") and not self.technician_repo.get(data["technician_id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid technician_id")
        if data.get("contractor_id") and not self.contractor_repo.get(data["contractor_id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid contractor_id")
        data["request_id"] = request_id
        labor = self.labor_repo.create(data, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, request_id, "labor_cost_added", f"Labor cost added ({labor.hours}h @ {labor.hourly_rate})", actor_id)
        self.db.commit()
        return labor

    def delete_labor_cost(self, request_id: int, labor_id: int, actor_id: Optional[int]):
        labor = self.labor_repo.get(labor_id)
        if not labor or labor.request_id != request_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Labor cost entry not found")
        self.labor_repo.soft_delete(labor, actor_id=actor_id)
        self.db.commit()

    # ---------------- Photos ----------------
    def upload_photo(self, request_id: int, file: UploadFile, photo_type: str, caption: Optional[str], actor_id: Optional[int]):
        self.get_request(request_id)
        if photo_type not in (PhotoType.BEFORE, PhotoType.AFTER):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="photo_type must be 'before' or 'after'")
        meta = self.uploader.upload(file, ENTITY_TYPE, request_id)
        meta["request_id"] = request_id
        meta["photo_type"] = photo_type
        meta["caption"] = caption
        photo = self.photo_repo.create(meta, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, request_id, "photo_added", f"{photo_type.title()} photo uploaded: {photo.file_name}", actor_id)
        self.db.commit()
        return photo

    def delete_photo(self, request_id: int, photo_id: int, actor_id: Optional[int]):
        photo = self.photo_repo.get(photo_id)
        if not photo or photo.request_id != request_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
        self.photo_repo.soft_delete(photo, actor_id=actor_id)
        self.db.commit()

    # ---------------- Dashboard ----------------
    def dashboard(self) -> dict:
        return self.repo.dashboard_counts()
