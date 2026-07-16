from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.organization_repository import (
    CountryRepository, CityRepository, CurrencyRepository, BranchRepository,
    CompanyProfileRepository, SystemSettingRepository,
)
from app.schemas.common import PaginationParams
from app.services.audit_service import AuditService


class LookupServiceBase:
    """Shared list/create/update/delete flow for simple lookup entities."""
    entity_label = "record"
    search_fields: list[str] = ["name"]

    def __init__(self, db: Session, repo):
        self.db = db
        self.repo = repo
        self.audit = AuditService(db)

    def list(self, params: PaginationParams, filters: Optional[dict] = None):
        return self.repo.list(
            page=params.page, page_size=params.page_size, search=params.search,
            search_fields=self.search_fields, sort_by=params.sort_by, sort_dir=params.sort_dir,
            filters=filters,
        )

    def get(self, id: int):
        obj = self.repo.get(id)
        if not obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{self.entity_label} not found")
        return obj

    def create(self, data: dict, actor_id: Optional[int]):
        obj = self.repo.create(data, actor_id=actor_id)
        self.audit.log_activity(self.entity_label.lower(), obj.id, "created", f"{self.entity_label} created", actor_id)
        self.db.commit()
        return obj

    def update(self, id: int, data: dict, actor_id: Optional[int]):
        obj = self.get(id)
        self.repo.update(obj, data, actor_id=actor_id)
        self.audit.log_activity(self.entity_label.lower(), obj.id, "updated", f"{self.entity_label} updated", actor_id)
        self.db.commit()
        return obj

    def delete(self, id: int, actor_id: Optional[int]):
        obj = self.get(id)
        self.repo.soft_delete(obj, actor_id=actor_id)
        self.audit.log_activity(self.entity_label.lower(), obj.id, "deleted", f"{self.entity_label} deleted", actor_id)
        self.db.commit()


class CountryService(LookupServiceBase):
    entity_label = "Country"
    search_fields = ["name", "iso_code2", "iso_code3"]

    def __init__(self, db: Session):
        super().__init__(db, CountryRepository(db))


class CityService(LookupServiceBase):
    entity_label = "City"
    search_fields = ["name"]

    def __init__(self, db: Session):
        super().__init__(db, CityRepository(db))


class CurrencyService(LookupServiceBase):
    entity_label = "Currency"
    search_fields = ["name", "code"]

    def __init__(self, db: Session):
        super().__init__(db, CurrencyRepository(db))


class BranchService(LookupServiceBase):
    entity_label = "Branch"
    search_fields = ["name", "code"]

    def __init__(self, db: Session):
        super().__init__(db, BranchRepository(db))

    def create(self, data: dict, actor_id: Optional[int]):
        if self.repo.get_by_code(data["code"]):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A branch with this code already exists")
        return super().create(data, actor_id)


class CompanyProfileService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CompanyProfileRepository(db)
        self.audit = AuditService(db)

    def get(self):
        profile = self.repo.get_active()
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company profile has not been configured yet")
        return profile

    def get_or_none(self):
        return self.repo.get_active()

    def upsert(self, data: dict, actor_id: Optional[int]):
        profile = self.repo.get_active()
        if profile:
            self.repo.update(profile, data, actor_id=actor_id)
        else:
            profile = self.repo.create(data, actor_id=actor_id)
        self.audit.log_activity("company_profile", profile.id, "updated", "Company profile updated", actor_id)
        self.db.commit()
        return profile


class SystemSettingService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SystemSettingRepository(db)
        self.audit = AuditService(db)

    def list(self, category: Optional[str] = None):
        filters = {"category": category} if category else None
        items, total = self.repo.list(page=1, page_size=500, filters=filters, sort_by="key")
        return items

    def get_by_key(self, key: str):
        setting = self.repo.get_by_key(key)
        if not setting:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
        return setting

    def update_by_key(self, key: str, value: str, actor_id: Optional[int]):
        setting = self.get_by_key(key)
        if not setting.is_editable:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This setting is not editable")
        setting.value = value
        self.audit.log_activity("system_setting", setting.id, "updated", f"Setting '{key}' updated", actor_id)
        self.db.commit()
        return setting
