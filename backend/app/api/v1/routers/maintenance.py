from math import ceil
from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.common import PaginationParams, PaginatedResponse, MessageResponse
from app.schemas.maintenance import (
    ContractorCreate, ContractorUpdate, ContractorOut,
    TechnicianCreate, TechnicianUpdate, TechnicianOut,
    MaintenanceRequestCreate, MaintenanceRequestUpdate, MaintenanceRequestListItemOut, MaintenanceRequestDetailOut,
    AssignRequest, HoldRequest, CancelRequest, CompleteRequest,
    MaterialCreate, MaterialOut, LaborCostCreate, LaborCostOut, PhotoOut,
    MaintenanceDashboardOut,
)
from app.schemas.maintenance_contract import (
    MaintenanceContractCreate, MaintenanceContractUpdate, MaintenanceContractListItemOut, MaintenanceContractDetailOut,
    TerminateMaintenanceContractRequest, RenewMaintenanceContractRequest, LogServiceVisitRequest,
    MaintenanceContractDashboardOut,
)
from app.services.maintenance_service import ContractorService, TechnicianService, MaintenanceService
from app.services.maintenance_contract_service import MaintenanceContractService
from app.models.user import User

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])


def _paginated(items, total, params: PaginationParams):
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


# ---------------- Dashboard ----------------
@router.get("/dashboard/summary", response_model=MaintenanceDashboardOut)
def maintenance_dashboard(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.view"))):
    return MaintenanceService(db).dashboard()


# ---------------- Contractors ----------------
@router.get("/contractors", response_model=PaginatedResponse[ContractorOut])
def list_contractors(params: PaginationParams = Depends(get_pagination_params), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.view"))):
    items, total = ContractorService(db).list_contractors(params)
    return _paginated(items, total, params)


@router.post("/contractors", response_model=ContractorOut, status_code=201)
def create_contractor(payload: ContractorCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.create"))):
    return ContractorService(db).create_contractor(payload.model_dump(), actor_id=current_user.id)


@router.get("/contractors/{contractor_id}", response_model=ContractorOut)
def get_contractor(contractor_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.view"))):
    return ContractorService(db).get_contractor(contractor_id)


@router.put("/contractors/{contractor_id}", response_model=ContractorOut)
def update_contractor(contractor_id: int, payload: ContractorUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return ContractorService(db).update_contractor(contractor_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/contractors/{contractor_id}", response_model=MessageResponse)
def delete_contractor(contractor_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.delete"))):
    ContractorService(db).delete_contractor(contractor_id, actor_id=current_user.id)
    return {"message": "Contractor deleted successfully"}


# ---------------- Technicians ----------------
@router.get("/technicians", response_model=PaginatedResponse[TechnicianOut])
def list_technicians(params: PaginationParams = Depends(get_pagination_params), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.view"))):
    items, total = TechnicianService(db).list_technicians(params)
    return _paginated(items, total, params)


@router.post("/technicians", response_model=TechnicianOut, status_code=201)
def create_technician(payload: TechnicianCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.create"))):
    return TechnicianService(db).create_technician(payload.model_dump(), actor_id=current_user.id)


@router.get("/technicians/{technician_id}", response_model=TechnicianOut)
def get_technician(technician_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.view"))):
    return TechnicianService(db).get_technician(technician_id)


@router.put("/technicians/{technician_id}", response_model=TechnicianOut)
def update_technician(technician_id: int, payload: TechnicianUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return TechnicianService(db).update_technician(technician_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/technicians/{technician_id}", response_model=MessageResponse)
def delete_technician(technician_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.delete"))):
    TechnicianService(db).delete_technician(technician_id, actor_id=current_user.id)
    return {"message": "Technician deleted successfully"}


# ---------------- Maintenance Requests ----------------
@router.get("/requests", response_model=PaginatedResponse[MaintenanceRequestListItemOut])
def list_requests(
    params: PaginationParams = Depends(get_pagination_params),
    maintenance_status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    property_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    maintenance_contract_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("maintenance.view")),
):
    items, total = MaintenanceService(db).list_requests(params, maintenance_status, priority, property_id, category, maintenance_contract_id)
    return _paginated(items, total, params)


@router.post("/requests", response_model=MaintenanceRequestDetailOut, status_code=201)
def create_request(payload: MaintenanceRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.create"))):
    return MaintenanceService(db).create_request(payload.model_dump(), actor_id=current_user.id)


@router.get("/requests/{request_id}", response_model=MaintenanceRequestDetailOut)
def get_request(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.view"))):
    return MaintenanceService(db).get_request(request_id)


@router.put("/requests/{request_id}", response_model=MaintenanceRequestDetailOut)
def update_request(request_id: int, payload: MaintenanceRequestUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return MaintenanceService(db).update_request(request_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/requests/{request_id}", response_model=MessageResponse)
def delete_request(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.delete"))):
    MaintenanceService(db).delete_request(request_id, actor_id=current_user.id)
    return {"message": "Maintenance request deleted successfully"}


# ---------------- Status transitions ----------------
@router.post("/requests/{request_id}/assign", response_model=MaintenanceRequestDetailOut)
def assign_request(request_id: int, payload: AssignRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return MaintenanceService(db).assign_request(request_id, payload.assigned_contractor_id, payload.assigned_technician_id, payload.scheduled_date, actor_id=current_user.id)


@router.post("/requests/{request_id}/start", response_model=MaintenanceRequestDetailOut)
def start_request(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return MaintenanceService(db).start_request(request_id, actor_id=current_user.id)


@router.post("/requests/{request_id}/hold", response_model=MaintenanceRequestDetailOut)
def hold_request(request_id: int, payload: HoldRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return MaintenanceService(db).hold_request(request_id, payload.on_hold_reason, actor_id=current_user.id)


@router.post("/requests/{request_id}/resume", response_model=MaintenanceRequestDetailOut)
def resume_request(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return MaintenanceService(db).resume_request(request_id, actor_id=current_user.id)


@router.post("/requests/{request_id}/complete", response_model=MaintenanceRequestDetailOut)
def complete_request(request_id: int, payload: CompleteRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return MaintenanceService(db).complete_request(request_id, payload.completed_date, actor_id=current_user.id)


@router.post("/requests/{request_id}/cancel", response_model=MaintenanceRequestDetailOut)
def cancel_request(request_id: int, payload: CancelRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return MaintenanceService(db).cancel_request(request_id, payload.cancellation_reason, actor_id=current_user.id)


# ---------------- Materials ----------------
@router.post("/requests/{request_id}/materials", response_model=MaterialOut, status_code=201)
def add_material(request_id: int, payload: MaterialCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return MaintenanceService(db).add_material(request_id, payload.model_dump(), actor_id=current_user.id)


@router.delete("/requests/{request_id}/materials/{material_id}", response_model=MessageResponse)
def delete_material(request_id: int, material_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    MaintenanceService(db).delete_material(request_id, material_id, actor_id=current_user.id)
    return {"message": "Material removed successfully"}


# ---------------- Labor Costs ----------------
@router.post("/requests/{request_id}/labor", response_model=LaborCostOut, status_code=201)
def add_labor_cost(request_id: int, payload: LaborCostCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return MaintenanceService(db).add_labor_cost(request_id, payload.model_dump(), actor_id=current_user.id)


@router.delete("/requests/{request_id}/labor/{labor_id}", response_model=MessageResponse)
def delete_labor_cost(request_id: int, labor_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    MaintenanceService(db).delete_labor_cost(request_id, labor_id, actor_id=current_user.id)
    return {"message": "Labor cost entry removed successfully"}


# ---------------- Photos (Before / After) ----------------
@router.post("/requests/{request_id}/photos", response_model=PhotoOut, status_code=201)
def upload_photo(
    request_id: int,
    photo_type: str = Form(...),
    caption: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("maintenance.edit")),
):
    return MaintenanceService(db).upload_photo(request_id, file, photo_type, caption, actor_id=current_user.id)


@router.delete("/requests/{request_id}/photos/{photo_id}", response_model=MessageResponse)
def delete_photo(request_id: int, photo_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    MaintenanceService(db).delete_photo(request_id, photo_id, actor_id=current_user.id)
    return {"message": "Photo removed successfully"}


# ---------------- Maintenance Contracts (recurring/annual service contracts:
# elevators, HVAC/AC, generators, fire safety, etc.) ----------------
# Reuses the existing maintenance.* permissions (view/create/edit/delete) —
# no new permission module, consistent with every prior extension in this
# codebase. Static-path routes are declared before "/{contract_id}" so
# FastAPI resolves them first, exactly like the leases router does.
@router.get("/contracts/dashboard/summary", response_model=MaintenanceContractDashboardOut)
def maintenance_contracts_dashboard(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.view"))):
    return MaintenanceContractService(db).dashboard()


@router.post("/contracts/maintenance/run")
def run_maintenance_contracts_sweep(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    """
    On-demand housekeeping: auto-expires overdue contracts, and sends
    renewal reminder + service-due notifications. See
    docs/maintenance-contracts-module.md for wiring this to a real
    scheduler (same honest limitation as the Phase 3 lease sweep).
    """
    return MaintenanceContractService(db).run_maintenance_sweep(actor_id=current_user.id)


@router.get("/contracts", response_model=PaginatedResponse[MaintenanceContractListItemOut])
def list_maintenance_contracts(
    params: PaginationParams = Depends(get_pagination_params),
    contract_status: Optional[str] = Query(None),
    property_id: Optional[int] = Query(None),
    contractor_id: Optional[int] = Query(None),
    service_type: Optional[str] = Query(None),
    expiring_soon: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("maintenance.view")),
):
    items, total = MaintenanceContractService(db).list_contracts(params, contract_status, property_id, contractor_id, service_type, expiring_soon)
    return _paginated(items, total, params)


@router.post("/contracts", response_model=MaintenanceContractDetailOut, status_code=201)
def create_maintenance_contract(payload: MaintenanceContractCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.create"))):
    return MaintenanceContractService(db).create_contract(payload.model_dump(), actor_id=current_user.id)


@router.get("/contracts/{contract_id}", response_model=MaintenanceContractDetailOut)
def get_maintenance_contract(contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.view"))):
    return MaintenanceContractService(db).get_contract(contract_id)


@router.put("/contracts/{contract_id}", response_model=MaintenanceContractDetailOut)
def update_maintenance_contract(contract_id: int, payload: MaintenanceContractUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return MaintenanceContractService(db).update_contract(contract_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/contracts/{contract_id}", response_model=MessageResponse)
def delete_maintenance_contract(contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.delete"))):
    MaintenanceContractService(db).delete_contract(contract_id, actor_id=current_user.id)
    return {"message": "Maintenance contract deleted successfully"}


@router.post("/contracts/{contract_id}/activate", response_model=MaintenanceContractDetailOut)
def activate_maintenance_contract(contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return MaintenanceContractService(db).activate_contract(contract_id, actor_id=current_user.id)


@router.post("/contracts/{contract_id}/terminate", response_model=MaintenanceContractDetailOut)
def terminate_maintenance_contract(contract_id: int, payload: TerminateMaintenanceContractRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return MaintenanceContractService(db).terminate_contract(contract_id, payload.terminated_date, payload.termination_reason, actor_id=current_user.id)


@router.post("/contracts/{contract_id}/renew", response_model=MaintenanceContractDetailOut)
def renew_maintenance_contract(contract_id: int, payload: RenewMaintenanceContractRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return MaintenanceContractService(db).renew_contract(
        contract_id, payload.new_end_date, payload.new_start_date, payload.annual_cost, payload.notes, actor_id=current_user.id,
    )


@router.post("/contracts/{contract_id}/log-visit", response_model=MaintenanceContractDetailOut)
def log_maintenance_contract_visit(contract_id: int, payload: LogServiceVisitRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("maintenance.edit"))):
    return MaintenanceContractService(db).log_service_visit(contract_id, payload.visit_date, payload.notes, actor_id=current_user.id)
