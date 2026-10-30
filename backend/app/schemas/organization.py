from typing import Optional
from pydantic import BaseModel, EmailStr
from app.schemas.common import AuditFieldsOut


# ---------- Country ----------
class CountryCreate(BaseModel):
    name: str
    iso_code2: str
    iso_code3: str
    phone_code: Optional[str] = None


class CountryUpdate(BaseModel):
    name: Optional[str] = None
    iso_code2: Optional[str] = None
    iso_code3: Optional[str] = None
    phone_code: Optional[str] = None
    status: Optional[str] = None


class CountryOut(AuditFieldsOut):
    name: str
    iso_code2: str
    iso_code3: str
    phone_code: Optional[str] = None


# ---------- City ----------
class CityCreate(BaseModel):
    name: str
    country_id: int


class CityUpdate(BaseModel):
    name: Optional[str] = None
    country_id: Optional[int] = None
    status: Optional[str] = None


class CityOut(AuditFieldsOut):
    name: str
    country_id: int


# ---------- Currency ----------
class CurrencyCreate(BaseModel):
    code: str
    name: str
    symbol: str
    exchange_rate_to_base: float = 1.0
    is_base_currency: bool = False


class CurrencyUpdate(BaseModel):
    name: Optional[str] = None
    symbol: Optional[str] = None
    exchange_rate_to_base: Optional[float] = None
    is_base_currency: Optional[bool] = None
    status: Optional[str] = None


class CurrencyOut(AuditFieldsOut):
    code: str
    name: str
    symbol: str
    exchange_rate_to_base: float
    is_base_currency: bool


# ---------- Company Profile ----------
class CompanyProfileUpdate(BaseModel):
    legal_name: Optional[str] = None
    trade_name: Optional[str] = None
    registration_number: Optional[str] = None
    tax_number: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city_id: Optional[int] = None
    country_id: Optional[int] = None
    base_currency_id: Optional[int] = None
    logo_url: Optional[str] = None
    default_language: Optional[str] = None


class CompanyProfileOut(AuditFieldsOut):
    legal_name: str
    trade_name: Optional[str] = None
    registration_number: Optional[str] = None
    tax_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city_id: Optional[int] = None
    country_id: Optional[int] = None
    base_currency_id: Optional[int] = None
    logo_url: Optional[str] = None
    default_language: str


# ---------- Branch ----------
class BranchCreate(BaseModel):
    name: str
    code: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    city_id: Optional[int] = None
    country_id: Optional[int] = None
    is_head_office: bool = False
    manager_id: Optional[int] = None


class BranchUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    city_id: Optional[int] = None
    country_id: Optional[int] = None
    is_head_office: Optional[bool] = None
    manager_id: Optional[int] = None
    status: Optional[str] = None


class BranchOut(AuditFieldsOut):
    name: str
    code: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    city_id: Optional[int] = None
    country_id: Optional[int] = None
    is_head_office: bool
    manager_id: Optional[int] = None


# ---------- System Setting ----------
class SystemSettingUpdate(BaseModel):
    value: Optional[str] = None


class SystemSettingOut(AuditFieldsOut):
    key: str
    value: Optional[str] = None
    value_type: str
    category: str
    description: Optional[str] = None
    is_editable: bool
