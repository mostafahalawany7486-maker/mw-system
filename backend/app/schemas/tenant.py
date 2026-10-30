from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator, model_validator
from app.schemas.common import AuditFieldsOut


# ---------------- Tenant Contact ----------------
class TenantContactCreate(BaseModel):
    full_name: str
    designation: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_primary: bool = False


class TenantContactUpdate(BaseModel):
    full_name: Optional[str] = None
    designation: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_primary: Optional[bool] = None


class TenantContactOut(AuditFieldsOut):
    tenant_id: int
    full_name: str
    designation: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_primary: bool


# ---------------- Emergency Contact ----------------
class TenantEmergencyContactCreate(BaseModel):
    full_name: str
    relationship_type: Optional[str] = None
    phone: str
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    is_primary: bool = False


class TenantEmergencyContactUpdate(BaseModel):
    full_name: Optional[str] = None
    relationship_type: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    is_primary: Optional[bool] = None


class TenantEmergencyContactOut(AuditFieldsOut):
    tenant_id: int
    full_name: str
    relationship_type: Optional[str] = None
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    is_primary: bool


# ---------------- Tenant Document ----------------
class TenantDocumentUpdate(BaseModel):
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    description: Optional[str] = None


class TenantDocumentOut(AuditFieldsOut):
    tenant_id: int
    document_type: str
    document_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    file_name: str
    file_url: Optional[str] = None
    file_size_bytes: int
    mime_type: str
    description: Optional[str] = None
    is_expired: bool = False


# ---------------- Tenant Rating ----------------
class TenantRatingCreate(BaseModel):
    rating_value: int
    comment: Optional[str] = None

    @field_validator("rating_value")
    @classmethod
    def validate_rating(cls, v: int) -> int:
        if not (1 <= v <= 5):
            raise ValueError("rating_value must be between 1 and 5")
        return v


class TenantRatingOut(AuditFieldsOut):
    tenant_id: int
    rating_value: int
    comment: Optional[str] = None


# ---------------- Blacklist ----------------
class BlacklistRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("A reason is required to blacklist a tenant")
        return v


# ---------------- Tenant ----------------
class TenantCreate(BaseModel):
    tenant_type: str  # "individual" | "company"

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None
    passport_number: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality_id: Optional[int] = None

    company_name: Optional[str] = None
    commercial_registration_number: Optional[str] = None
    tax_number: Optional[str] = None
    contact_person_name: Optional[str] = None
    contact_person_title: Optional[str] = None

    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = None
    secondary_phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    branch_id: Optional[int] = None
    notes_summary: Optional[str] = None

    @field_validator("tenant_type")
    @classmethod
    def validate_tenant_type(cls, v: str) -> str:
        if v not in ("individual", "company"):
            raise ValueError("tenant_type must be 'individual' or 'company'")
        return v

    @model_validator(mode="after")
    def validate_type_specific_fields(self):
        if self.tenant_type == "individual":
            if not self.first_name or not self.last_name:
                raise ValueError("first_name and last_name are required for individual tenants")
        else:
            if not self.company_name:
                raise ValueError("company_name is required for company tenants")
        return self


class TenantUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None
    passport_number: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality_id: Optional[int] = None

    company_name: Optional[str] = None
    commercial_registration_number: Optional[str] = None
    tax_number: Optional[str] = None
    contact_person_name: Optional[str] = None
    contact_person_title: Optional[str] = None

    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = None
    secondary_phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    branch_id: Optional[int] = None
    notes_summary: Optional[str] = None
    status: Optional[str] = None


class TenantListItemOut(AuditFieldsOut):
    tenant_code: str
    tenant_type: str
    display_name: str
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    branch_id: Optional[int] = None
    is_blacklisted: bool
    average_rating: Optional[float] = None


class TenantDetailOut(AuditFieldsOut):
    tenant_code: str
    tenant_type: str
    display_name: str

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None
    passport_number: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality_id: Optional[int] = None

    company_name: Optional[str] = None
    commercial_registration_number: Optional[str] = None
    tax_number: Optional[str] = None
    contact_person_name: Optional[str] = None
    contact_person_title: Optional[str] = None

    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    secondary_phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    branch_id: Optional[int] = None
    notes_summary: Optional[str] = None

    is_blacklisted: bool
    blacklist_reason: Optional[str] = None
    blacklisted_at: Optional[datetime] = None
    blacklisted_by: Optional[int] = None

    contacts: List[TenantContactOut] = []
    emergency_contacts: List[TenantEmergencyContactOut] = []
    documents: List[TenantDocumentOut] = []
    ratings: List[TenantRatingOut] = []
    average_rating: Optional[float] = None
    rating_count: int = 0


class TenantDashboardOut(BaseModel):
    total_tenants: int
    individual_tenants: int
    company_tenants: int
    active_tenants: int
    blacklisted_tenants: int
    average_rating_overall: Optional[float] = None
    recently_added: List[TenantListItemOut] = []
