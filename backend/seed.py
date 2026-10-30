"""
Foundational/setup data only (no demo business data) — run with: python seed.py
Idempotent: safe to run multiple times (checks for existing records first).

Seeds: permission catalog + system roles, countries/cities, currencies,
company profile, head office branch, system settings, the Amenities
lookup catalog, and the first Administrator account (from
FIRST_ADMIN_EMAIL / FIRST_ADMIN_PASSWORD in .env).

This intentionally does NOT create any Owners, Tenants, Properties,
Leases/Rental Contracts, Financial transactions, Maintenance data, or
Accounting data — every real company's data is different, and shipping
fictional Owners/Tenants/balances was actively unhelpful once a real
company starts using this deployment. The previous version of this
script (which also seeded ~2 owners, 3 tenants, 6 properties, sample
leases/rentals/transactions/maintenance/accounting entries, and two
extra demo logins) is kept as `seed_with_demo_data.py.bak` for
reference or local dev/demo use — copy it back over `seed.py` (or run
it directly with `python seed_with_demo_data.py.bak`) if you want that
richer demo dataset instead, e.g. for a sales demo or QA environment.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.core.config import settings
from app.models.user import User, Role, Permission
from app.models.organization import Country, City, Currency, CompanyProfile, Branch, SystemSetting
from app.models.owner import Owner, OwnerAddress, OwnerBankAccount, OwnerContact
from app.models.lease import LeaseAgreement, LeaseStatus
from app.models.property import Property, Amenity, Floor
from app.models.tenant import Tenant, TenantContact, TenantEmergencyContact
from app.models.rental import RentalContract, RentalContractStatus, RentalPaymentInstallment, RentalInstallmentStatus
import uuid
from app.models.financial import FinancialAccount, Transaction, TransactionType, TransactionDirection, Receipt, Invoice, InvoiceStatus
from app.models.maintenance import (
    Contractor, Technician, MaintenanceRequest, MaintenanceRequestStatus, MaintenancePriority,
    MaintenanceMaterial, MaintenanceLaborCost,
)
from app.models.maintenance_contract import MaintenanceContract, MaintenanceContractStatus
from app.models.accounting import (
    ChartOfAccount, CostCenter, VatRate, PostingRule, JournalEntry, JournalEntryLine,
    EntryStatus, SourceType,
)
from app.models.reports import ReportSchedule, ReportFrequency, ReportExportFormat

# ---------------------------------------------------------------------------
# Permission catalog. Codes follow 'module.action'. Every module built in
# this and future phases should register its permissions here.
# ---------------------------------------------------------------------------
MODULES = [
    "users", "roles", "branches", "countries", "cities", "currencies",
    "company", "settings", "audit", "owners", "leases", "properties", "tenants", "rentals", "financial", "maintenance", "accounting", "reports",
    "rent_cycles", "rent_vouchers", "payments", "owner_ledger", "occupancy",
]
ACTIONS = ["view", "create", "edit", "delete"]

SYSTEM_ROLES = [
    {"name": "Administrator", "description": "Full system access", "is_system_role": True, "all_permissions": True},
    {"name": "Branch Manager", "description": "Manages a single branch's operations", "is_system_role": True,
     "permission_codes": [
         "users.view", "branches.view", "countries.view", "cities.view",
         "currencies.view", "company.view", "settings.view",
         "owners.view", "owners.create", "owners.edit",
         "leases.view", "leases.create", "leases.edit",
         "properties.view", "properties.create", "properties.edit",
         "tenants.view", "tenants.create", "tenants.edit",
         "rentals.view", "rentals.create", "rentals.edit",
         "financial.view", "financial.create", "financial.edit",
         "maintenance.view", "maintenance.create", "maintenance.edit",
         "accounting.view", "reports.view", "reports.create", "reports.edit", "reports.delete",
         "rent_cycles.view", "rent_cycles.create", "rent_cycles.edit",
         "rent_vouchers.view", "rent_vouchers.create", "rent_vouchers.edit",
         "payments.view", "payments.create", "payments.edit",
         "owner_ledger.view", "owner_ledger.create", "owner_ledger.edit",
         "occupancy.view", "occupancy.create", "occupancy.edit",
     ]},
    {"name": "Staff", "description": "Standard operational staff member", "is_system_role": True,
     "permission_codes": ["branches.view", "countries.view", "cities.view", "currencies.view", "company.view", "owners.view", "leases.view", "properties.view", "tenants.view", "rentals.view", "financial.view", "maintenance.view", "maintenance.create", "reports.view", "rent_cycles.view", "rent_vouchers.view", "rent_vouchers.create", "payments.view", "payments.create", "owner_ledger.view", "occupancy.view", "occupancy.edit"]},
]

COUNTRIES = [
    {"name": "United States", "iso_code2": "US", "iso_code3": "USA", "phone_code": "+1"},
    {"name": "United Arab Emirates", "iso_code2": "AE", "iso_code3": "ARE", "phone_code": "+971"},
    {"name": "United Kingdom", "iso_code2": "GB", "iso_code3": "GBR", "phone_code": "+44"},
    {"name": "Kuwait", "iso_code2": "KW", "iso_code3": "KWT", "phone_code": "+965"},
]

CITIES = {
    "United States": ["New York", "Los Angeles", "Chicago"],
    "United Arab Emirates": ["Dubai", "Abu Dhabi"],
    "United Kingdom": ["London", "Manchester"],
    "Kuwait": ["Kuwait City", "Hawalli", "Salmiya"],
}

CURRENCIES = [
    {"code": "USD", "name": "US Dollar", "symbol": "$", "is_base_currency": False, "exchange_rate_to_base": 3.2468},
    {"code": "AED", "name": "UAE Dirham", "symbol": "د.إ", "is_base_currency": False, "exchange_rate_to_base": 11.928},
    {"code": "GBP", "name": "British Pound", "symbol": "£", "is_base_currency": False, "exchange_rate_to_base": 2.565},
    # Confirmed directly: this company operates in Kuwaiti Dinar — set
    # as the base currency (rate 1.0), with the other three re-based
    # relative to it instead of USD (was the base before this). These
    # are still just reasonable starting reference rates for a fresh
    # install, not live/precise FX data — meant to be corrected via
    # whatever the actual rate is when it matters, same as before.
    {"code": "KWD", "name": "Kuwaiti Dinar", "symbol": "د.ك", "is_base_currency": True, "exchange_rate_to_base": 1.0},
]

SYSTEM_SETTINGS = [
    {"key": "date_format", "value": "YYYY-MM-DD", "value_type": "string", "category": "general", "description": "Default date display format"},
    {"key": "theme_default", "value": "light", "value_type": "string", "category": "appearance", "description": "Default UI theme for new users"},
    {"key": "session_timeout_minutes", "value": "30", "value_type": "number", "category": "security", "description": "Idle session timeout"},
    {"key": "company_name_display", "value": "PMS Leasing Co.", "value_type": "string", "category": "general", "description": "Fallback display name before company profile is set"},
]

AMENITIES = [
    {"name": "Swimming Pool", "category": "comfort"},
    {"name": "Gym", "category": "comfort"},
    {"name": "Parking", "category": "utility"},
    {"name": "Elevator", "category": "utility"},
    {"name": "24/7 Security", "category": "safety"},
    {"name": "CCTV", "category": "safety"},
    {"name": "Central AC", "category": "comfort"},
    {"name": "Balcony", "category": "comfort"},
    {"name": "Furnished", "category": "comfort"},
    {"name": "Pet Friendly", "category": "policy"},
    {"name": "Loading Dock", "category": "utility"},
    {"name": "Fire Safety System", "category": "safety"},
]


def run():
    db = SessionLocal()
    try:
        # ---------------- Permissions ----------------
        existing_codes = {p.code for p in db.query(Permission).all()}
        for module in MODULES:
            for action in ACTIONS:
                code = f"{module}.{action}"
                if code not in existing_codes:
                    db.add(Permission(code=code, module=module, action=action, description=f"Allows '{action}' on {module}"))
        db.commit()
        print(f"✔ Permissions ensured ({len(MODULES) * len(ACTIONS)} total)")

        all_permissions = db.query(Permission).all()
        perm_by_code = {p.code: p for p in all_permissions}

        # ---------------- Roles ----------------
        for role_def in SYSTEM_ROLES:
            role = db.query(Role).filter(Role.name == role_def["name"]).first()
            if not role:
                role = Role(name=role_def["name"], description=role_def["description"], is_system_role=role_def["is_system_role"])
                db.add(role)
                db.flush()
            if role_def.get("all_permissions"):
                role.permissions = all_permissions
            else:
                role.permissions = [perm_by_code[c] for c in role_def.get("permission_codes", []) if c in perm_by_code]
        db.commit()
        print(f"✔ System roles ensured ({len(SYSTEM_ROLES)})")

        # ---------------- Countries & Cities ----------------
        country_by_name = {}
        for c in COUNTRIES:
            country = db.query(Country).filter(Country.iso_code2 == c["iso_code2"]).first()
            if not country:
                country = Country(**c)
                db.add(country)
                db.flush()
            country_by_name[c["name"]] = country
        db.commit()

        for country_name, city_names in CITIES.items():
            country = country_by_name[country_name]
            for city_name in city_names:
                exists = db.query(City).filter(City.name == city_name, City.country_id == country.id).first()
                if not exists:
                    db.add(City(name=city_name, country_id=country.id))
        db.commit()
        print(f"✔ Countries ({len(COUNTRIES)}) and cities seeded")

        # ---------------- Currencies ----------------
        for cur in CURRENCIES:
            exists = db.query(Currency).filter(Currency.code == cur["code"]).first()
            if not exists:
                db.add(Currency(**cur))
        db.commit()
        print(f"✔ Currencies ensured ({len(CURRENCIES)})")

        # ---------------- Company Profile ----------------
        # Deliberately left blank/neutral — not pre-filled with any
        # placeholder company name, email, address, country, city, or
        # base currency. Every one of those used to be filled with
        # example data (a fake US company/address), which is exactly
        # the kind of "looks real, isn't" seed data a fresh company
        # setup should never start with. legal_name is the one NOT NULL
        # column on this table, so it gets an unmistakable placeholder
        # instead of a fake real-sounding name; everything else stays
        # genuinely empty until set from Company Profile in the app.
        profile = db.query(CompanyProfile).first()
        if not profile:
            profile = CompanyProfile(legal_name="My Company", default_language="en")
            db.add(profile)
        db.commit()
        print("✔ Company profile ensured (blank — set your real details from Company Profile in the app)")

        # ---------------- Head Office Branch ----------------
        branch = db.query(Branch).filter(Branch.code == "HO").first()
        if not branch:
            branch = Branch(name="Head Office", code="HO", is_head_office=True)
            db.add(branch)
        db.commit()
        print("✔ Head office branch ensured")

        # ---------------- System Settings ----------------
        for s in SYSTEM_SETTINGS:
            exists = db.query(SystemSetting).filter(SystemSetting.key == s["key"]).first()
            if not exists:
                db.add(SystemSetting(**s))
        db.commit()
        print(f"✔ System settings ensured ({len(SYSTEM_SETTINGS)})")

        # ---------------- Administrator Account ----------------
        admin_role = db.query(Role).filter(Role.name == "Administrator").first()
        admin = db.query(User).filter(User.email == settings.FIRST_ADMIN_EMAIL).first()
        if not admin:
            admin = User(
                first_name="System",
                last_name="Administrator",
                email=settings.FIRST_ADMIN_EMAIL,
                hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
                is_active=True,
                is_superuser=True,
                role_id=admin_role.id if admin_role else None,
                branch_id=branch.id,
            )
            db.add(admin)
            db.commit()
            print(f"✔ Administrator account created: {settings.FIRST_ADMIN_EMAIL} / {settings.FIRST_ADMIN_PASSWORD}")
        else:
            print(f"↷ Administrator account already exists: {settings.FIRST_ADMIN_EMAIL}")

        # ---------------- Amenities catalog (Phase 4) ----------------
        for a in AMENITIES:
            if not db.query(Amenity).filter(Amenity.name == a["name"]).first():
                db.add(Amenity(**a))
        db.commit()
        print(f"✔ Amenities catalog ensured ({len(AMENITIES)} items)")

        print("\n✅ Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
