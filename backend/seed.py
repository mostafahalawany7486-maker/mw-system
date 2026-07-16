"""
Seed data for Phase 1. Run with: python seed.py
Idempotent: safe to run multiple times (checks for existing records first).
"""
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.core.config import settings
from app.models.user import User, Role, Permission
from app.models.organization import Country, City, Currency, CompanyProfile, Branch, SystemSetting
from app.models.owner import Owner, OwnerAddress, OwnerBankAccount, OwnerContact

# ---------------------------------------------------------------------------
# Permission catalog. Codes follow 'module.action'. Every module built in
# this and future phases should register its permissions here.
# ---------------------------------------------------------------------------
MODULES = [
    "users", "roles", "branches", "countries", "cities", "currencies",
    "company", "settings", "audit", "owners",
]
ACTIONS = ["view", "create", "edit", "delete"]

SYSTEM_ROLES = [
    {"name": "Administrator", "description": "Full system access", "is_system_role": True, "all_permissions": True},
    {"name": "Branch Manager", "description": "Manages a single branch's operations", "is_system_role": True,
     "permission_codes": [
         "users.view", "branches.view", "countries.view", "cities.view",
         "currencies.view", "company.view", "settings.view",
         "owners.view", "owners.create", "owners.edit",
     ]},
    {"name": "Staff", "description": "Standard operational staff member", "is_system_role": True,
     "permission_codes": ["branches.view", "countries.view", "cities.view", "currencies.view", "company.view", "owners.view"]},
]

COUNTRIES = [
    {"name": "United States", "iso_code2": "US", "iso_code3": "USA", "phone_code": "+1"},
    {"name": "United Arab Emirates", "iso_code2": "AE", "iso_code3": "ARE", "phone_code": "+971"},
    {"name": "United Kingdom", "iso_code2": "GB", "iso_code3": "GBR", "phone_code": "+44"},
]

CITIES = {
    "United States": ["New York", "Los Angeles", "Chicago"],
    "United Arab Emirates": ["Dubai", "Abu Dhabi"],
    "United Kingdom": ["London", "Manchester"],
}

CURRENCIES = [
    {"code": "USD", "name": "US Dollar", "symbol": "$", "is_base_currency": True, "exchange_rate_to_base": 1.0},
    {"code": "AED", "name": "UAE Dirham", "symbol": "د.إ", "is_base_currency": False, "exchange_rate_to_base": 3.6725},
    {"code": "GBP", "name": "British Pound", "symbol": "£", "is_base_currency": False, "exchange_rate_to_base": 0.79},
]

SYSTEM_SETTINGS = [
    {"key": "date_format", "value": "YYYY-MM-DD", "value_type": "string", "category": "general", "description": "Default date display format"},
    {"key": "theme_default", "value": "light", "value_type": "string", "category": "appearance", "description": "Default UI theme for new users"},
    {"key": "session_timeout_minutes", "value": "30", "value_type": "number", "category": "security", "description": "Idle session timeout"},
    {"key": "company_name_display", "value": "PMS Leasing Co.", "value_type": "string", "category": "general", "description": "Fallback display name before company profile is set"},
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

        base_currency = db.query(Currency).filter(Currency.is_base_currency.is_(True)).first()
        us = country_by_name["United States"]
        ny = db.query(City).filter(City.name == "New York").first()

        # ---------------- Company Profile ----------------
        profile = db.query(CompanyProfile).first()
        if not profile:
            profile = CompanyProfile(
                legal_name="PMS Leasing Company LLC",
                trade_name="PMS Leasing",
                email="info@pms-demo.com",
                phone="+1-555-0100",
                address_line1="123 Main Street",
                city_id=ny.id if ny else None,
                country_id=us.id,
                base_currency_id=base_currency.id if base_currency else None,
                default_language="en",
            )
            db.add(profile)
        db.commit()
        print("✔ Company profile ensured")

        # ---------------- Head Office Branch ----------------
        branch = db.query(Branch).filter(Branch.code == "HO").first()
        if not branch:
            branch = Branch(
                name="Head Office", code="HO", email="headoffice@pms-demo.com",
                city_id=ny.id if ny else None, country_id=us.id, is_head_office=True,
            )
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

        # ---------------- Sample test users (for QA/testing) ----------------
        manager_role = db.query(Role).filter(Role.name == "Branch Manager").first()
        staff_role = db.query(Role).filter(Role.name == "Staff").first()
        sample_users = [
            {"first_name": "Maria", "last_name": "Manager", "email": "maria.manager@pms-demo.com", "role_id": manager_role.id if manager_role else None},
            {"first_name": "Sam", "last_name": "Staff", "email": "sam.staff@pms-demo.com", "role_id": staff_role.id if staff_role else None},
        ]
        for u in sample_users:
            if not db.query(User).filter(User.email == u["email"]).first():
                db.add(User(
                    first_name=u["first_name"], last_name=u["last_name"], email=u["email"],
                    hashed_password=hash_password("ChangeMe!123"), is_active=True, is_superuser=False,
                    role_id=u["role_id"], branch_id=branch.id,
                ))
        db.commit()
        print("✔ Sample QA users ensured (maria.manager@pms-demo.com / sam.staff@pms-demo.com, password: ChangeMe!123)")

        # ---------------- Sample Property Owners (Phase 2) ----------------
        us_currency = db.query(Currency).filter(Currency.code == "USD").first()
        la = db.query(City).filter(City.name == "Los Angeles").first()
        dubai = db.query(City).filter(City.name == "Dubai").first()
        uae = db.query(Country).filter(Country.iso_code2 == "AE").first()

        if db.query(Owner).count() == 0:
            individual_owner = Owner(
                owner_code="OWN-000001",
                owner_type="individual",
                first_name="Robert",
                last_name="Chen",
                national_id="A1234567",
                nationality_id=us.id,
                primary_email="robert.chen" + chr(64) + "ownerdemo.com",
                primary_phone="+1-555-0199",
                branch_id=branch.id,
            )
            db.add(individual_owner)
            db.flush()
            db.add(OwnerAddress(owner_id=individual_owner.id, address_type="mailing", line1="456 Sunset Blvd", city_id=la.id if la else None, country_id=us.id, is_primary=True))
            db.add(OwnerBankAccount(owner_id=individual_owner.id, bank_name="First National Bank", account_holder_name="Robert Chen", account_number="000123456789", currency_id=us_currency.id if us_currency else None, is_primary=True))

            company_owner = Owner(
                owner_code="OWN-000002",
                owner_type="company",
                company_name="Skyline Holdings LLC",
                registration_number="REG-88213",
                tax_number="TAX-99021",
                contact_person_name="Amira Al-Farsi",
                contact_person_title="Asset Manager",
                primary_email="contact" + chr(64) + "skylineholdings.com",
                primary_phone="+971-4-555-0100",
                branch_id=branch.id,
            )
            db.add(company_owner)
            db.flush()
            db.add(OwnerAddress(owner_id=company_owner.id, address_type="mailing", line1="Office 1204, Business Bay Tower", city_id=dubai.id if dubai else None, country_id=uae.id if uae else None, is_primary=True))
            db.add(OwnerContact(owner_id=company_owner.id, full_name="Amira Al-Farsi", designation="Asset Manager", email="amira" + chr(64) + "skylineholdings.com", phone="+971-4-555-0101", is_primary=True))

            db.commit()
            print("✔ Sample property owners ensured (OWN-000001 Robert Chen, OWN-000002 Skyline Holdings LLC)")
        else:
            print("↷ Property owners already exist, skipping sample owner seed")

        print("\n✅ Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
