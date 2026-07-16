"""
Generic Repository Pattern base class. Concrete repositories subclass this
for entity-specific query methods, while inheriting standard CRUD, soft
delete, and pagination/search/sort behavior for free.
"""
from datetime import datetime
from typing import Generic, TypeVar, Type, Optional, Sequence
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from app.models.base import BaseModel, RecordStatus

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get(self, id: int, include_deleted: bool = False) -> Optional[ModelType]:
        stmt = select(self.model).where(self.model.id == id)
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_uuid(self, uuid: str) -> Optional[ModelType]:
        stmt = select(self.model).where(self.model.uuid == uuid, self.model.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        search_fields: Optional[list[str]] = None,
        sort_by: Optional[str] = None,
        sort_dir: str = "asc",
        filters: Optional[dict] = None,
        include_deleted: bool = False,
    ) -> tuple[Sequence[ModelType], int]:
        stmt = select(self.model)
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))

        if search and search_fields:
            conditions = []
            for field in search_fields:
                column = getattr(self.model, field, None)
                if column is not None:
                    conditions.append(column.ilike(f"%{search}%"))
            if conditions:
                stmt = stmt.where(or_(*conditions))

        if filters:
            for key, value in filters.items():
                if value is not None and hasattr(self.model, key):
                    stmt = stmt.where(getattr(self.model, key) == value)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        if sort_by and hasattr(self.model, sort_by):
            column = getattr(self.model, sort_by)
            stmt = stmt.order_by(column.desc() if sort_dir == "desc" else column.asc())
        else:
            stmt = stmt.order_by(self.model.id.desc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = self.db.execute(stmt).scalars().all()
        return items, total

    def create(self, obj_in: dict, actor_id: Optional[int] = None) -> ModelType:
        obj = self.model(**obj_in)
        if actor_id is not None:
            obj.created_by = actor_id
            obj.updated_by = actor_id
        self.db.add(obj)
        self.db.flush()
        return obj

    def update(self, db_obj: ModelType, obj_in: dict, actor_id: Optional[int] = None) -> ModelType:
        for key, value in obj_in.items():
            if value is not None and hasattr(db_obj, key):
                setattr(db_obj, key, value)
        if actor_id is not None:
            db_obj.updated_by = actor_id
        db_obj.updated_at = datetime.utcnow()
        self.db.flush()
        return db_obj

    def soft_delete(self, db_obj: ModelType, actor_id: Optional[int] = None) -> ModelType:
        db_obj.deleted_at = datetime.utcnow()
        db_obj.status = RecordStatus.ARCHIVED
        if actor_id is not None:
            db_obj.updated_by = actor_id
        self.db.flush()
        return db_obj

    def restore(self, db_obj: ModelType, actor_id: Optional[int] = None) -> ModelType:
        db_obj.deleted_at = None
        db_obj.status = RecordStatus.ACTIVE
        if actor_id is not None:
            db_obj.updated_by = actor_id
        self.db.flush()
        return db_obj
