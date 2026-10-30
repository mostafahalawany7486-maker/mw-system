"""
Data Integrity Audit — read-only diagnostic report.

Requested as a follow-up to the property-data-separation review: "find
tenants without apartments, contracts without buildings, duplicate
tenant records, duplicate apartment records... generate a report of
problems before fixing. Do not delete records automatically."

Every check here is a pure SELECT — nothing in this file writes,
updates, or deletes a single row. It exists to surface problems for a
human to review and fix (via the normal edit/merge/delete screens),
never to fix them itself, exactly as specified.
"""
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from app.models.tenant import Tenant
from app.models.rental import RentalContract, RentalContractStatus
from app.models.property import Property
from app.models.base import RecordStatus

MAX_SAMPLES = 50  # cap how many example rows each finding returns, so a
                   # badly-out-of-sync system doesn't return a multi-MB report


class DataAuditService:
    def __init__(self, db: Session):
        self.db = db

    def run_audit(self) -> dict:
        return {
            "tenants_without_contracts": self._tenants_without_contracts(),
            "duplicate_tenant_national_ids": self._duplicate_tenant_national_ids(),
            "duplicate_units_same_floor": self._duplicate_units_same_floor(),
            "multiple_active_contracts_per_property": self._multiple_active_contracts_per_property(),
            "contracts_with_invalid_dates": self._contracts_with_invalid_dates(),
            "contracts_on_archived_properties": self._contracts_on_archived_properties(),
        }

    # ---------------- Individual checks ----------------
    def _tenants_without_contracts(self) -> dict:
        """Tenants (Phase 6) who have never had a single RentalContract
        (any status, including expired/terminated) — i.e. registered but
        never actually linked to a unit. Not necessarily wrong (could be
        a prospective tenant mid-onboarding), but worth a human look."""
        subq = select(RentalContract.tenant_id).distinct()
        stmt = (
            select(Tenant)
            .where(Tenant.deleted_at.is_(None), Tenant.id.not_in(subq))
            .order_by(Tenant.id.desc())
            .limit(MAX_SAMPLES)
        )
        rows = self.db.execute(stmt).scalars().all()
        total = self.db.execute(
            select(func.count()).select_from(Tenant).where(Tenant.deleted_at.is_(None), Tenant.id.not_in(subq))
        ).scalar_one()
        return {
            "count": total,
            "description": "Tenants with zero rental contracts of any status — never actually linked to a unit.",
            "samples": [{"id": t.id, "tenant_code": t.tenant_code, "display_name": t.display_name, "created_at": t.created_at.isoformat()} for t in rows],
        }

    def _duplicate_tenant_national_ids(self) -> dict:
        """Two or more active Tenant rows sharing the same non-null
        national_id — likely the same person registered twice. Single-
        create already blocks this going forward (see
        TenantService.create_tenant); this check is for data that
        predates that guard, or came in through another path."""
        dup_ids_stmt = (
            select(Tenant.national_id)
            .where(Tenant.national_id.is_not(None), Tenant.deleted_at.is_(None))
            .group_by(Tenant.national_id)
            .having(func.count(Tenant.id) > 1)
        )
        dup_ids = list(self.db.execute(dup_ids_stmt).scalars().all())
        samples = []
        if dup_ids:
            rows = self.db.execute(
                select(Tenant).where(Tenant.national_id.in_(dup_ids[:MAX_SAMPLES]), Tenant.deleted_at.is_(None)).order_by(Tenant.national_id)
            ).scalars().all()
            samples = [{"id": t.id, "tenant_code": t.tenant_code, "display_name": t.display_name, "national_id": t.national_id} for t in rows]
        return {
            "count": len(dup_ids),
            "description": "Distinct National ID values shared by 2+ tenant records (samples list every matching tenant row, not just one per group).",
            "samples": samples,
        }

    def _duplicate_units_same_floor(self) -> dict:
        """Two or more units under the same building AND floor sharing
        the same unit_number — a data-entry duplicate (Unit 301 entered
        twice), not two different real units. Deliberately scoped to
        (parent_property_id, floor_id) — the same unit_number in a
        DIFFERENT building/floor is completely normal and not flagged."""
        stmt = (
            select(Property.parent_property_id, Property.floor_id, Property.unit_number, func.count(Property.id).label("cnt"))
            .where(Property.deleted_at.is_(None), Property.unit_number.is_not(None), Property.parent_property_id.is_not(None))
            .group_by(Property.parent_property_id, Property.floor_id, Property.unit_number)
            .having(func.count(Property.id) > 1)
            .limit(MAX_SAMPLES)
        )
        groups = self.db.execute(stmt).all()
        samples = []
        for building_id, floor_id, unit_number, cnt in groups:
            unit_rows = self.db.execute(
                select(Property).where(
                    Property.parent_property_id == building_id, Property.floor_id == floor_id,
                    Property.unit_number == unit_number, Property.deleted_at.is_(None),
                )
            ).scalars().all()
            samples.append({
                "building_id": building_id, "floor_id": floor_id, "unit_number": unit_number,
                "count": cnt, "property_ids": [u.id for u in unit_rows],
            })
        return {
            "count": len(groups),
            "description": "Groups of 2+ units with the identical Unit Number under the same building AND floor.",
            "samples": samples,
        }

    def _multiple_active_contracts_per_property(self) -> dict:
        """Defensive check: RentalService.activate_contract() has blocked
        a second active contract on the same unit since the Occupancy
        Engine (Phase 18) — but that only guards contracts activated
        AFTER that check existed. This catches any pre-existing data
        that slipped in before the guard was added, or via a path that
        bypasses the service layer (e.g. a direct DB migration/import)."""
        stmt = (
            select(RentalContract.property_id, func.count(RentalContract.id).label("cnt"))
            .where(RentalContract.contract_status == RentalContractStatus.ACTIVE, RentalContract.deleted_at.is_(None))
            .group_by(RentalContract.property_id)
            .having(func.count(RentalContract.id) > 1)
            .limit(MAX_SAMPLES)
        )
        groups = self.db.execute(stmt).all()
        samples = []
        for property_id, cnt in groups:
            contracts = self.db.execute(
                select(RentalContract).where(RentalContract.property_id == property_id, RentalContract.contract_status == RentalContractStatus.ACTIVE, RentalContract.deleted_at.is_(None))
            ).scalars().all()
            samples.append({
                "property_id": property_id, "count": cnt,
                "contract_ids": [{"id": c.id, "contract_number": c.contract_number, "tenant_id": c.tenant_id} for c in contracts],
            })
        return {
            "count": len(groups),
            "description": "Properties with 2+ contracts simultaneously marked Active — should be structurally impossible going forward; any result here predates that guard.",
            "samples": samples,
        }

    def _contracts_with_invalid_dates(self) -> dict:
        stmt = (
            select(RentalContract)
            .where(RentalContract.deleted_at.is_(None), RentalContract.end_date <= RentalContract.start_date)
            .order_by(RentalContract.id.desc())
            .limit(MAX_SAMPLES)
        )
        rows = self.db.execute(stmt).scalars().all()
        total = self.db.execute(
            select(func.count()).select_from(RentalContract).where(RentalContract.deleted_at.is_(None), RentalContract.end_date <= RentalContract.start_date)
        ).scalar_one()
        return {
            "count": total,
            "description": "Contracts where end_date is not after start_date — should be blocked by validation on create/update; flags anything that predates that check.",
            "samples": [{"id": c.id, "contract_number": c.contract_number, "start_date": c.start_date.isoformat(), "end_date": c.end_date.isoformat()} for c in rows],
        }

    def _contracts_on_archived_properties(self) -> dict:
        """Not necessarily an error (a property can be legitimately
        archived after its contracts end), but worth surfacing: an
        ACTIVE contract on an archived property is worth a second look."""
        stmt = (
            select(RentalContract)
            .join(Property, Property.id == RentalContract.property_id)
            .options(selectinload(RentalContract.property_ref))
            .where(
                RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE,
                Property.status == RecordStatus.ARCHIVED,
            )
            .limit(MAX_SAMPLES)
        )
        rows = self.db.execute(stmt).scalars().all()
        return {
            "count": len(rows),
            "description": "Active contracts whose property has been archived — usually means the property was archived by mistake while still occupied.",
            "samples": [{"id": c.id, "contract_number": c.contract_number, "property_id": c.property_id, "property_title": c.property_ref.title if c.property_ref else None} for c in rows],
        }
