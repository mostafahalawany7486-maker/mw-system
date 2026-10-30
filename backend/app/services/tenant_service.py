from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.tenant_repository import (
    TenantRepository, TenantContactRepository, TenantEmergencyContactRepository,
    TenantDocumentRepository, TenantRatingRepository,
)
from app.models.tenant import Tenant
from app.schemas.common import PaginationParams
from app.services.audit_service import AuditService
from app.services.file_storage_service import FileUploadService

ENTITY_TYPE = "tenant"


class TenantService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TenantRepository(db)
        self.contact_repo = TenantContactRepository(db)
        self.emergency_repo = TenantEmergencyContactRepository(db)
        self.document_repo = TenantDocumentRepository(db)
        self.rating_repo = TenantRatingRepository(db)
        self.audit = AuditService(db)
        self.uploader = FileUploadService()

    def _attach_rating_summary(self, tenant: Tenant) -> Tenant:
        tenant.average_rating = self.repo.average_rating(tenant.id)
        tenant.rating_count = self.repo.rating_count(tenant.id)
        return tenant

    # ---------------- Tenant CRUD ----------------
    def list_tenants(self, params: PaginationParams, tenant_type: Optional[str], is_blacklisted: Optional[bool], branch_id: Optional[int], building_id: Optional[int] = None):
        items, total = self.repo.list_tenants(
            page=params.page, page_size=params.page_size, search=params.search,
            tenant_type=tenant_type, is_blacklisted=is_blacklisted, branch_id=branch_id, building_id=building_id,
            sort_by=params.sort_by, sort_dir=params.sort_dir or "desc",
        )
        items = [self._attach_rating_summary(t) for t in items]
        return items, total

    def get_tenant(self, tenant_id: int) -> Tenant:
        tenant = self.repo.get_detail(tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        return self._attach_rating_summary(tenant)

    def create_tenant(self, data: dict, actor_id: Optional[int]) -> Tenant:
        if data.get("national_id"):
            stmt = select(Tenant).where(Tenant.national_id == data["national_id"], Tenant.deleted_at.is_(None))
            existing = self.db.execute(stmt).scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A tenant with this national ID already exists")

        payload = dict(data)
        payload["tenant_code"] = self.repo.next_tenant_code()
        tenant = self.repo.create(payload, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, tenant.id, "created", f"Tenant {tenant.tenant_code} ({tenant.display_name}) created", actor_id)
        self.audit.log_audit(ENTITY_TYPE, tenant.id, "created", None, actor_id)
        self.db.commit()
        return self.get_tenant(tenant.id)

    def update_tenant(self, tenant_id: int, data: dict, actor_id: Optional[int]) -> Tenant:
        tenant = self.repo.get(tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        before = {k: getattr(tenant, k) for k in data.keys()}
        self.repo.update(tenant, data, actor_id=actor_id)
        after = {k: getattr(tenant, k) for k in data.keys()}
        changes = self.audit.diff(before, after)
        if changes:
            self.audit.log_activity(ENTITY_TYPE, tenant.id, "updated", f"Tenant {tenant.tenant_code} updated", actor_id)
            self.audit.log_audit(ENTITY_TYPE, tenant.id, "updated", changes, actor_id)
        self.db.commit()
        return self.get_tenant(tenant.id)

    def delete_tenant(self, tenant_id: int, actor_id: Optional[int]) -> None:
        tenant = self.repo.get(tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        # Same reasoning as OwnerService.delete_owner: block deleting a
        # tenant who still has an active contract, rather than letting
        # them silently vanish while a unit is still recorded as leased
        # to them.
        from app.models.rental import RentalContract, RentalContractStatus
        active_contracts = self.db.query(RentalContract).filter(
            RentalContract.tenant_id == tenant_id, RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE,
        ).count()
        if active_contracts > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete: this tenant has {active_contracts} active rental contract(s). Terminate those first.",
            )
        self.repo.soft_delete(tenant, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, tenant.id, "deleted", f"Tenant {tenant.tenant_code} deleted", actor_id)
        self.db.commit()

    def dashboard(self) -> dict:
        return self.repo.dashboard_counts()

    # ---------------- Blacklist ----------------
    def blacklist(self, tenant_id: int, reason: str, actor_id: Optional[int]) -> Tenant:
        tenant = self.repo.get(tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        if tenant.is_blacklisted:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tenant is already blacklisted")
        tenant.is_blacklisted = True
        tenant.blacklist_reason = reason
        tenant.blacklisted_at = datetime.now(timezone.utc)
        tenant.blacklisted_by = actor_id
        self.audit.log_activity(ENTITY_TYPE, tenant.id, "blacklisted", f"Tenant {tenant.tenant_code} blacklisted: {reason}", actor_id)
        self.audit.log_audit(ENTITY_TYPE, tenant.id, "blacklisted", {"is_blacklisted": {"old": False, "new": True}}, actor_id)
        self.db.commit()
        return self.get_tenant(tenant.id)

    def unblacklist(self, tenant_id: int, actor_id: Optional[int]) -> Tenant:
        tenant = self.repo.get(tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        if not tenant.is_blacklisted:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tenant is not currently blacklisted")
        tenant.is_blacklisted = False
        tenant.blacklist_reason = None
        tenant.blacklisted_at = None
        tenant.blacklisted_by = None
        self.audit.log_activity(ENTITY_TYPE, tenant.id, "unblacklisted", f"Tenant {tenant.tenant_code} removed from blacklist", actor_id)
        self.audit.log_audit(ENTITY_TYPE, tenant.id, "unblacklisted", {"is_blacklisted": {"old": True, "new": False}}, actor_id)
        self.db.commit()
        return self.get_tenant(tenant.id)

    # ---------------- Rating ----------------
    def add_rating(self, tenant_id: int, rating_value: int, comment: Optional[str], actor_id: Optional[int]):
        tenant = self.repo.get(tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        rating = self.rating_repo.create(
            {"tenant_id": tenant_id, "rating_value": rating_value, "comment": comment}, actor_id=actor_id
        )
        self.audit.log_activity(ENTITY_TYPE, tenant_id, "rating_added", f"Rating of {rating_value}/5 added", actor_id)
        self.db.commit()
        return rating

    def delete_rating(self, tenant_id: int, rating_id: int, actor_id: Optional[int]):
        rating = self.rating_repo.get(rating_id)
        if not rating or rating.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")
        self.rating_repo.soft_delete(rating, actor_id=actor_id)
        self.db.commit()

    # ---------------- Contacts ----------------
    def add_contact(self, tenant_id: int, data: dict, actor_id: Optional[int]):
        self.get_tenant(tenant_id)
        if data.get("is_primary"):
            self.contact_repo.unset_other_primaries(tenant_id)
        data["tenant_id"] = tenant_id
        contact = self.contact_repo.create(data, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, tenant_id, "contact_added", f"Contact {contact.full_name} added", actor_id)
        self.db.commit()
        return contact

    def update_contact(self, tenant_id: int, contact_id: int, data: dict, actor_id: Optional[int]):
        contact = self.contact_repo.get(contact_id)
        if not contact or contact.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
        if data.get("is_primary"):
            self.contact_repo.unset_other_primaries(tenant_id, exclude_id=contact_id)
        self.contact_repo.update(contact, data, actor_id=actor_id)
        self.db.commit()
        return contact

    def delete_contact(self, tenant_id: int, contact_id: int, actor_id: Optional[int]):
        contact = self.contact_repo.get(contact_id)
        if not contact or contact.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
        self.contact_repo.soft_delete(contact, actor_id=actor_id)
        self.db.commit()

    # ---------------- Emergency Contacts ----------------
    def add_emergency_contact(self, tenant_id: int, data: dict, actor_id: Optional[int]):
        self.get_tenant(tenant_id)
        if data.get("is_primary"):
            self.emergency_repo.unset_other_primaries(tenant_id)
        data["tenant_id"] = tenant_id
        contact = self.emergency_repo.create(data, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, tenant_id, "emergency_contact_added", f"Emergency contact {contact.full_name} added", actor_id)
        self.db.commit()
        return contact

    def update_emergency_contact(self, tenant_id: int, contact_id: int, data: dict, actor_id: Optional[int]):
        contact = self.emergency_repo.get(contact_id)
        if not contact or contact.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergency contact not found")
        if data.get("is_primary"):
            self.emergency_repo.unset_other_primaries(tenant_id, exclude_id=contact_id)
        self.emergency_repo.update(contact, data, actor_id=actor_id)
        self.db.commit()
        return contact

    def delete_emergency_contact(self, tenant_id: int, contact_id: int, actor_id: Optional[int]):
        contact = self.emergency_repo.get(contact_id)
        if not contact or contact.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergency contact not found")
        self.emergency_repo.soft_delete(contact, actor_id=actor_id)
        self.db.commit()

    # ---------------- Documents ----------------
    def upload_document(
        self, tenant_id: int, file: UploadFile, document_type: str, document_number: Optional[str],
        issue_date, expiry_date, description: Optional[str], actor_id: Optional[int],
    ):
        self.get_tenant(tenant_id)
        meta = self.uploader.upload(file, "tenant_document", tenant_id)
        meta.update({
            "tenant_id": tenant_id, "document_type": document_type, "document_number": document_number,
            "issue_date": issue_date, "expiry_date": expiry_date, "description": description,
        })
        doc = self.document_repo.create(meta, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, tenant_id, "document_added", f"Document '{doc.file_name}' ({document_type}) uploaded", actor_id)
        self.db.commit()
        return doc

    def update_document(self, tenant_id: int, document_id: int, data: dict, actor_id: Optional[int]):
        doc = self.document_repo.get(document_id)
        if not doc or doc.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        self.document_repo.update(doc, data, actor_id=actor_id)
        self.db.commit()
        return doc

    def delete_document(self, tenant_id: int, document_id: int, actor_id: Optional[int]):
        doc = self.document_repo.get(document_id)
        if not doc or doc.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        self.uploader.delete(doc.file_path)
        self.document_repo.soft_delete(doc, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, tenant_id, "document_removed", f"Document '{doc.file_name}' removed", actor_id)
        self.db.commit()
