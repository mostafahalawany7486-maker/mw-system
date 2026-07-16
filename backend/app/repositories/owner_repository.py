from typing import Optional
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload
from app.models.owner import Owner, OwnerAddress, OwnerBankAccount, OwnerContact, OwnerDocument
from app.repositories.base import BaseRepository


class OwnerRepository(BaseRepository[Owner]):
    def __init__(self, db: Session):
        super().__init__(Owner, db)

    def get_detail(self, owner_id: int) -> Optional[Owner]:
        stmt = (
            select(Owner)
            .options(
                selectinload(Owner.addresses),
                selectinload(Owner.bank_accounts),
                selectinload(Owner.contacts),
                selectinload(Owner.documents),
            )
            .where(Owner.id == owner_id, Owner.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_code(self, owner_code: str) -> Optional[Owner]:
        stmt = select(Owner).where(Owner.owner_code == owner_code, Owner.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def next_owner_code(self) -> str:
        """Generates the next sequential owner code, e.g. OWN-000001.
        Reads the max numeric suffix among existing codes (including soft-deleted,
        to avoid ever reissuing a code)."""
        stmt = select(func.count()).select_from(Owner)
        count = self.db.execute(stmt).scalar_one()
        return f"OWN-{count + 1:06d}"

    def list_owners(
        self, page: int, page_size: int, search: Optional[str], owner_type: Optional[str],
        status: Optional[str], branch_id: Optional[int], sort_by: Optional[str], sort_dir: str,
    ) -> tuple[list[Owner], int]:
        stmt = select(Owner).where(Owner.deleted_at.is_(None))

        if owner_type:
            stmt = stmt.where(Owner.owner_type == owner_type)
        if status:
            stmt = stmt.where(Owner.status == status)
        if branch_id:
            stmt = stmt.where(Owner.branch_id == branch_id)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(
                Owner.owner_code.ilike(like),
                Owner.first_name.ilike(like),
                Owner.last_name.ilike(like),
                Owner.company_name.ilike(like),
                Owner.primary_email.ilike(like),
                Owner.primary_phone.ilike(like),
                Owner.national_id.ilike(like),
            ))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        sort_column_map = {
            "created_at": Owner.created_at,
            "owner_code": Owner.owner_code,
            "company_name": Owner.company_name,
            "last_name": Owner.last_name,
        }
        column = sort_column_map.get(sort_by, Owner.created_at)
        stmt = stmt.order_by(column.desc() if sort_dir == "desc" else column.asc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def dashboard_counts(self) -> dict:
        base = select(func.count()).select_from(Owner).where(Owner.deleted_at.is_(None))
        total = self.db.execute(base).scalar_one()

        individual = self.db.execute(base.where(Owner.owner_type == "individual")).scalar_one()
        company = self.db.execute(base.where(Owner.owner_type == "company")).scalar_one()
        active = self.db.execute(base.where(Owner.status == "active")).scalar_one()

        # owners with zero bank accounts on file
        subq = select(OwnerBankAccount.owner_id).distinct()
        missing_bank = self.db.execute(
            base.where(Owner.id.not_in(subq))
        ).scalar_one()

        recent_stmt = (
            select(Owner)
            .where(Owner.deleted_at.is_(None))
            .order_by(Owner.created_at.desc())
            .limit(5)
        )
        recent = list(self.db.execute(recent_stmt).scalars().all())

        return {
            "total_owners": total,
            "individual_owners": individual,
            "company_owners": company,
            "active_owners": active,
            "owners_missing_bank_details": missing_bank,
            "recently_added": recent,
        }


class OwnerAddressRepository(BaseRepository[OwnerAddress]):
    def __init__(self, db: Session):
        super().__init__(OwnerAddress, db)

    def list_for_owner(self, owner_id: int) -> list[OwnerAddress]:
        stmt = select(OwnerAddress).where(
            OwnerAddress.owner_id == owner_id, OwnerAddress.deleted_at.is_(None)
        ).order_by(OwnerAddress.is_primary.desc(), OwnerAddress.created_at.asc())
        return list(self.db.execute(stmt).scalars().all())

    def unset_other_primaries(self, owner_id: int, exclude_id: Optional[int] = None):
        stmt = select(OwnerAddress).where(OwnerAddress.owner_id == owner_id, OwnerAddress.is_primary.is_(True))
        if exclude_id:
            stmt = stmt.where(OwnerAddress.id != exclude_id)
        for addr in self.db.execute(stmt).scalars().all():
            addr.is_primary = False


class OwnerBankAccountRepository(BaseRepository[OwnerBankAccount]):
    def __init__(self, db: Session):
        super().__init__(OwnerBankAccount, db)

    def list_for_owner(self, owner_id: int) -> list[OwnerBankAccount]:
        stmt = select(OwnerBankAccount).where(
            OwnerBankAccount.owner_id == owner_id, OwnerBankAccount.deleted_at.is_(None)
        ).order_by(OwnerBankAccount.is_primary.desc(), OwnerBankAccount.created_at.asc())
        return list(self.db.execute(stmt).scalars().all())

    def unset_other_primaries(self, owner_id: int, exclude_id: Optional[int] = None):
        stmt = select(OwnerBankAccount).where(OwnerBankAccount.owner_id == owner_id, OwnerBankAccount.is_primary.is_(True))
        if exclude_id:
            stmt = stmt.where(OwnerBankAccount.id != exclude_id)
        for acct in self.db.execute(stmt).scalars().all():
            acct.is_primary = False


class OwnerContactRepository(BaseRepository[OwnerContact]):
    def __init__(self, db: Session):
        super().__init__(OwnerContact, db)

    def list_for_owner(self, owner_id: int) -> list[OwnerContact]:
        stmt = select(OwnerContact).where(
            OwnerContact.owner_id == owner_id, OwnerContact.deleted_at.is_(None)
        ).order_by(OwnerContact.is_primary.desc(), OwnerContact.created_at.asc())
        return list(self.db.execute(stmt).scalars().all())

    def unset_other_primaries(self, owner_id: int, exclude_id: Optional[int] = None):
        stmt = select(OwnerContact).where(OwnerContact.owner_id == owner_id, OwnerContact.is_primary.is_(True))
        if exclude_id:
            stmt = stmt.where(OwnerContact.id != exclude_id)
        for c in self.db.execute(stmt).scalars().all():
            c.is_primary = False


class OwnerDocumentRepository(BaseRepository[OwnerDocument]):
    def __init__(self, db: Session):
        super().__init__(OwnerDocument, db)

    def list_for_owner(self, owner_id: int) -> list[OwnerDocument]:
        stmt = select(OwnerDocument).where(
            OwnerDocument.owner_id == owner_id, OwnerDocument.deleted_at.is_(None)
        ).order_by(OwnerDocument.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())
