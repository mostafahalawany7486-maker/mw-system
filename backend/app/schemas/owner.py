from datetime import date
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator, model_validator
from app.schemas.common import AuditFieldsOut


# ---------------- Owner Address ----------------
class OwnerAddressCreate(BaseModel):
    address_type: str = "mailing"
    line1: str
    line2: Optional[str] = None
    city_id: Optional[int] = None
    country_id: Optional[int] = None
    postal_code: Optional[str] = None
    is_primary: bool = False


class OwnerAddressUpdate(BaseModel):
    address_type: Optional[str] = None
    line1: Optional[str] = None
    line2: Optional[str] = None
    city_id: Optional[int] = None
    country_id: Optional[int] = None
    postal_code: Optional[str] = None
    is_primary: Optional[bool] = None


class OwnerAddressOut(AuditFieldsOut):
    owner_id: int
    address_type: str
    line1: str
    line2: Optional[str] = None
    city_id: Optional[int] = None
    country_id: Optional[int] = None
    postal_code: Optional[str] = None
    is_primary: bool


# ---------------- Owner Bank Account ----------------
class OwnerBankAccountCreate(BaseModel):
    bank_name: str
    account_holder_name: str
    account_number: Optional[str] = None
    iban: Optional[str] = None
    swift_code: Optional[str] = None
    currency_id: Optional[int] = None
    is_primary: bool = False


class OwnerBankAccountUpdate(BaseModel):
    bank_name: Optional[str] = None
    account_holder_name: Optional[str] = None
    account_number: Optional[str] = None
    iban: Optional[str] = None
    swift_code: Optional[str] = None
    currency_id: Optional[int] = None
    is_primary: Optional[bool] = None


class OwnerBankAccountOut(AuditFieldsOut):
    owner_id: int
    bank_name: str
    account_holder_name: str
    account_number: Optional[str] = None
    iban: Optional[str] = None
    swift_code: Optional[str] = None
    currency_id: Optional[int] = None
    is_primary: bool


# ---------------- Owner Contact ----------------
class OwnerContactCreate(BaseModel):
    full_name: str
    designation: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_primary: bool = False


class OwnerContactUpdate(BaseModel):
    full_name: Optional[str] = None
    designation: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_primary: Optional[bool] = None


class OwnerContactOut(AuditFieldsOut):
    owner_id: int
    full_name: str
    designation: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_primary: bool


# ---------------- Owner Document ----------------
class OwnerDocumentUpdate(BaseModel):
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    description: Optional[str] = None


class OwnerDocumentOut(AuditFieldsOut):
    owner_id: int
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


# ---------------- Owner ----------------
class OwnerCreate(BaseModel):
    owner_type: str  # "individual" | "company"

    # individual
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality_id: Optional[int] = None

    # company
    company_name: Optional[str] = None
    registration_number: Optional[str] = None
    tax_number: Optional[str] = None
    contact_person_name: Optional[str] = None
    contact_person_title: Optional[str] = None

    # common
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = None
    secondary_phone: Optional[str] = None
    website: Optional[str] = None
    branch_id: Optional[int] = None
    notes_summary: Optional[str] = None

    @field_validator("owner_type")
    @classmethod
    def validate_owner_type(cls, v: str) -> str:
        if v not in ("individual", "company"):
            raise ValueError("owner_type must be 'individual' or 'company'")
        return v

    @model_validator(mode="after")
    def validate_type_specific_fields(self):
        if self.owner_type == "individual":
            if not self.first_name or not self.last_name:
                raise ValueError("first_name and last_name are required for individual owners")
        else:
            if not self.company_name:
                raise ValueError("company_name is required for company owners")
        return self


class OwnerUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality_id: Optional[int] = None

    company_name: Optional[str] = None
    registration_number: Optional[str] = None
    tax_number: Optional[str] = None
    contact_person_name: Optional[str] = None
    contact_person_title: Optional[str] = None

    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = None
    secondary_phone: Optional[str] = None
    website: Optional[str] = None
    branch_id: Optional[int] = None
    notes_summary: Optional[str] = None
    status: Optional[str] = None


class OwnerListItemOut(AuditFieldsOut):
    owner_code: str
    owner_type: str
    display_name: str
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    branch_id: Optional[int] = None


class OwnerDetailOut(AuditFieldsOut):
    owner_code: str
    owner_type: str
    display_name: str

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality_id: Optional[int] = None

    company_name: Optional[str] = None
    registration_number: Optional[str] = None
    tax_number: Optional[str] = None
    contact_person_name: Optional[str] = None
    contact_person_title: Optional[str] = None

    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    secondary_phone: Optional[str] = None
    website: Optional[str] = None
    branch_id: Optional[int] = None
    notes_summary: Optional[str] = None

    addresses: List[OwnerAddressOut] = []
    bank_accounts: List[OwnerBankAccountOut] = []
    contacts: List[OwnerContactOut] = []
    documents: List[OwnerDocumentOut] = []


class OwnerDashboardOut(BaseModel):
    total_owners: int
    individual_owners: int
    company_owners: int
    active_owners: int
    owners_missing_bank_details: int
    recently_added: List[OwnerListItemOut] = []
