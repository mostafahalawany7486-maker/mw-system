"""
Tenant Management module (Phase 6) — the company SUBLEASES properties TO
these tenants (see business model: Owner -> Lease Agreement -> Company ->
Sublease -> Tenant). This phase builds the Tenant entity itself; the
Sublease Agreement linking Tenant to Property is a later phase, mirroring
how Phase 2 (Owner) preceded Phase 3 (Lease Agreement).

Tenant follows the exact same individual/company discriminator pattern as
Owner (Phase 2) — same reasoning: the two variants share nearly every
field and only differ in a handful of identity columns.
"""
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, Date, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class TenantType:
    INDIVIDUAL = "individual"
    COMPANY = "company"


class Tenant(BaseModel):
    __tablename__ = "tenants"

    tenant_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    tenant_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # individual | company

    # --- Individual-specific ---
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    national_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    passport_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    nationality_id: Mapped[Optional[int]] = mapped_column(ForeignKey("countries.id"), nullable=True)

    # --- Company-specific ---
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    commercial_registration_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    tax_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_person_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    contact_person_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # --- Common contact info ---
    primary_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    primary_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    secondary_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Rental Receipt phase: the receipt's "Tenant Address" line needs a
    # real data source — this was previously missing entirely (receipt
    # printed it as blank). Free-text rather than a structured
    # address_line1/city/country breakdown like Property/Owner have,
    # since this is only ever displayed as one printed line on a receipt,
    # not used for filtering/search/geocoding the way property addresses are.
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    branch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("branches.id"), nullable=True)
    notes_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Blacklist ---
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    blacklist_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blacklisted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    blacklisted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    contacts: Mapped[list["TenantContact"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    emergency_contacts: Mapped[list["TenantEmergencyContact"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    documents: Mapped[list["TenantDocument"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    ratings: Mapped[list["TenantRating"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")

    @property
    def display_name(self) -> str:
        if self.tenant_type == TenantType.COMPANY:
            return self.company_name or self.tenant_code
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or self.tenant_code


class TenantContact(BaseModel):
    """Additional contact persons (mainly relevant for company tenants)."""
    __tablename__ = "tenant_contacts"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    designation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="contacts", foreign_keys=[tenant_id])


class TenantEmergencyContact(BaseModel):
    __tablename__ = "tenant_emergency_contacts"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    relationship_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g. spouse, parent, sibling, colleague
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="emergency_contacts", foreign_keys=[tenant_id])


class TenantDocument(BaseModel):
    """Structured identity/legal documents — mirrors OwnerDocument (Phase 2)."""
    __tablename__ = "tenant_documents"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)  # national_id|passport|commercial_registration|visa|other
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

    tenant: Mapped["Tenant"] = relationship(back_populates="documents", foreign_keys=[tenant_id])

    @property
    def is_expired(self) -> bool:
        return bool(self.expiry_date and self.expiry_date < date.today())


class TenantRating(BaseModel):
    """A single rating entry (1-5) left by staff about this tenant, e.g.
    after a lease ends — payment reliability, property care, etc. A
    tenant's overall rating is the average of these entries, computed at
    read time (never stored/cached)."""
    __tablename__ = "tenant_ratings"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    rating_value: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="ratings", foreign_keys=[tenant_id])
