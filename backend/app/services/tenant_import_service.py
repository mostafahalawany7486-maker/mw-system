"""
Bulk Tenant Import (per building) — extension on top of Phase 6 (Tenant
Management).

Two-step workflow, both scoped to a single building/Property at a time
(the simpler, more accurate option — see the design discussion this
followed): download a pre-filled .xlsx template listing every existing
unit of that building, fill in tenant details next to each unit, upload
it back. Each row only ever creates a plain Tenant record (Phase 6) —
linking a tenant to a specific unit's Rental Contract stays a deliberate
separate, manual step (Phase 7's existing contract-creation flow),
exactly as requested; this does not create RentalContract rows.

All-or-nothing on upload: every row is validated first with zero DB
writes, and only if every row passes does anything get created, in one
transaction (commit once at the end). Any unexpected failure mid-batch
rolls back the whole transaction — never a partial import.

Column order in the generated template is authoritative for reading it
back (matched by position, not by header text) since we control both
sides of that round trip. If someone hand-edits the header row order,
re-download a fresh template instead of fixing the old one.
"""
from io import BytesIO
from typing import Optional
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.repositories.property_repository import PropertyRepository
from app.repositories.tenant_repository import TenantRepository
from app.services.audit_service import AuditService

ENTITY_TYPE = "tenant"

# Fixed column order — both render_template() and parse_upload() must
# agree on this list. Columns marked (unit ref.) are pre-filled,
# read-only-by-convention (not DB-enforced — see module docstring);
# everything else is what the user fills in.
COLUMNS = [
    ("unit_number", "Unit Number", "رقم الوحدة", True),
    ("floor", "Floor", "الدور", True),
    ("unit_type", "Unit Type", "نوع الوحدة", True),
    ("tenant_type", "Tenant Type (individual/company)", "نوع المستأجر", False),
    ("first_name", "First Name", "الاسم الأول", False),
    ("last_name", "Last Name", "اسم العائلة", False),
    ("company_name", "Company Name", "اسم الشركة", False),
    ("national_id", "National ID", "الرقم المدني", False),
    ("passport_number", "Passport Number", "رقم الجواز", False),
    ("primary_phone", "Primary Phone", "الهاتف الأساسي", False),
    ("primary_email", "Primary Email", "البريد الإلكتروني", False),
    ("secondary_phone", "Secondary Phone", "هاتف إضافي", False),
    ("address", "Address", "العنوان", False),
    ("notes_summary", "Notes", "ملاحظات", False),
]
REQUIRED_HEADER_ROW = 4  # header text lives on this row; data starts on ROW+1
UNIT_TYPE_LABELS = {
    "apartment": "Apartment", "office": "Office", "shop": "Shop", "commercial_unit": "Commercial Unit",
    "parking": "Parking", "storage": "Storage",
}


