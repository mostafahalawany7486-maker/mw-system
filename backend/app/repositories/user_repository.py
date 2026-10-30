from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.models.user import User, Role, Permission
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def get_by_email(self, email: str, include_deleted: bool = False) -> Optional[User]:
        stmt = select(User).options(selectinload(User.role).selectinload(Role.permissions)).where(
            User.email == email.lower()
        )
        if not include_deleted:
            stmt = stmt.where(User.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_with_role(self, user_id: int) -> Optional[User]:
        stmt = (
            select(User)
            .options(selectinload(User.role).selectinload(Role.permissions))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_with_role(self, page: int, page_size: int, search: Optional[str], sort_by: Optional[str],
                        sort_dir: str, filters: Optional[dict]) -> tuple[list[User], int]:
        """Same pagination behavior as BaseRepository.list(), but eager-loads
        role+permissions in one extra query instead of N lazy-loads."""
        from sqlalchemy import func, or_

        stmt = select(User).where(User.deleted_at.is_(None))
        if search:
            conditions = [User.first_name.ilike(f"%{search}%"), User.last_name.ilike(f"%{search}%"), User.email.ilike(f"%{search}%")]
            stmt = stmt.where(or_(*conditions))
        if filters:
            for key, value in filters.items():
                if value is not None and hasattr(User, key):
                    stmt = stmt.where(getattr(User, key) == value)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        if sort_by and hasattr(User, sort_by):
            column = getattr(User, sort_by)
            stmt = stmt.order_by(column.desc() if sort_dir == "desc" else column.asc())
        else:
            stmt = stmt.order_by(User.id.desc())

        stmt = stmt.options(selectinload(User.role).selectinload(Role.permissions))
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total


class RoleRepository(BaseRepository[Role]):
    def __init__(self, db: Session):
        super().__init__(Role, db)

    def get_with_permissions(self, role_id: int) -> Optional[Role]:
        stmt = select(Role).options(selectinload(Role.permissions)).where(
            Role.id == role_id, Role.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_name(self, name: str) -> Optional[Role]:
        stmt = select(Role).where(Role.name == name, Role.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()


class PermissionRepository(BaseRepository[Permission]):
    def __init__(self, db: Session):
        super().__init__(Permission, db)

    def get_by_ids(self, ids: list[int]) -> list[Permission]:
        if not ids:
            return []
        stmt = select(Permission).where(Permission.id.in_(ids))
        return list(self.db.execute(stmt).scalars().all())
