from math import ceil
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.common import PaginationParams, PaginatedResponse, MessageResponse
from app.schemas.organization import (
    CountryCreate, CountryUpdate, CountryOut, CityCreate, CityUpdate, CityOut,
    CurrencyCreate, CurrencyUpdate, CurrencyOut, BranchCreate, BranchUpdate, BranchOut,
    CompanyProfileUpdate, CompanyProfileOut, SystemSettingUpdate, SystemSettingOut,
)
from app.services.organization_service import (
    CountryService, CityService, CurrencyService, BranchService, CompanyProfileService, SystemSettingService,
)
from app.models.user import User

router = APIRouter(tags=["Organization Setup"])


def _paginated(items, total, params: PaginationParams):
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


# ---------------- Company Profile (singleton) ----------------
@router.get("/company-profile", response_model=CompanyProfileOut)
def get_company_profile(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("company.view"))):
    return CompanyProfileService(db).get()


@router.put("/company-profile", response_model=CompanyProfileOut)
def update_company_profile(payload: CompanyProfileUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("company.edit"))):
    return CompanyProfileService(db).upsert(payload.model_dump(exclude_unset=True), actor_id=current_user.id)


# ---------------- Branches ----------------
@router.get("/branches", response_model=PaginatedResponse[BranchOut])
def list_branches(params: PaginationParams = Depends(get_pagination_params), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("branches.view"))):
    items, total = BranchService(db).list(params)
    return _paginated(items, total, params)


@router.post("/branches", response_model=BranchOut, status_code=201)
def create_branch(payload: BranchCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("branches.create"))):
    return BranchService(db).create(payload.model_dump(), actor_id=current_user.id)


@router.get("/branches/{branch_id}", response_model=BranchOut)
def get_branch(branch_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("branches.view"))):
    return BranchService(db).get(branch_id)


@router.put("/branches/{branch_id}", response_model=BranchOut)
def update_branch(branch_id: int, payload: BranchUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("branches.edit"))):
    return BranchService(db).update(branch_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/branches/{branch_id}", response_model=MessageResponse)
def delete_branch(branch_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("branches.delete"))):
    BranchService(db).delete(branch_id, actor_id=current_user.id)
    return {"message": "Branch deleted successfully"}


# ---------------- Countries ----------------
@router.get("/countries", response_model=PaginatedResponse[CountryOut])
def list_countries(params: PaginationParams = Depends(get_pagination_params), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("countries.view"))):
    items, total = CountryService(db).list(params)
    return _paginated(items, total, params)


@router.post("/countries", response_model=CountryOut, status_code=201)
def create_country(payload: CountryCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("countries.create"))):
    return CountryService(db).create(payload.model_dump(), actor_id=current_user.id)


@router.put("/countries/{country_id}", response_model=CountryOut)
def update_country(country_id: int, payload: CountryUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("countries.edit"))):
    return CountryService(db).update(country_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/countries/{country_id}", response_model=MessageResponse)
def delete_country(country_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("countries.delete"))):
    CountryService(db).delete(country_id, actor_id=current_user.id)
    return {"message": "Country deleted successfully"}


# ---------------- Cities ----------------
@router.get("/cities", response_model=PaginatedResponse[CityOut])
def list_cities(
    params: PaginationParams = Depends(get_pagination_params),
    country_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("cities.view")),
):
    filters = {"country_id": country_id} if country_id else None
    items, total = CityService(db).list(params, filters=filters)
    return _paginated(items, total, params)


@router.post("/cities", response_model=CityOut, status_code=201)
def create_city(payload: CityCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("cities.create"))):
    return CityService(db).create(payload.model_dump(), actor_id=current_user.id)


@router.put("/cities/{city_id}", response_model=CityOut)
def update_city(city_id: int, payload: CityUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("cities.edit"))):
    return CityService(db).update(city_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/cities/{city_id}", response_model=MessageResponse)
def delete_city(city_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("cities.delete"))):
    CityService(db).delete(city_id, actor_id=current_user.id)
    return {"message": "City deleted successfully"}


# ---------------- Currencies ----------------
@router.get("/currencies", response_model=PaginatedResponse[CurrencyOut])
def list_currencies(params: PaginationParams = Depends(get_pagination_params), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("currencies.view"))):
    items, total = CurrencyService(db).list(params)
    return _paginated(items, total, params)


@router.post("/currencies", response_model=CurrencyOut, status_code=201)
def create_currency(payload: CurrencyCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("currencies.create"))):
    return CurrencyService(db).create(payload.model_dump(), actor_id=current_user.id)


@router.put("/currencies/{currency_id}", response_model=CurrencyOut)
def update_currency(currency_id: int, payload: CurrencyUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("currencies.edit"))):
    return CurrencyService(db).update(currency_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/currencies/{currency_id}", response_model=MessageResponse)
def delete_currency(currency_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("currencies.delete"))):
    CurrencyService(db).delete(currency_id, actor_id=current_user.id)
    return {"message": "Currency deleted successfully"}


# ---------------- System Settings ----------------
@router.get("/settings", response_model=list[SystemSettingOut])
def list_settings(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("settings.view")),
):
    return SystemSettingService(db).list(category)


@router.put("/settings/{key}", response_model=SystemSettingOut)
def update_setting(key: str, payload: SystemSettingUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("settings.edit"))):
    return SystemSettingService(db).update_by_key(key, payload.value, actor_id=current_user.id)
