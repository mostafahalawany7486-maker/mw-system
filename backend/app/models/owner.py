"""
Property Owners module (Phase 2).

Business context: the company leases properties FROM these owners (see
project business model). An Owner is either an Individual or a Company —
modeled as a single table with a `owner_type` discriminator rather than
joined-table inheritance, since the two variants share almost every
attribute (contact info, addresses, bank accounts, documents) and only
differ in a handful of identity fields. This keeps CRUD, search, and
filtering simple while still being fully validated per-type in the service
layer.

Sub-resources (addresses, bank accounts, contacts, documents) are modeled
as dedicated child tables (owner_id FK) rather than the generic polymorphic
Attachments/Notes tables, because they have structured, owner-specific
fields (e.g. IBAN, document expiry) that benefit from real columns rather
than a generic key-value blob. Generic Notes and Activity Log (from Phase 1)
are still reused as-is for freeform notes and history — see OwnerService.
"""
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, Date, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class OwnerType:
    INDIVIDUAL = "individual"
    COMPANY = "company"


class Owner(BaseModel):
    __tablename__ = "owners"

    owner_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    owner_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # individual | company

    # --- Individual-specific (nullable when owner_type=company) ---
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    national_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    nationality_id: Mapped[Optional[int]] = mapped_column(ForeignKey("countries.id"), nullable=True)

    # --- Company-specific (nullable when owner_type=individual) ---
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    registration_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tax_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_person_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    contact_person_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # --- Common contact info ---
    primary_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    primary_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    secondary_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    branch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("branches.id"), nullable=True)
    notes_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # short free-text summary shown on list/detail header

    addresses: Mapped[list["OwnerAddress"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    bank_accounts: Mapped[list["OwnerBankAccount"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    contacts: Mapped[list["OwnerContact"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    documents: Mapped[list["OwnerDocument"]] = relationship(back_populates="owner", cascade="all, delete-orphan")

    @property
    def display_name(self) -> str:
        if self.owner_type == OwnerType.COMPANY:
            return self.company_name or self.owner_code
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or self.owner_code


class OwnerAddress(BaseModel):
    __tablename__ = "owner_addresses"

    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    address_type: Mapped[str] = mapped_column(String(30), default="mailing")  # mailing | permanent | property | other
    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cities.id"), nullable=True)
    country_id: Mapped[Optional[int]] = mapped_column(ForeignKey("countries.id"), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    owner: Mapped["Owner"] = relationship(back_populates="addresses", foreign_keys=[owner_id])


class OwnerBankAccount(BaseModel):
    __tablename__ = "owner_bank_accounts"

    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_name: Mapped[str] = mapped_column(String(150), nullable=False)
    account_holder_name: Mapped[str] = mapped_column(String(150), nullable=False)
    account_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    iban: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    swift_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    currency_id: Mapped[Optional[int]] = mapped_column(ForeignKey("currencies.id"), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    owner: Mapped["Owner"] = relationship(back_populates="bank_accounts", foreign_keys=[owner_id])


class OwnerContact(BaseModel):
    """Additional contact persons for an owner (mainly relevant for company owners
    with multiple points of contact — e.g. finance vs. operations)."""
    __tablename__ = "owner_contacts"

    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    designation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    owner: Mapped["Owner"] = relationship(back_populates="contacts", foreign_keys=[owner_id])


class OwnerDocument(BaseModel):
    """Structured legal/KYC documents (ID, trade license, POA, tax cert, ...),
    distinct from the generic Attachments system: these carry a document type,
    number, and expiry date so the system can later flag expiring documents."""
    __tablename__ = "owner_documents"

    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)  # id_card|passport|trade_license|tax_certificate|poa|other
    document_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(20), default="local")

    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    owner: Mapped["Owner"] = relationship(back_populates="documents", foreign_keys=[owner_id])

    @property
    def is_expired(self) -> bool:
        return bool(self.expiry_date and self.expiry_date < date.today())
