"""
Reset Business Data — deletes every Owner/Tenant/Property/Contract,
every Financial Account and the entire Accounting setup (Chart of
Accounts, Cost Centers, VAT Rates, Posting Rules), and everything
transactionally linked to any of them, so a database that already has
real test data typed into it by hand can be wiped clean before
entering the real company's data.

Scope updated per a confirmed follow-up: the very first version of
this script deliberately preserved Financial Accounts and the
Accounting setup — the person running it has since confirmed they want
those wiped too, to start entering their own real bank/cash accounts
and chart of accounts from scratch.

This is DIFFERENT from seed.py's "Fresh Start" change (which only
changed what a *fresh* `python seed.py` inserts going forward) — this
script acts on an EXISTING, already-running database that already has
records in it, typed in through the app itself.

═══════════════════════════════════════════════════════════════════
  THIS IS DESTRUCTIVE AND IRREVERSIBLE. BACK UP YOUR DATABASE FIRST.
═══════════════════════════════════════════════════════════════════
    pg_dump -U <user> -d <db_name> -F c -f backup_before_reset.dump
Restore with: pg_restore -U <user> -d <db_name> backup_before_reset.dump

Usage:
    python reset_business_data.py --yes
    python reset_business_data.py --yes --keep-accounts

Without --yes, this only prints what WOULD be deleted (dry run) and
exits — nothing is touched. Requires the literal --yes flag; there is
no interactive-only path, so this can never be triggered by
accidentally pressing Enter.

--keep-accounts: per a follow-up request, Financial Accounts (the
bank/cash accounts used for collecting rent, e.g. "ACC-000002 —
Motamad AL Watani") are left untouched instead of being wiped. Every
Transaction/Payment/Invoice pointing at them is still deleted as
normal — only the account rows themselves (and their balances, which
end up back at whatever they were before any test transactions) survive
the reset. Currencies were never touched by this script to begin with
(see PRESERVED below) — this flag only changes the Financial Accounts
part of that.

────────────────────────────────────────────────────────────────────
DELETION ORDER — verified, not guessed:
Every ForeignKey(...) declaration across every model in this table's
dependency graph (now 46 tables, up from 41 in the first version, to
cover Financial Accounts + Accounting) was extracted programmatically
and fed through a topological sort, so this list is guaranteed to
never delete a row that something else still points at (which would
otherwise fail with a foreign key violation partway through — see the
try/except below: if this ordering were ever wrong, the whole run
rolls back cleanly rather than leaving the database half-deleted).
Property and Floor are handled as a special 3-pass case outside the
main loop because they're mutually self-referential (a building "has"
floors via Floor.building_id, while a unit — also a Property row —
references its own Floor via floor_id): units are deleted first, then
Floor rows, then the remaining (building/standalone) Property rows.

PRESERVED (nothing here is touched):
  Users, Roles, Permissions, Branches, Countries, Cities, Currencies,
  Company Profile, System Settings, and the Amenities lookup catalog.
  Report Schedules are also left alone (a system config, not
  owner/tenant data) — its own optional, nullable link to an
  Attachment about to be deleted is cleared first (row kept). 
  Notifications are left alone (tied to Users, not business data).
────────────────────────────────────────────────────────────────────
"""
import sys

from app.core.database import SessionLocal
from app.models.system import ActivityLog, Attachment, AuditLog, Note
from app.models.financial_engine import DepositLedgerEntry
from app.models.accounting import ChartOfAccount, CostCenter, JournalEntry, JournalEntryLine, PostingRule, VatRate
from app.models.maintenance import (
    Contractor, MaintenanceLaborCost, MaintenanceMaterial, MaintenancePhoto, MaintenanceRequest, Technician,
)
from app.models.maintenance_contract import MaintenanceContract
from app.models.occupancy import OccupancyStatusHistory, UnitOccupancyOverride
from app.models.owner import Owner, OwnerAddress, OwnerBankAccount, OwnerContact, OwnerDocument
from app.models.owner_ledger import OwnerLedgerEntry
from app.models.payment import Payment, PaymentAllocation
from app.models.pending_rent_slip import PendingRentSlip
from app.models.property import Floor, Property, PropertyDocument, PropertyImage
from app.models.rent_cycle import RentCycle, RentCycleRecord
from app.models.rent_voucher import RentVoucher
from app.models.tenant import Tenant, TenantContact, TenantDocument, TenantEmergencyContact, TenantRating
from app.models.financial import FinancialAccount, Invoice, Receipt, Transaction
from app.models.lease import LeaseAgreement, LeasePaymentInstallment
from app.models.rental import RentalContract, RentalPaymentInstallment

