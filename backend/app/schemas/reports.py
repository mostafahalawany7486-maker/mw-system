"""
Phase 11 — Reports. Everything here is computed live from Phases 1–10's
existing data; there are no new persisted tables. This is deliberately
distinct from Phase 10's accounting-grade financial statements (which
require posted journal entries): these are fast, operational business
reports computed directly from source transactional data (Transactions,
Rental/Lease installments, Maintenance costs), useful even if the GL
isn't fully configured yet.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator


class NamedAmount(BaseModel):
    label: str
    total_amount: Decimal
    count: int = 0


class MonthlyAmount(BaseModel):
    month: str  # YYYY-MM
    total_amount: Decimal


class PropertyAmount(BaseModel):
    property_id: int
    property_code: str
    property_title: str
    total_amount: Decimal


# ---------------- Financial Reports ----------------
class FinancialReportOut(BaseModel):
    date_from: date
    date_to: date
    total_income: Decimal
    total_expense: Decimal
    net_cash_flow: Decimal
    total_outstanding_tenant: Decimal
    total_outstanding_owner: Decimal
    collection_rate_percentage: Decimal
    transactions_by_type: List[NamedAmount]


# ---------------- Tenant Reports ----------------
class TenantOutstandingItem(BaseModel):
    tenant_id: int
    display_name: str
    outstanding_amount: Decimal


class TenantPaymentItem(BaseModel):
    tenant_id: int
    display_name: str
    total_paid: Decimal
    payment_count: int


class TenantReportOut(BaseModel):
    total_tenants: int
    individual_tenants: int
    company_tenants: int
    blacklisted_tenants: int
    average_rating: Optional[Decimal] = None
    contracts_expiring_soon: int
    top_tenants_by_payment: List[TenantPaymentItem]
    outstanding_tenants: List[TenantOutstandingItem]


# ---------------- Owner Reports ----------------
class OwnerPropertyCountItem(BaseModel):
    owner_id: int
    display_name: str
    property_count: int


class OwnerOutstandingItem(BaseModel):
    owner_id: int
    display_name: str
    outstanding_amount: Decimal


class OwnerReportOut(BaseModel):
    total_owners: int
    individual_owners: int
    company_owners: int
    total_paid_to_owners: Decimal
    top_owners_by_properties: List[OwnerPropertyCountItem]
    outstanding_owners: List[OwnerOutstandingItem]


# ---------------- Property Reports ----------------
class PropertyTypeCount(BaseModel):
    property_type: str
    count: int


class PropertyStatusCount(BaseModel):
    availability_status: str
    count: int


class PropertyReportOut(BaseModel):
    total_properties: int
    by_type: List[PropertyTypeCount]
    by_availability: List[PropertyStatusCount]
    top_properties_by_revenue: List[PropertyAmount]


# ---------------- Vacancy Reports ----------------
class VacantPropertyItem(BaseModel):
    property_id: int
    property_code: str
    title: str
    property_type: str
    days_vacant: int


class VacancyReportOut(BaseModel):
    as_of_date: date
    total_properties: int
    vacant_count: int
    leased_count: int
    other_count: int
    vacancy_rate_percentage: Decimal
    vacant_properties: List[VacantPropertyItem]


# ---------------- Occupancy Reports ----------------
class OccupancyByTypeItem(BaseModel):
    property_type: str
    total: int
    occupied: int
    occupancy_rate_percentage: Decimal


class OccupancyTrendPoint(BaseModel):
    month: str
    occupancy_rate_percentage: Decimal


class OccupancyReportOut(BaseModel):
    as_of_date: date
    overall_occupancy_rate_percentage: Decimal
    by_property_type: List[OccupancyByTypeItem]
    trend: List[OccupancyTrendPoint]


# ---------------- Unit Reports (Phase 2.0) ----------------
# Covers "Building Units Report" / "Villa Units Report" (pass property_id
# to scope to that building/villa's children), "Unit Status Report" (the
# by_status breakdown), and "Unit Availability Report" (filter
# availability_status='available', or just read vacant_count) from one
# endpoint rather than four near-identical ones — same reasoning as the
# existing Vacancy/Occupancy reports reusing one Property table query.
class UnitReportItem(BaseModel):
    property_id: int
    property_code: str
    title: str
    property_type: str
    availability_status: str
    building_title: Optional[str] = None
    floor_label: Optional[str] = None
    unit_number: Optional[str] = None
    rent_price: Optional[Decimal] = None


class UnitReportOut(BaseModel):
    as_of_date: date
    scoped_to_property_id: Optional[int] = None
    scoped_to_property_title: Optional[str] = None
    total_units: int
    vacant_count: int
    occupied_count: int
    reserved_count: int
    under_maintenance_count: int
    by_status: List[PropertyStatusCount]
    by_type: List[PropertyTypeCount]
    units: List[UnitReportItem]


# ---------------- Income Reports ----------------
class IncomeReportOut(BaseModel):
    date_from: date
    date_to: date
    total_income: Decimal
    by_category: List[NamedAmount]
    by_property: List[PropertyAmount]
    trend: List[MonthlyAmount]


# ---------------- Expense Reports ----------------
class ExpenseReportOut(BaseModel):
    date_from: date
    date_to: date
    total_expense: Decimal
    total_maintenance_cost: Decimal
    by_category: List[NamedAmount]
    by_property: List[PropertyAmount]
    trend: List[MonthlyAmount]


# ---------------- Profit Reports ----------------
class ProfitByPropertyItem(BaseModel):
    property_id: int
    property_code: str
    property_title: str
    income: Decimal
    expense: Decimal
    profit: Decimal


class ProfitTrendPoint(BaseModel):
    month: str
    income: Decimal
    expense: Decimal
    profit: Decimal


class ProfitReportOut(BaseModel):
    date_from: date
    date_to: date
    total_income: Decimal
    total_expense: Decimal
    net_profit: Decimal
    profit_margin_percentage: Decimal
    by_property: List[ProfitByPropertyItem]
    trend: List[ProfitTrendPoint]


# ---------------- Dashboard Analytics ----------------
class DashboardKPIs(BaseModel):
    total_properties: int
    occupied_properties: int
    vacancy_rate_percentage: Decimal
    total_tenants: int
    total_owners: int
    active_rental_contracts: int
    active_lease_agreements: int
    open_maintenance_requests: int
    total_income_this_month: Decimal
    total_expense_this_month: Decimal
    net_profit_this_month: Decimal
    total_outstanding_tenant: Decimal
    total_outstanding_owner: Decimal
    # Enterprise Dashboard extension (additive — all existing fields above are unchanged)
    total_units: int = 0
    occupied_units: int = 0
    vacant_units: int = 0
    occupancy_rate_percentage: Decimal = Decimal("0")
    contracts_expiring_soon: int = 0


class DashboardAnalyticsOut(BaseModel):
    generated_at: date
    kpis: DashboardKPIs
    monthly_trend: List[ProfitTrendPoint]
    top_properties_by_revenue: List[PropertyAmount]
    # Enterprise Dashboard extension (additive)
    properties_by_type: List[PropertyTypeCount] = []
    properties_by_availability: List[PropertyStatusCount] = []
    occupancy_by_type: List[OccupancyByTypeItem] = []
    cash_flow_by_type: List[NamedAmount] = []


# ---------------- Property Profit Center: single-property reports ----------------
class PropertyProfitAndLossOut(BaseModel):
    property_id: int
    property_code: str
    property_title: str
    date_from: date
    date_to: date
    total_income: Decimal
    total_expense: Decimal
    net_profit: Decimal
    profit_margin_percentage: Decimal
    income_by_category: List[NamedAmount]
    expense_by_category: List[NamedAmount]
    trend: List[ProfitTrendPoint]


class PropertyDashboardKPIs(BaseModel):
    availability_status: str
    active_leases_count: int
    open_maintenance_requests: int
    total_income_this_month: Decimal
    total_expense_this_month: Decimal
    net_profit_this_month: Decimal
    total_income_ytd: Decimal
    total_expense_ytd: Decimal
    net_profit_ytd: Decimal
    total_outstanding_tenant: Decimal


class PropertyFinancialDashboardOut(BaseModel):
    property_id: int
    property_code: str
    property_title: str
    generated_at: date
    kpis: PropertyDashboardKPIs
    monthly_trend: List[ProfitTrendPoint]


# ---------------- Enterprise Reporting extension: Lease/Maintenance/Collections/Outstanding/Expiration ----------------
class ContractStatusCount(BaseModel):
    status: str
    count: int
    total_rent: Decimal


class RentalContractSummaryItem(BaseModel):
    id: int
    contract_number: str
    tenant_display_name: Optional[str] = None
    property_id: int
    property_title: Optional[str] = None
    unit_number: Optional[str] = None
    start_date: date
    end_date: date
    rent_amount: Decimal
    contract_status: str


class LeaseAgreementSummaryItem(BaseModel):
    id: int
    contract_number: str
    owner_display_name: Optional[str] = None
    property_id: Optional[int] = None
    property_title: Optional[str] = None
    unit_number: Optional[str] = None
    start_date: date
    end_date: date
    rent_amount: Decimal
    contract_status: str


class LeaseReportOut(BaseModel):
    rental_contracts_by_status: List[ContractStatusCount]
    lease_agreements_by_status: List[ContractStatusCount]
    rental_contracts: List[RentalContractSummaryItem]
    lease_agreements: List[LeaseAgreementSummaryItem]


class MaintenanceStatusCount(BaseModel):
    status: str
    count: int


class MaintenancePriorityCount(BaseModel):
    priority: str
    count: int


class MaintenanceCategoryCount(BaseModel):
    category: str
    count: int


class MaintenanceContractorCount(BaseModel):
    contractor_id: int
    contractor_name: str
    request_count: int


class MaintenanceRequestSummaryItem(BaseModel):
    id: int
    request_number: str
    title: str
    property_title: Optional[str] = None
    category: Optional[str] = None
    priority: str
    maintenance_status: str
    reported_date: date
    completed_date: Optional[date] = None
    total_actual_cost: Decimal
    contractor_name: Optional[str] = None


class MaintenanceReportOut(BaseModel):
    date_from: date
    date_to: date
    total_requests: int
    by_status: List[MaintenanceStatusCount]
    by_priority: List[MaintenancePriorityCount]
    by_category: List[MaintenanceCategoryCount]
    by_contractor: List[MaintenanceContractorCount]
    total_cost: Decimal
    average_resolution_days: Optional[Decimal] = None
    requests: List[MaintenanceRequestSummaryItem]


class CollectionsMonthlyPoint(BaseModel):
    month: str
    due: Decimal
    collected: Decimal
    collection_rate_percentage: Decimal


class CollectionsByPropertyItem(BaseModel):
    property_id: int
    property_code: str
    property_title: str
    due: Decimal
    collected: Decimal
    collection_rate_percentage: Decimal


class CollectionsReportOut(BaseModel):
    date_from: date
    date_to: date
    total_due: Decimal
    total_collected: Decimal
    collection_rate_percentage: Decimal
    monthly_trend: List[CollectionsMonthlyPoint]
    by_property: List[CollectionsByPropertyItem]


class AgingBuckets(BaseModel):
    current: Decimal
    days_1_30: Decimal
    days_31_60: Decimal
    days_61_90: Decimal
    days_90_plus: Decimal


class OutstandingReportOut(BaseModel):
    as_of_date: date
    tenant_outstanding_total: Decimal
    tenant_aging: AgingBuckets
    tenant_outstanding_list: List[TenantOutstandingItem]
    owner_outstanding_total: Decimal
    owner_aging: AgingBuckets
    owner_outstanding_list: List[OwnerOutstandingItem]


class ExpiringRentalContractItem(BaseModel):
    id: int
    contract_number: str
    tenant_display_name: Optional[str] = None
    property_id: int
    property_title: Optional[str] = None
    unit_number: Optional[str] = None
    end_date: date
    days_remaining: int
    rent_amount: Decimal


class ExpiringLeaseAgreementItem(BaseModel):
    id: int
    contract_number: str
    owner_display_name: Optional[str] = None
    property_id: Optional[int] = None
    property_title: Optional[str] = None
    unit_number: Optional[str] = None
    end_date: date
    days_remaining: int
    rent_amount: Decimal


class ContractExpirationReportOut(BaseModel):
    as_of_date: date
    window_days: int
    total_expiring: int
    expiring_rental_contracts: List[ExpiringRentalContractItem]
    expiring_lease_agreements: List[ExpiringLeaseAgreementItem]


# ---------------- Export Scheduling ----------------
VALID_REPORT_TYPES = {"property", "owner", "tenant", "lease", "occupancy", "financial", "maintenance", "collections", "outstanding", "contract_expiration", "owner_balance", "tenant_ledger", "security_deposit", "renewed_contracts", "top_tenants", "repeated_late_payers"}
VALID_EXPORT_FORMATS = {"pdf", "excel"}
VALID_FREQUENCIES = {"daily", "weekly", "monthly"}


class ReportScheduleCreate(BaseModel):
    name: str
    report_type: str
    export_format: str = "pdf"
    frequency: str = "monthly"
    filters: Optional[dict] = None
    is_active: bool = True

    @field_validator("report_type")
    @classmethod
    def validate_report_type(cls, v: str) -> str:
        if v not in VALID_REPORT_TYPES:
            raise ValueError(f"report_type must be one of {sorted(VALID_REPORT_TYPES)}")
        return v

    @field_validator("export_format")
    @classmethod
    def validate_export_format(cls, v: str) -> str:
        if v not in VALID_EXPORT_FORMATS:
            raise ValueError(f"export_format must be one of {sorted(VALID_EXPORT_FORMATS)}")
        return v

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        if v not in VALID_FREQUENCIES:
            raise ValueError(f"frequency must be one of {sorted(VALID_FREQUENCIES)}")
        return v


class ReportScheduleUpdate(BaseModel):
    name: Optional[str] = None
    export_format: Optional[str] = None
    frequency: Optional[str] = None
    filters: Optional[dict] = None
    is_active: Optional[bool] = None


class ReportScheduleOut(BaseModel):
    id: int
    uuid: str
    name: str
    report_type: str
    export_format: str
    frequency: str
    filters: Optional[dict] = None
    is_active: bool
    next_run_at: datetime
    last_run_at: Optional[datetime] = None
    last_export_file_url: Optional[str] = None
    last_export_file_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------- Rent Billing Engine reports ----------------
class InvoiceRegisterItem(BaseModel):
    id: int
    invoice_number: str
    tenant_display_name: Optional[str] = None
    property_title: Optional[str] = None
    unit_number: Optional[str] = None
    issue_date: date
    due_date: date
    amount: Decimal
    amount_paid: Decimal
    invoice_status: str


class InvoiceRegisterOut(BaseModel):
    date_from: date
    date_to: date
    total_invoices: int
    total_amount: Decimal
    total_outstanding: Decimal
    invoices: List[InvoiceRegisterItem] = []


class PaymentRegisterItem(BaseModel):
    id: int
    transaction_number: str
    tenant_id: Optional[int] = None
    amount: Decimal
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None
    transaction_date: date


class PaymentRegisterOut(BaseModel):
    date_from: date
    date_to: date
    total_payments: int
    total_collected: Decimal
    payments: List[PaymentRegisterItem] = []


class OverdueInvoiceItem(BaseModel):
    id: int
    invoice_number: str
    tenant_display_name: Optional[str] = None
    property_title: Optional[str] = None
    unit_number: Optional[str] = None
    due_date: date
    days_overdue: int
    outstanding_amount: Decimal


class OverdueInvoiceReportOut(BaseModel):
    as_of_date: date
    total_overdue: int
    total_overdue_amount: Decimal
    invoices: List[OverdueInvoiceItem] = []
