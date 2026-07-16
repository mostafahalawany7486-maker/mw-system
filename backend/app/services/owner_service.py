from typing import Optional
from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.owner_repository import (
    OwnerRepository, OwnerAddressRepository, OwnerBankAccountRepository,
    OwnerContactRepository, OwnerDocumentRepository,
)
from app.models.owner import Owner
from app.schemas.common import PaginationParams
from app.services.audit_service import AuditService
from app.services.file_storage_service import FileUploadService

ENTITY_TYPE = "owner"


class OwnerService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = OwnerRepository(db)
        self.address_repo = OwnerAddressRepository(db)
        self.bank_repo = OwnerBankAccountRepository(db)
        self.contact_repo = OwnerContactRepository(db)
        self.document_repo = OwnerDocumentRepository(db)
        self.audit = AuditService(db)
        self.uploader = FileUploadService()

    # ---------------- Owner CRUD ----------------
    def list_owners(self, params: PaginationParams, owner_type: Optional[str], status_: Optional[str], branch_id: Optional[int]):
        return self.repo.list_owners(
            page=params.page, page_size=params.page_size, search=params.search,
            owner_type=owner_type, status=status_, branch_id=branch_id,
            sort_by=params.sort_by, sort_dir=params.sort_dir or "desc",
        )

    def get_owner(self, owner_id: int) -> Owner:
        owner = self.repo.get_detail(owner_id)
        if not owner:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found")
        return owner

    def create_owner(self, data: dict, actor_id: Optional[int]) -> Owner:
        if data.get("national_id"):
            stmt = select(Owner).where(Owner.national_id == data["national_id"], Owner.deleted_at.is_(None))
            existing = self.db.execute(stmt).scalar_one_or_none()
            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An owner with this national ID already exists")

        payload = dict(data)
        payload["owner_code"] = self.repo.next_owner_code()
        owner = self.repo.create(payload, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, owner.id, "created", f"Owner {owner.owner_code} ({owner.display_name}) created", actor_id)
        self.audit.log_audit(ENTITY_TYPE, owner.id, "created", None, actor_id)
        self.db.commit()
        return self.repo.get_detail(owner.id)

    def update_owner(self, owner_id: int, data: dict, actor_id: Optional[int]) -> Owner:
        owner = self.get_owner(owner_id)
        before = {k: getattr(owner, k) for k in data.keys()}
        self.repo.update(owner, data, actor_id=actor_id)
        after = {k: getattr(owner, k) for k in data.keys()}
        changes = self.audit.diff(before, after)
        if changes:
            self.audit.log_activity(ENTITY_TYPE, owner.id, "updated", f"Owner {owner.owner_code} updated", actor_id)
            self.audit.log_audit(ENTITY_TYPE, owner.id, "updated", changes, actor_id)
        self.db.commit()
        return self.repo.get_detail(owner.id)

    def delete_owner(self, owner_id: int, actor_id: Optional[int]) -> None:
        owner = self.get_owner(owner_id)
        self.repo.soft_delete(owner, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, owner.id, "deleted", f"Owner {owner.owner_code} deleted", actor_id)
        self.db.commit()

    def dashboard(self) -> dict:
        return self.repo.dashboard_counts()

    # ---------------- Addresses ----------------
    def add_address(self, owner_id: int, data: dict, actor_id: Optional[int]):
        self.get_owner(owner_id)  # 404s if missing
        if data.get("is_primary"):
            self.address_repo.unset_other_primaries(owner_id)
        data["owner_id"] = owner_id
        addr = self.address_repo.create(data, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, owner_id, "address_added", "An address was added", actor_id)
        self.db.commit()
        return addr

    def update_address(self, owner_id: int, address_id: int, data: dict, actor_id: Optional[int]):
        addr = self.address_repo.get(address_id)
        if not addr or addr.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
        if data.get("is_primary"):
            self.address_repo.unset_other_primaries(owner_id, exclude_id=address_id)
        self.address_repo.update(addr, data, actor_id=actor_id)
        self.db.commit()
        return addr

    def delete_address(self, owner_id: int, address_id: int, actor_id: Optional[int]):
        addr = self.address_repo.get(address_id)
        if not addr or addr.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
        self.address_repo.soft_delete(addr, actor_id=actor_id)
        self.db.commit()

    # ---------------- Bank Accounts ----------------
    def add_bank_account(self, owner_id: int, data: dict, actor_id: Optional[int]):
        self.get_owner(owner_id)
        if data.get("is_primary"):
            self.bank_repo.unset_other_primaries(owner_id)
        data["owner_id"] = owner_id
        acct = self.bank_repo.create(data, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, owner_id, "bank_account_added", f"Bank account at {acct.bank_name} added", actor_id)
        self.audit.log_audit(ENTITY_TYPE, owner_id, "bank_account_added", {"bank_name": {"old": None, "new": acct.bank_name}}, actor_id)
        self.db.commit()
        return acct

    def update_bank_account(self, owner_id: int, account_id: int, data: dict, actor_id: Optional[int]):
        acct = self.bank_repo.get(account_id)
        if not acct or acct.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank account not found")
        if data.get("is_primary"):
            self.bank_repo.unset_other_primaries(owner_id, exclude_id=account_id)
        self.bank_repo.update(acct, data, actor_id=actor_id)
        self.db.commit()
        return acct

    def delete_bank_account(self, owner_id: int, account_id: int, actor_id: Optional[int]):
        acct = self.bank_repo.get(account_id)
        if not acct or acct.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank account not found")
        self.bank_repo.soft_delete(acct, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, owner_id, "bank_account_removed", f"Bank account at {acct.bank_name} removed", actor_id)
        self.db.commit()

    # ---------------- Contacts ----------------
    def add_contact(self, owner_id: int, data: dict, actor_id: Optional[int]):
        self.get_owner(owner_id)
        if data.get("is_primary"):
            self.contact_repo.unset_other_primaries(owner_id)
        data["owner_id"] = owner_id
        contact = self.contact_repo.create(data, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, owner_id, "contact_added", f"Contact {contact.full_name} added", actor_id)
        self.db.commit()
        return contact

    def update_contact(self, owner_id: int, contact_id: int, data: dict, actor_id: Optional[int]):
        contact = self.contact_repo.get(contact_id)
        if not contact or contact.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
        if data.get("is_primary"):
            self.contact_repo.unset_other_primaries(owner_id, exclude_id=contact_id)
        self.contact_repo.update(contact, data, actor_id=actor_id)
        self.db.commit()
        return contact

    def delete_contact(self, owner_id: int, contact_id: int, actor_id: Optional[int]):
        contact = self.contact_repo.get(contact_id)
        if not contact or contact.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
        self.contact_repo.soft_delete(contact, actor_id=actor_id)
        self.db.commit()

    # ---------------- Documents ----------------
    def upload_document(
        self, owner_id: int, file: UploadFile, document_type: str, document_number: Optional[str],
        issue_date, expiry_date, description: Optional[str], actor_id: Optional[int],
    ):
        self.get_owner(owner_id)
        meta = self.uploader.upload(file, "owner_document", owner_id)
        meta.update({
            "owner_id": owner_id,
            "document_type": document_type,
            "document_number": document_number,
            "issue_date": issue_date,
            "expiry_date": expiry_date,
            "description": description,
        })
        doc = self.document_repo.create(meta, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, owner_id, "document_added", f"Document '{doc.file_name}' ({document_type}) uploaded", actor_id)
        self.db.commit()
        return doc

    def delete_document(self, owner_id: int, document_id: int, actor_id: Optional[int]):
        doc = self.document_repo.get(document_id)
        if not doc or doc.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        self.uploader.delete(doc.file_path)
        self.document_repo.soft_delete(doc, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, owner_id, "document_removed", f"Document '{doc.file_name}' removed", actor_id)
        self.db.commit()

    def update_document(self, owner_id: int, document_id: int, data: dict, actor_id: Optional[int]):
        doc = self.document_repo.get(document_id)
        if not doc or doc.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        self.document_repo.update(doc, data, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, owner_id, "document_updated", f"Document '{doc.file_name}' metadata updated", actor_id)
        self.db.commit()
        return doc