# Verified order (see module docstring) — DO NOT reorder by hand without
# re-running the dependency check this was generated from.
DELETION_ORDER = [
    ("Activity Log", ActivityLog),
    ("Attachments", Attachment),
    ("Audit Log", AuditLog),
    ("Deposit Ledger Entries", DepositLedgerEntry),
    ("Journal Entry Lines", JournalEntryLine),
    ("Maintenance Labor Costs", MaintenanceLaborCost),
    ("Maintenance Materials", MaintenanceMaterial),
    ("Maintenance Photos", MaintenancePhoto),
    ("Notes", Note),
    ("Occupancy Status History", OccupancyStatusHistory),
    ("Owner Addresses", OwnerAddress),
    ("Owner Bank Accounts", OwnerBankAccount),
    ("Owner Contacts", OwnerContact),
    ("Owner Documents", OwnerDocument),
    ("Owner Ledger Entries", OwnerLedgerEntry),
    ("Payment Allocations", PaymentAllocation),
    ("Pending Rent Slips", PendingRentSlip),
    ("Posting Rules", PostingRule),
    ("Property Documents", PropertyDocument),
    ("Property Images", PropertyImage),
    ("Receipts", Receipt),
    ("Rent Cycle Records", RentCycleRecord),
    ("Rent Vouchers", RentVoucher),
    ("Tenant Contacts", TenantContact),
    ("Tenant Documents", TenantDocument),
    ("Tenant Emergency Contacts", TenantEmergencyContact),
    ("Tenant Ratings", TenantRating),
    ("Unit Occupancy Overrides", UnitOccupancyOverride),
    ("Journal Entries", JournalEntry),
    ("Maintenance Requests", MaintenanceRequest),
    ("Payments", Payment),
    ("Cost Centers", CostCenter),
    ("VAT Rates", VatRate),
    ("Invoices", Invoice),          # Invoice.paid_transaction_id -> Transaction: must go before Transaction
    ("Rent Cycles", RentCycle),
    ("Maintenance Contracts", MaintenanceContract),
    ("Technicians", Technician),    # Technician.contractor_id -> Contractor: must go before Contractor
    ("Transactions", Transaction),  # Transaction.rental_installment_id / lease_installment_id -> installments: must go before those
    ("Contractors", Contractor),
    # NOTE: "Financial Accounts" used to be a fixed step here — it's now
    # handled separately in main() (skipped entirely when --keep-accounts
    # is passed), so it's deliberately left OUT of this list.
    ("Lease Payment Installments", LeasePaymentInstallment),
    ("Rental Payment Installments", RentalPaymentInstallment),
    ("Chart of Accounts", ChartOfAccount),
    ("Lease Agreements", LeaseAgreement),
    ("Rental Contracts", RentalContract),
    # --- Property + Floor: special 3-pass case here (see delete_properties_respecting_hierarchy) ---
    ("Tenants", Tenant),
    # --- Owner: deleted last of all — Property.owner_id must already be gone ---
]


def unlink_preserved_records_referencing_deleted_data(db, dry_run: bool) -> None:
    """ReportSchedule (preserved — a system config, not business data)
    has its own optional, nullable link to an Attachment — found by
    checking every model in the codebase (not just the ones already in
    DELETION_ORDER) for a ForeignKey into any table this script
    touches. The row itself is kept; only the dangling link is
    cleared, run first so Attachments (deleted very early below) can
    never hit a foreign key violation because of it.
    """
    from app.models.reports import ReportSchedule

    print("Unlinking preserved records from data about to be deleted (rows kept, only the link is cleared):")
    if dry_run:
        rs = db.query(ReportSchedule).filter(ReportSchedule.last_export_attachment_id.isnot(None)).count()
        print(f"  {'Report Schedules -> last export file':<35} {rs:>6} would be unlinked")
    else:
        rs = db.query(ReportSchedule).filter(ReportSchedule.last_export_attachment_id.isnot(None)).update({"last_export_attachment_id": None}, synchronize_session=False)
        print(f"  {'Report Schedules -> last export file':<35} {rs:>6} unlinked")
    print()


