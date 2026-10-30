from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.organization import Country, City, Currency, CompanyProfile, Branch, SystemSetting
from app.repositories.base import BaseRepository


class CountryRepository(BaseRepository[Country]):
    def __init__(self, db: Session):
        super().__init__(Country, db)


class CityRepository(BaseRepository[City]):
    def __init__(self, db: Session):
        super().__init__(City, db)


class CurrencyRepository(BaseRepository[Currency]):
    def __init__(self, db: Session):
        super().__init__(Currency, db)


class BranchRepository(BaseRepository[Branch]):
    def __init__(self, db: Session):
        super().__init__(Branch, db)

    def get_by_code(self, code: str) -> Optional[Branch]:
        stmt = select(Branch).where(Branch.code == code, Branch.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()


class CompanyProfileRepository(BaseRepository[CompanyProfile]):
    def __init__(self, db: Session):
        super().__init__(CompanyProfile, db)

    def get_active(self) -> Optional[CompanyProfile]:
        stmt = select(CompanyProfile).where(CompanyProfile.deleted_at.is_(None)).order_by(CompanyProfile.id.asc())
        return self.db.execute(stmt).scalars().first()


class SystemSettingRepository(BaseRepository[SystemSetting]):
    def __init__(self, db: Session):
        super().__init__(SystemSetting, db)

    def get_by_key(self, key: str) -> Optional[SystemSetting]:
        stmt = select(SystemSetting).where(SystemSetting.key == key, SystemSetting.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()