class TenantImportService:
    def __init__(self, db: Session):
        self.db = db
        self.property_repo = PropertyRepository(db)
        self.tenant_repo = TenantRepository(db)
        self.audit = AuditService(db)

    # ---------------- Template generation ----------------
    def render_template(self, building_id: int) -> tuple[bytes, str]:
        building = self.property_repo.get(building_id)
        if not building:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

        unit_ids = self.property_repo.get_unit_ids(building_id)
        units = self.property_repo.get_many_with_parent(unit_ids) if unit_ids else []
        units.sort(key=lambda u: (u.floor_number or "", u.unit_number or ""))

        wb = Workbook()
        ws = wb.active
        ws.title = "Tenant Import"

        title_font = Font(bold=True, size=14)
        subtitle_font = Font(size=10, italic=True, color="666666")
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="0EA5E9")
        ref_fill = PatternFill("solid", fgColor="EFEFEF")
        required_font = Font(bold=True, color="B00020")
        thin = Side(style="thin", color="CCCCCC")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        ws.cell(row=1, column=1, value=f"Tenant Import — {building.title} ({building.property_code})").font = title_font
        ws.cell(row=2, column=1, value=(
            "Columns A–C are reference only (do not need to match anything — just showing you which unit each row is for). "
            "Fill in tenant details in the remaining columns, one row per tenant, then upload this file back. "
            "Tenant Type, and either (First+Last Name) or Company Name, are required per row. Phone and Email are optional."
        )).font = subtitle_font
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(COLUMNS))
        ws.row_dimensions[2].height = 30
        ws.cell(row=2, column=1).alignment = Alignment(wrap_text=True, vertical="top")

        for col_idx, (_key, label_en, label_ar, is_ref) in enumerate(COLUMNS, start=1):
            cell = ws.cell(row=REQUIRED_HEADER_ROW, column=col_idx, value=f"{label_en} / {label_ar}")
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            cell.border = border
            ws.column_dimensions[get_column_letter(col_idx)].width = 22 if not is_ref else 16
        ws.row_dimensions[REQUIRED_HEADER_ROW].height = 30
        ws.freeze_panes = f"A{REQUIRED_HEADER_ROW + 1}"

        # Tenant Type dropdown — column D (index 4) — makes the one
        # free-text field most prone to typos ("individual"/"company")
        # a pick-list instead.
        dv = DataValidation(type="list", formula1='"individual,company"', allow_blank=True, showDropDown=False)
        ws.add_data_validation(dv)
        dv.add(f"D{REQUIRED_HEADER_ROW + 1}:D{REQUIRED_HEADER_ROW + max(len(units), 20) + 1}")

        row = REQUIRED_HEADER_ROW + 1
        if units:
            for unit in units:
                ws.cell(row=row, column=1, value=unit.unit_number or "—").fill = ref_fill
                ws.cell(row=row, column=2, value=unit.floor_number or "—").fill = ref_fill
                ws.cell(row=row, column=3, value=UNIT_TYPE_LABELS.get(unit.property_type, unit.property_type)).fill = ref_fill
                for col_idx in range(1, len(COLUMNS) + 1):
                    ws.cell(row=row, column=col_idx).border = border
                row += 1
        else:
            # No child units recorded yet for this building — still a
            # usable template, just without pre-filled reference rows.
            for _ in range(15):
                for col_idx in range(1, len(COLUMNS) + 1):
                    ws.cell(row=row, column=col_idx).border = border
                row += 1

        buf = BytesIO()
        wb.save(buf)
        filename = f"tenant-import-{building.property_code}.xlsx"
        return buf.getvalue(), filename

    # ---------------- Upload / import ----------------
    def parse_and_import(self, building_id: int, file: UploadFile, actor_id: Optional[int]) -> dict:
        building = self.property_repo.get(building_id)
        if not building:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

        try:
            content = file.file.read()
            wb = load_workbook(BytesIO(content), data_only=True)
            ws = wb.active
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not read this file — please upload the .xlsx template downloaded from this page.")

        col_index = {key: i for i, (key, _en, _ar, _ref) in enumerate(COLUMNS)}
        rows_data = []
        errors: list[dict] = []

        existing_national_ids = set(
            self.db.execute(select(Tenant.national_id).where(Tenant.national_id.is_not(None), Tenant.deleted_at.is_(None))).scalars().all()
        )
        seen_national_ids_in_file: set[str] = set()

        excel_row_num = REQUIRED_HEADER_ROW + 1
        for raw_row in ws.iter_rows(min_row=REQUIRED_HEADER_ROW + 1, values_only=True):
            values = list(raw_row) + [None] * (len(COLUMNS) - len(raw_row))
            row_errors = self._validate_row(values, col_index, excel_row_num, existing_national_ids, seen_national_ids_in_file)
            if row_errors:
                errors.extend(row_errors)
            else:
                parsed = self._row_to_payload(values, col_index)
                if parsed is not None:  # None means the row was entirely blank — silently skipped, not an error
                    rows_data.append(parsed)
                    nid = parsed.get("national_id")
                    if nid:
                        seen_national_ids_in_file.add(nid)
            excel_row_num += 1

        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": f"{len(errors)} row(s) have errors — nothing was imported. Fix these and re-upload the whole file.",
                    "errors": errors,
                },
            )

        if not rows_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenant rows found in this file (every row was blank).")

        created: list[Tenant] = []
        try:
            for payload in rows_data:
                payload["tenant_code"] = self.tenant_repo.next_tenant_code()
                tenant = self.tenant_repo.create(payload, actor_id=actor_id)
                created.append(tenant)
            for tenant in created:
                self.audit.log_activity(
                    ENTITY_TYPE, tenant.id, "created",
                    f"Tenant {tenant.tenant_code} ({tenant.display_name}) created via bulk import for {building.title}",
                    actor_id,
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Import failed while saving — nothing was created. Please try again.")

        return {
            "created_count": len(created),
            "tenants": [{"id": t.id, "tenant_code": t.tenant_code, "display_name": t.display_name} for t in created],
        }

    # ---------------- Row-level validation (pure, no DB writes) ----------------
    def _validate_row(self, values: list, col_index: dict, excel_row_num: int, existing_ids: set, seen_in_file: set) -> list[dict]:
        def get(key):
            v = values[col_index[key]]
            return str(v).strip() if v is not None and str(v).strip() != "" else None

        # A fully blank row (nothing filled beyond the read-only unit
        # reference columns) is silently ignored, not an error — the
        # template pre-fills one row per unit whether or not the user
        # has a tenant for it yet.
        fillable_keys = [k for k, _e, _a, is_ref in COLUMNS if not is_ref]
        if all(get(k) is None for k in fillable_keys):
            return []

        errors = []
        tenant_type = get("tenant_type")
        if not tenant_type or tenant_type.lower() not in ("individual", "company"):
            errors.append({"row": excel_row_num, "message": "Tenant Type must be exactly 'individual' or 'company'."})
        elif tenant_type.lower() == "individual":
            if not get("first_name") or not get("last_name"):
                errors.append({"row": excel_row_num, "message": "First Name and Last Name are required for an individual tenant."})
        elif tenant_type.lower() == "company":
            if not get("company_name"):
                errors.append({"row": excel_row_num, "message": "Company Name is required for a company tenant."})

        email = get("primary_email")
        if email and "@" not in email:
            errors.append({"row": excel_row_num, "message": f"'{email}' does not look like a valid email address."})

        nid = get("national_id")
        if nid:
            if nid in existing_ids:
                errors.append({"row": excel_row_num, "message": f"National ID '{nid}' already belongs to an existing tenant in the system."})
            elif nid in seen_in_file:
                errors.append({"row": excel_row_num, "message": f"National ID '{nid}' appears more than once in this file."})

        return errors

    def _row_to_payload(self, values: list, col_index: dict) -> Optional[dict]:
        def get(key):
            v = values[col_index[key]]
            return str(v).strip() if v is not None and str(v).strip() != "" else None

        fillable_keys = [k for k, _e, _a, is_ref in COLUMNS if not is_ref]
        if all(get(k) is None for k in fillable_keys):
            return None

        tenant_type = get("tenant_type").lower()
        return {
            "tenant_type": tenant_type,
            "first_name": get("first_name"),
            "last_name": get("last_name"),
            "company_name": get("company_name"),
            "national_id": get("national_id"),
            "passport_number": get("passport_number"),
            "primary_phone": get("primary_phone"),
            "primary_email": get("primary_email"),
            "secondary_phone": get("secondary_phone"),
            "address": get("address"),
            "notes_summary": get("notes_summary"),
        }