def delete_properties_respecting_hierarchy(db, dry_run: bool) -> int:
    """Property is self-referential (a unit's parent_property_id points
    at its building) AND mutually referential with Floor (a building
    "has" floors via Floor.building_id, while a unit references its own
    Floor via floor_id) — deleted in three passes: units first, then
    Floor rows, then top-level properties (buildings/standalone), so
    nothing is ever deleted while something else still points at it.
    (CostCenter, which used to need its property_id link cleared here,
    is now deleted outright earlier in DELETION_ORDER instead, since
    it's in scope for deletion too — nothing left to unlink.)
    """
    if dry_run:
        unit_count = db.query(Property).filter(Property.parent_property_id.isnot(None)).count()
        floor_count = db.query(Floor).count()
        building_count = db.query(Property).count()
        print(f"  {'Properties (units)':<35} {unit_count:>6} row(s) would be deleted")
        print(f"  {'Floors':<35} {floor_count:>6} row(s) would be deleted")
        print(f"  {'Properties (buildings/standalone)':<35} {building_count:>6} row(s) would be deleted")
        return unit_count + floor_count + building_count

    units_deleted = db.query(Property).filter(Property.parent_property_id.isnot(None)).delete(synchronize_session=False)
    floors_deleted = db.query(Floor).delete(synchronize_session=False)
    buildings_deleted = db.query(Property).delete(synchronize_session=False)
    print(f"  {'Properties (units)':<35} {units_deleted:>6} row(s)")
    print(f"  {'Floors':<35} {floors_deleted:>6} row(s)")
    print(f"  {'Properties (buildings/standalone)':<35} {buildings_deleted:>6} row(s)")
    return units_deleted + floors_deleted + buildings_deleted


def main():
    dry_run = "--yes" not in sys.argv
    keep_accounts = "--keep-accounts" in sys.argv

    # Financial Accounts is inserted back into the deletion order right
    # where it always lived (after Contractors, before Lease Payment
    # Installments) unless --keep-accounts was passed — everything else
    # in DELETION_ORDER, and its position relative to those two steps,
    # is unchanged either way.
    deletion_order = list(DELETION_ORDER)
    if not keep_accounts:
        contractors_idx = deletion_order.index(("Contractors", Contractor))
        deletion_order.insert(contractors_idx + 1, ("Financial Accounts", FinancialAccount))

    db = SessionLocal()
    try:
        print("=" * 70)
        print("RESET BUSINESS DATA" + (" — DRY RUN (nothing will be deleted)" if dry_run else " — LIVE RUN"))
        if keep_accounts:
            print("(--keep-accounts: Financial Accounts / bank & cash accounts will be PRESERVED)")
        print("=" * 70)

        total = 0
        unlink_preserved_records_referencing_deleted_data(db, dry_run)

        rc_index = deletion_order.index(("Rental Contracts", RentalContract))
        pre_property_steps = deletion_order[:rc_index + 1]
        post_property_steps = deletion_order[rc_index + 1:]

        def run_step(label, model):
            nonlocal total
            count = db.query(model).count()
            total += count
            if dry_run:
                print(f"  {label:<35} {count:>6} row(s) would be deleted")
            else:
                deleted = db.query(model).delete(synchronize_session=False)
                print(f"  {label:<35} {deleted:>6} row(s) deleted")

        for label, model in pre_property_steps:
            run_step(label, model)

        # Property + Floor: their own special-cased pass, positioned here
        # because everything that references a Property row (maintenance,
        # ledger entries, contracts, images/documents, occupancy history,
        # payments, cost centers...) has already been deleted above, and
        # Owner (which Property references) hasn't been deleted yet.
        total += delete_properties_respecting_hierarchy(db, dry_run)

        for label, model in post_property_steps:
            run_step(label, model)

        # Owner is always last — nothing left should reference it by now.
        run_step("Owners", Owner)

        print("-" * 70)
        if dry_run:
            print(f"TOTAL: {total} row(s) would be deleted.")
            print("\nThis was a DRY RUN — nothing was touched. Back up your database, then")
            print("re-run with --yes to actually delete this data:")
            print("    python reset_business_data.py --yes" + (" --keep-accounts" if keep_accounts else ""))
        else:
            db.commit()
            print(f"DONE — {total} row(s) deleted.")
            print("\nPreserved (untouched): Users, Roles, Permissions, Branches, Countries,")
            print("Cities, Currencies, Company Profile, System Settings, and the Amenities")
            if keep_accounts:
                print("catalog, plus every Financial Account (bank/cash accounts) — kept as")
                print("requested via --keep-accounts, with their balances back at whatever they")
                print("were before any test transactions.")
                print("\nYou can now start entering your real Owners, Tenants, and Properties,")
                print("and collect payments against your existing accounts right away.")
            else:
                print("catalog.")
                print("\nEvery account balance in the system is now genuinely zero — Financial")
                print("Accounts and the Chart of Accounts were deleted too. Create your real")
                print("bank/cash accounts from Financial -> Add Account, and (optionally) your")
                print("real Chart of Accounts from Accounting, before recording anything.")
                print("\nYou can now start entering your real Owners, Tenants, and Properties.")
    except Exception as exc:
        db.rollback()
        print(f"\nFAILED — nothing was deleted, the whole run was rolled back. Error: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
