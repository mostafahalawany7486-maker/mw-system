"""
Global Search — Executive Dashboard Phase 3.

Searches Buildings/Units, Tenants, Owners, Contracts (rental +
master lease), Receipts, Expenses, Maintenance, and Payments in one
call, capped per category for speed (this is a live-as-you-type
search, not a report). Every match is a real row from a real query —
nothing pre-indexed or cached, which is fine at this data scale;
worth revisiting with a proper search index (e.g. Postgres full-text
or a dedicated search service) only if the table sizes ever justify
it.
"""
from typing import Optional
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

PER_CATEGORY_LIMIT = 6


class SearchService:
    def __init__(self, db: Session):
        self.db = db

    def search(self, q: str) -> dict:
        q = (q or "").strip()
        if len(q) < 2:
            return {"query": q, "results": {}}

        like = f"%{q}%"
        results: dict[str, list[dict]] = {}

        results["buildings_units"] = self._search_properties(like)
        results["tenants"] = self._search_tenants(like)
        results["owners"] = self._search_owners(like)
        results["contracts"] = self._search_contracts(like)
        results["receipts"] = self._search_receipts(like)
        results["expenses"] = self._search_expenses(like)
        results["maintenance"] = self._search_maintenance(like)
        results["payments"] = self._search_payments(like)

        results = {k: v for k, v in results.items() if v}
        return {"query": q, "results": results}

    def _search_properties(self, like: str) -> list[dict]:
        from app.models.property import Property
        rows = self.db.execute(
            select(Property).where(
                Property.deleted_at.is_(None),
                or_(Property.title.ilike(like), Property.property_code.ilike(like), Property.unit_number.ilike(like)),
            ).limit(PER_CATEGORY_LIMIT)
        ).scalars().all()
        return [
            {"id": p.id, "label": f"{p.property_code} — {p.title}" + (f" (Unit {p.unit_number})" if p.unit_number else ""), "link": f"/properties/{p.id}"}
            for p in rows
        ]

    def _search_tenants(self, like: str) -> list[dict]:
        from app.models.tenant import Tenant
        rows = self.db.execute(
            select(Tenant).where(
                Tenant.deleted_at.is_(None),
                or_(Tenant.tenant_code.ilike(like), Tenant.first_name.ilike(like), Tenant.last_name.ilike(like), Tenant.company_name.ilike(like), Tenant.primary_phone.ilike(like)),
            ).limit(PER_CATEGORY_LIMIT)
        ).scalars().all()
        return [{"id": t.id, "label": f"{t.tenant_code} — {t.display_name}", "link": f"/tenants/{t.id}"} for t in rows]

    def _search_owners(self, like: str) -> list[dict]:
        from app.models.owner import Owner
        rows = self.db.execute(
            select(Owner).where(
                Owner.deleted_at.is_(None),
                or_(Owner.owner_code.ilike(like), Owner.first_name.ilike(like), Owner.last_name.ilike(like), Owner.company_name.ilike(like)),
            ).limit(PER_CATEGORY_LIMIT)
        ).scalars().all()
        return [{"id": o.id, "label": f"{o.owner_code} — {o.display_name}", "link": f"/owners/{o.id}"} for o in rows]

    def _search_contracts(self, like: str) -> list[dict]:
        from app.models.rental import RentalContract
        from app.models.lease import LeaseAgreement
        rental_rows = self.db.execute(
            select(RentalContract).where(RentalContract.deleted_at.is_(None), RentalContract.contract_number.ilike(like)).limit(PER_CATEGORY_LIMIT)
        ).scalars().all()
        lease_rows = self.db.execute(
            select(LeaseAgreement).where(LeaseAgreement.deleted_at.is_(None), LeaseAgreement.contract_number.ilike(like)).limit(PER_CATEGORY_LIMIT)
        ).scalars().all()
        out = [{"id": c.id, "label": f"Contract {c.contract_number}", "link": f"/rentals/{c.id}"} for c in rental_rows]
        out += [{"id": c.id, "label": f"Master Lease {c.contract_number}", "link": f"/leases/{c.id}"} for c in lease_rows]
        return out[:PER_CATEGORY_LIMIT]

    def _search_receipts(self, like: str) -> list[dict]:
        from app.models.financial import Receipt
        rows = self.db.execute(
            select(Receipt).where(Receipt.deleted_at.is_(None), Receipt.receipt_number.ilike(like)).limit(PER_CATEGORY_LIMIT)
        ).scalars().all()
        return [{"id": r.id, "label": f"Receipt {r.receipt_number}", "link": f"/receipts/{r.id}/print"} for r in rows]

    def _search_expenses(self, like: str) -> list[dict]:
        from app.models.financial import Transaction, TransactionType
        rows = self.db.execute(
            select(Transaction).where(
                Transaction.deleted_at.is_(None), Transaction.transaction_type == TransactionType.EXPENSE,
                or_(Transaction.transaction_number.ilike(like), Transaction.category.ilike(like), Transaction.description.ilike(like)),
            ).limit(PER_CATEGORY_LIMIT)
        ).scalars().all()
        return [{"id": t.id, "label": f"{t.transaction_number} — {(t.category or t.description or 'Expense').replace('_', ' ')} ({t.amount})", "link": "/financial"} for t in rows]

    def _search_maintenance(self, like: str) -> list[dict]:
        from app.models.maintenance import MaintenanceRequest
        rows = self.db.execute(
            select(MaintenanceRequest).where(
                MaintenanceRequest.deleted_at.is_(None),
                or_(MaintenanceRequest.request_number.ilike(like), MaintenanceRequest.title.ilike(like)),
            ).limit(PER_CATEGORY_LIMIT)
        ).scalars().all()
        return [{"id": m.id, "label": f"{m.request_number} — {m.title}", "link": "/maintenance"} for m in rows]

    def _search_payments(self, like: str) -> list[dict]:
        from app.models.financial import Transaction, TransactionType
        rows = self.db.execute(
            select(Transaction).where(
                Transaction.deleted_at.is_(None),
                Transaction.transaction_type.in_([TransactionType.TENANT_PAYMENT, TransactionType.OWNER_PAYMENT]),
                or_(Transaction.transaction_number.ilike(like), Transaction.reference_number.ilike(like)),
            ).limit(PER_CATEGORY_LIMIT)
        ).scalars().all()
        return [{"id": t.id, "label": f"{t.transaction_number} — {t.amount}", "link": "/financial"} for t in rows]
