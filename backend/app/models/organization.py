"""
Organization & lookup entities: Company Profile, Branches, Countries,
Cities, Currencies, System Settings.
"""
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class Country(BaseModel):
    __tablename__ = "countries"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    iso_code2: Mapped[str] = mapped_column(String(2), unique=True, nullable=False)  # e.g. US, AE
    iso_code3: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)  # e.g. USA, ARE
    phone_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    cities: Mapped[list["City"]] = relationship(back_populates="country")


class City(BaseModel):
    __tablename__ = "cities"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"), nullable=False)

    country: Mapped["Country"] = relationship(back_populates="cities")


class Currency(BaseModel):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)  # ISO 4217, e.g. USD
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    exchange_rate_to_base: Mapped[float] = mapped_column(Numeric(18, 6), default=1.0)
    is_base_currency: Mapped[bool] = mapped_column(Boolean, default=False)


class CompanyProfile(BaseModel):
    """Singleton-style table: one active row represents the operating company."""
    __tablename__ = "company_profile"

    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    registration_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tax_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cities.id"), nullable=True)
    country_id: Mapped[Optional[int]] = mapped_column(ForeignKey("countries.id"), nullable=True)
    base_currency_id: Mapped[Optional[int]] = mapped_column(ForeignKey("currencies.id"), nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    default_language: Mapped[str] = mapped_column(String(10), default="en")  # future multi-language hook


class Branch(BaseModel):
    __tablename__ = "branches"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cities.id"), nullable=True)
    country_id: Mapped[Optional[int]] = mapped_column(ForeignKey("countries.id"), nullable=True)
    is_head_office: Mapped[bool] = mapped_column(Boolean, default=False)
    manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    city: Mapped[Optional["City"]] = relationship(foreign_keys=[city_id])
    country: Mapped[Optional["Country"]] = relationship(foreign_keys=[country_id])


class SystemSetting(BaseModel):
    """Key-value system settings store (feature flags, formats, defaults)."""
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(20), default="string")  # string|number|boolean|json
    category: Mapped[str] = mapped_column(String(50), default="general")
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_editable: Mapped[bool] = mapped_column(Boolean, default=True)
