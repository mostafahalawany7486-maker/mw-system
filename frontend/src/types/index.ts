export interface Role {
  id: number;
  name: string;
  description?: string | null;
  is_system_role: boolean;
  permissions: Permission[];
}

export interface Permission {
  id: number;
  code: string;
  module: string;
  action: string;
  description?: string | null;
}

export interface User {
  id: number;
  uuid: string;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string | null;
  is_active: boolean;
  is_superuser: boolean;
  avatar_url?: string | null;
  role_id?: number | null;
  branch_id?: number | null;
  role?: Role | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CurrentUser extends User {
  permissions: string[];
}

export interface Branch {
  id: number;
  name: string;
  code: string;
  email?: string | null;
  phone?: string | null;
  address_line1?: string | null;
  city_id?: number | null;
  country_id?: number | null;
  is_head_office: boolean;
  manager_id?: number | null;
  status: string;
}

export interface Country {
  id: number;
  name: string;
  iso_code2: string;
  iso_code3: string;
  phone_code?: string | null;
  status: string;
}

export interface City {
  id: number;
  name: string;
  country_id: number;
  status: string;
}

export interface Currency {
  id: number;
  code: string;
  name: string;
  symbol: string;
  exchange_rate_to_base: number;
  is_base_currency: boolean;
  status: string;
}

export interface CompanyProfile {
  id: number;
  legal_name: string;
  trade_name?: string | null;
  registration_number?: string | null;
  tax_number?: string | null;
  email?: string | null;
  phone?: string | null;
  website?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city_id?: number | null;
  country_id?: number | null;
  base_currency_id?: number | null;
  logo_url?: string | null;
  default_language: string;
}

export interface SystemSetting {
  id: number;
  key: string;
  value?: string | null;
  value_type: string;
  category: string;
  description?: string | null;
  is_editable: boolean;
}

export interface ActivityLogEntry {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  description: string;
  actor_id?: number | null;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  changed_fields?: Record<string, { old: unknown; new: unknown }> | null;
  actor_id?: number | null;
  ip_address?: string | null;
  created_at: string;
}

export interface NotificationItem {
  id: number;
  title: string;
  message: string;
  notification_type: string;
  is_read: boolean;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ---------------- Phase 2: Property Owners ----------------
export interface OwnerAddress {
  id: number;
  owner_id: number;
  address_type: string;
  line1: string;
  line2?: string | null;
  city_id?: number | null;
  country_id?: number | null;
  postal_code?: string | null;
  is_primary: boolean;
}

export interface OwnerBankAccount {
  id: number;
  owner_id: number;
  bank_name: string;
  account_holder_name: string;
  account_number?: string | null;
  iban?: string | null;
  swift_code?: string | null;
  currency_id?: number | null;
  is_primary: boolean;
}

export interface OwnerContact {
  id: number;
  owner_id: number;
  full_name: string;
  designation?: string | null;
  email?: string | null;
  phone?: string | null;
  is_primary: boolean;
}

export interface OwnerDocument {
  id: number;
  owner_id: number;
  document_type: string;
  document_number?: string | null;
  issue_date?: string | null;
  expiry_date?: string | null;
  file_name: string;
  file_url?: string | null;
  file_size_bytes: number;
  mime_type: string;
  description?: string | null;
  is_expired: boolean;
}

export interface OwnerListItem {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  owner_code: string;
  owner_type: "individual" | "company";
  display_name: string;
  primary_email?: string | null;
  primary_phone?: string | null;
  branch_id?: number | null;
}

export interface OwnerDetail extends OwnerListItem {
  first_name?: string | null;
  last_name?: string | null;
  national_id?: string | null;
  date_of_birth?: string | null;
  nationality_id?: number | null;
  company_name?: string | null;
  registration_number?: string | null;
  tax_number?: string | null;
  contact_person_name?: string | null;
  contact_person_title?: string | null;
  secondary_phone?: string | null;
  website?: string | null;
  notes_summary?: string | null;
  addresses: OwnerAddress[];
  bank_accounts: OwnerBankAccount[];
  contacts: OwnerContact[];
  documents: OwnerDocument[];
}

export interface OwnerDashboard {
  total_owners: number;
  individual_owners: number;
  company_owners: number;
  active_owners: number;
  owners_missing_bank_details: number;
  recently_added: OwnerListItem[];
}

// ---------------- Owner Ledger & Recoverable Expense Engine ----------------
export interface OwnerLedgerEntry {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  owner_id: number;
  owner_name?: string | null;
  property_id?: number | null;
  property_title?: string | null;
  building_id?: number | null;
  building_name?: string | null;
  transaction_date: string;
  transaction_type: string;
  expense_category?: string | null;
  reference_type?: string | null;
  reference_id?: number | null;
  description: string;
  debit: string;
  credit: string;
  balance: string;
  entry_status: "active" | "reversed" | "reversal";
  reversal_of_id?: number | null;
  reversed_by_id?: number | null;
}

export interface OwnerLedgerBalance {
  owner_id: number;
  current_balance: string;
  outstanding_recoverable_expenses: string;
}

export interface OwnerLedgerDashboard {
  owner_id: number;
  current_balance: string;
  outstanding_recoverable_expenses: string;
  monthly_income: string;
  monthly_expenses: string;
  payments_made: string;
  payments_received: string;
}

export interface OwnerStatement {
  owner_id: number;
  owner_name?: string | null;
  date_from: string;
  date_to: string;
  opening_balance: string;
  rental_income: string;
  management_fees: string;
  recoverable_expenses: string;
  recovered_amounts: string;
  owner_payments: string;
  other_adjustments: string;
  net_movement: string;
  closing_balance: string;
  line_items: OwnerLedgerEntry[];
}

// ---------------- Payment & Collection Engine ----------------
export interface PaymentAllocation {
  id: number;
  payment_id: number;
  invoice_id: number;
  invoice_number?: string | null;
  amount: string;
  transaction_id?: number | null;
}

export interface Payment {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  payment_number: string;
  tenant_id: number;
  tenant_name?: string | null;
  rental_contract_id?: number | null;
  property_id?: number | null;
  property_title?: string | null;
  building_name?: string | null;
  owner_id?: number | null;
  owner_name?: string | null;
  account_id: number;
  payment_method: string;
  payment_date: string;
  amount: string;
  currency?: string | null;
  reference_number?: string | null;
  notes?: string | null;
  payment_status: "pending" | "verified" | "partially_paid" | "paid" | "cancelled" | "refunded" | "reversed";
  cancellation_reason?: string | null;
  refund_reason?: string | null;
  verified_at?: string | null;
  refunded_at?: string | null;
  reversed_at?: string | null;
  allocations: PaymentAllocation[];
}

export interface CollectionDashboard {
  collected_today: string;
  collected_this_month: string;
  total_outstanding: string;
  overdue_amount: string;
  collection_percentage: string;
  payments_by_status: Record<string, number>;
}

// ---------------- Rent Cycle Engine ----------------
export interface RentCycleRecord {
  id: number;
  cycle_id: number;
  rental_contract_id: number;
  invoice_id?: number | null;
  installment_id?: number | null;
  amount: string;
  due_date: string;
  record_status: "generated" | "skipped" | "failed";
  skip_reason?: string | null;
  tenant_display_name?: string | null;
  property_title?: string | null;
  building_title?: string | null;
  unit_number?: string | null;
  invoice_number?: string | null;
  invoice_status?: string | null;
  receipt_number?: string | null;
}

export interface RentCycle {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  cycle_number: string;
  month: number;
  year: number;
  start_date: string;
  due_date: string;
  closing_date?: string | null;
  cycle_status: "draft" | "generated" | "printed" | "distributed" | "collecting" | "partially_collected" | "completed" | "closed" | "cancelled";
  generated_at?: string | null;
  closed_at?: string | null;
  property_ids?: number[] | null;
  notes?: string | null;
  cancellation_reason?: string | null;
  records: RentCycleRecord[];
}

export interface RentCycleDashboard {
  total_cycles: number;
  open_cycles: number;
  cycles_by_status: Record<string, number>;
  current_cycle_number?: string | null;
  total_receipts: number;
  total_expected_income: string;
  total_collected_income: string;
  active_lease_count: number;
  generated_receipt_count: number;
  collection_progress_percent: string;
}

export interface RentCycleGenerateResult {
  cycle: RentCycle;
  invoices_generated: number;
  receipts_generated: number;
  leases_skipped: number;
  message: string;
}

// ---------------- Phase 3: Lease Agreements ----------------
export interface LeasePaymentInstallment {
  id: number;
  lease_id: number;
  installment_number: number;
  due_date: string;
  amount: string;
  payment_status: "pending" | "paid" | "overdue" | "cancelled";
  paid_date?: string | null;
  payment_method?: string | null;
  reference_number?: string | null;
  notes?: string | null;
  is_overdue: boolean;
}

export interface LeaseAgreementListItem {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  contract_number: string;
  owner_id: number;
  owner_display_name?: string | null;
  property_id?: number | null;
  property_title?: string | null;
  unit_number?: string | null;
  property_reference: string;
  start_date: string;
  end_date: string;
  contract_status: "draft" | "active" | "expired" | "terminated" | "renewed";
  rent_amount: string;
  currency_id?: number | null;
  is_expiring_soon: boolean;
  days_until_expiry: number;
}

export interface LeaseAgreementDetail extends LeaseAgreementListItem {
  branch_id?: number | null;
  signed_date?: string | null;
  is_renewable: boolean;
  renewal_notice_days: number;
  renewal_reminder_sent: boolean;
  renewed_from_lease_id?: number | null;
  payment_frequency: "monthly" | "quarterly" | "semi_annual" | "annual" | "one_time" | "custom";
  security_deposit_amount: string;
  security_deposit_status: "held" | "returned" | "partially_returned" | "forfeited";
  terminated_date?: string | null;
  termination_reason?: string | null;
  notes_summary?: string | null;
  installments: LeasePaymentInstallment[];
}

export interface LeaseDashboard {
  total_leases: number;
  active_leases: number;
  draft_leases: number;
  expiring_soon: number;
  terminated_leases: number;
  total_outstanding_amount: string;
  upcoming_renewals: LeaseAgreementListItem[];
}

// ---------------- Phase 4: Property Management ----------------
export type PropertyType =
  | "building" | "villa" | "apartment" | "commercial_unit" | "warehouse"
  | "shop" | "office" | "land" | "parking" | "storage"
  | "commercial_building" | "commercial_complex" | "mixed_use";

export type AvailabilityStatus = "available" | "leased" | "reserved" | "under_maintenance" | "off_market";
export type FurnishingStatus = "furnished" | "semi_furnished" | "unfurnished";

export interface Amenity {
  id: number;
  name: string;
  category?: string | null;
  status: string;
}

export interface PropertyImage {
  id: number;
  property_id: number;
  file_name: string;
  file_url?: string | null;
  file_size_bytes: number;
  mime_type: string;
  caption?: string | null;
  is_cover: boolean;
  sort_order: number;
}

export interface PropertyDocument {
  id: number;
  property_id: number;
  document_type: string;
  document_number?: string | null;
  issue_date?: string | null;
  expiry_date?: string | null;
  file_name: string;
  file_url?: string | null;
  file_size_bytes: number;
  mime_type: string;
  description?: string | null;
  is_expired: boolean;
}

export interface PropertyListItem {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  property_code: string;
  internal_code?: string | null;
  property_type: PropertyType;
  title: string;
  owner_id: number;
  owner_display_name?: string | null;
  city_id?: number | null;
  availability_status: AvailabilityStatus;
  area_sqm?: string | null;
  bedrooms?: number | null;
  current_lease_contract_number?: string | null;
  unit_number?: string | null;
  rent_price?: string | null;
  floor_id?: number | null;
  floor_label?: string | null;
  parent_property_id?: number | null;
}

export interface Floor {
  id: number;
  building_id: number;
  floor_number: string;
  floor_name?: string | null;
  total_units?: number | null;
  description?: string | null;
  unit_count: number;
  status: string;
}

export interface PropertySummary {
  property_type: PropertyType;
  total_floors: number;
  total_units: number;
  occupied_units: number;
  vacant_units: number;
  reserved_units: number;
  under_maintenance_units: number;
  residential_units: number;
  commercial_units: number;
  occupancy_rate: number;
  active_contracts: number;
  expired_contracts: number;
  contracts_expiring_soon: number;
  monthly_revenue: string;
  monthly_expenses: string;
  net_profit?: string | null;
  last_updated?: string | null;
}

export interface PropertyDetail extends PropertyListItem {
  parent_property_id?: number | null;
  description?: string | null;
  branch_id?: number | null;
  address_line1?: string | null;
  address_line2?: string | null;
  country_id?: number | null;
  postal_code?: string | null;
  display_location?: string | null;
  latitude?: string | null;
  longitude?: string | null;
  bathrooms?: number | null;
  floor_number?: string | null;
  total_floors?: number | null;
  year_built?: number | null;
  furnishing_status?: FurnishingStatus | null;
  notes_summary?: string | null;
  amenities: Amenity[];
  images: PropertyImage[];
  documents: PropertyDocument[];
  current_lease_id?: number | null;
  current_lease_end_date?: string | null;
  floor_label?: string | null;
  electricity_meter_number?: string | null;
  water_meter_number?: string | null;
  paci_number?: string | null;
  parking_space_id?: number | null;
  parking_space_code?: string | null;
  storage_space_id?: number | null;
  storage_space_code?: string | null;
  // --- Phase 2.0: Building/Villa characteristics ---
  elevators?: number | null;
  parking_spaces_count?: number | null;
  garden?: boolean | null;
  swimming_pool?: boolean | null;
  maid_room?: boolean | null;
  // Populated only for container-type properties (building/villa/
  // commercial_building/commercial_complex/warehouse/land/mixed_use).
  summary?: PropertySummary | null;
}

export interface PropertyDashboard {
  total_properties: number;
  by_type: Record<string, number>;
  by_availability: Record<string, number>;
  recently_added: PropertyListItem[];
  total_buildings: number;
  total_villas: number;
  total_commercial_properties: number;
  total_warehouses: number;
  total_lands: number;
  total_units: number;
  occupied_units: number;
  vacant_units: number;
  occupancy_rate: number;
}

// ---------------- Phase 6: Tenant Management ----------------
export interface TenantContact {
  id: number;
  tenant_id: number;
  full_name: string;
  designation?: string | null;
  email?: string | null;
  phone?: string | null;
  is_primary: boolean;
}

export interface TenantEmergencyContact {
  id: number;
  tenant_id: number;
  full_name: string;
  relationship_type?: string | null;
  phone: string;
  email?: string | null;
  address?: string | null;
  is_primary: boolean;
}

export interface TenantDocument {
  id: number;
  tenant_id: number;
  document_type: string;
  document_number?: string | null;
  issue_date?: string | null;
  expiry_date?: string | null;
  file_name: string;
  file_url?: string | null;
  file_size_bytes: number;
  mime_type: string;
  description?: string | null;
  is_expired: boolean;
}

export interface TenantRating {
  id: number;
  tenant_id: number;
  rating_value: number;
  comment?: string | null;
  created_at: string;
}

export interface TenantListItem {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  tenant_code: string;
  tenant_type: "individual" | "company";
  display_name: string;
  primary_email?: string | null;
  primary_phone?: string | null;
  branch_id?: number | null;
  is_blacklisted: boolean;
  average_rating?: number | null;
}

export interface TenantDetail extends TenantListItem {
  first_name?: string | null;
  last_name?: string | null;
  national_id?: string | null;
  passport_number?: string | null;
  date_of_birth?: string | null;
  nationality_id?: number | null;
  company_name?: string | null;
  commercial_registration_number?: string | null;
  tax_number?: string | null;
  contact_person_name?: string | null;
  contact_person_title?: string | null;
  secondary_phone?: string | null;
  website?: string | null;
  address?: string | null;
  notes_summary?: string | null;
  blacklist_reason?: string | null;
  blacklisted_at?: string | null;
  blacklisted_by?: number | null;
  contacts: TenantContact[];
  emergency_contacts: TenantEmergencyContact[];
  documents: TenantDocument[];
  ratings: TenantRating[];
  rating_count: number;
}

export interface TenantDashboard {
  total_tenants: number;
  individual_tenants: number;
  company_tenants: number;
  active_tenants: number;
  blacklisted_tenants: number;
  average_rating_overall?: number | null;
  recently_added: TenantListItem[];
}

// ---------------- Phase 7: Rental Contracts ----------------
export interface RentalInstallment {
  id: number;
  contract_id: number;
  installment_number: number;
  due_date: string;
  amount: string;
  discount_amount: string;
  tax_amount: string;
  late_fee_amount: string;
  total_payable: string;
  payment_status: "pending" | "paid" | "overdue" | "cancelled";
  paid_date?: string | null;
  payment_method?: string | null;
  reference_number?: string | null;
  notes?: string | null;
  is_overdue: boolean;
  receipt_number?: string | null;
  printed_at?: string | null;
  print_count: number;
}

export interface RentalContractListItem {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  contract_number: string;
  tenant_id: number;
  tenant_display_name?: string | null;
  property_id: number;
  property_title?: string | null;
  unit_number?: string | null;
  start_date: string;
  end_date: string;
  contract_status: "draft" | "active" | "expired" | "terminated" | "renewed";
  rent_amount: string;
  currency_id?: number | null;
  is_expiring_soon: boolean;
  days_until_expiry: number;
  tenant_is_blacklisted: boolean;
}

export interface RentalContractDetail extends RentalContractListItem {
  branch_id?: number | null;
  signed_date?: string | null;
  is_renewable: boolean;
  auto_renew: boolean;
  renewal_notice_days: number;
  renewal_reminder_sent: boolean;
  renewed_from_contract_id?: number | null;
  payment_frequency: "monthly" | "quarterly" | "semi_annual" | "annual" | "one_time" | "custom";
  security_deposit_amount: string;
  security_deposit_status: "held" | "returned" | "partially_returned" | "forfeited";
  discount_type: "none" | "percentage" | "fixed";
  discount_value: string;
  discount_reason?: string | null;
  discount_amount_computed: string;
  tax_rate: string;
  tax_amount_computed: string;
  late_fee_type: "percentage" | "fixed";
  late_fee_value: string;
  late_fee_grace_period_days: number;
  terminated_date?: string | null;
  termination_reason?: string | null;
  notes_summary?: string | null;
  installments: RentalInstallment[];
}

export interface RentalDashboard {
  total_contracts: number;
  active_contracts: number;
  draft_contracts: number;
  expiring_soon: number;
  terminated_contracts: number;
  total_outstanding_amount: string;
  upcoming_renewals: RentalContractListItem[];
}

// ---------------- Phase 8: Financial Management ----------------
export type AccountType = "cash" | "bank";
export type TransactionType =
  | "tenant_payment" | "owner_payment" | "expense" | "income"
  | "deposit_received" | "deposit_refund" | "refund" | "transfer_in" | "transfer_out";
export type InvoiceStatus = "draft" | "sent" | "paid" | "overdue" | "cancelled";

export interface FinancialAccount {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  account_code: string;
  account_type: AccountType;
  name: string;
  bank_name?: string | null;
  account_number?: string | null;
  iban?: string | null;
  currency_id?: number | null;
  branch_id?: number | null;
  opening_balance: string;
  is_default: boolean;
  current_balance: string;
}

export interface FinancialTransaction {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  transaction_number: string;
  transaction_type: TransactionType;
  direction: "in" | "out";
  transaction_status: "completed" | "cancelled";
  amount: string;
  account_id: number;
  account_name?: string | null;
  transfer_pair_id?: number | null;
  tenant_id?: number | null;
  tenant_display_name?: string | null;
  owner_id?: number | null;
  owner_display_name?: string | null;
  property_id?: number | null;
  property_title?: string | null;
  unit_number?: string | null;
  rental_contract_id?: number | null;
  rental_installment_id?: number | null;
  lease_agreement_id?: number | null;
  lease_installment_id?: number | null;
  category?: string | null;
  payment_method?: string | null;
  reference_number?: string | null;
  transaction_date: string;
  description?: string | null;
  receipt_number?: string | null;
  receipt_id?: number | null;
}

export interface Receipt {
  id: number;
  receipt_number: string;
  transaction_id: number;
  issued_date: string;
  notes?: string | null;
  transaction?: FinancialTransaction | null;
}

export interface Invoice {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  invoice_number: string;
  tenant_id: number;
  tenant_display_name?: string | null;
  rental_contract_id?: number | null;
  property_id?: number | null;
  property_title?: string | null;
  unit_number?: string | null;
  amount: string;
  issue_date: string;
  due_date: string;
  invoice_status: InvoiceStatus;
  description?: string | null;
  paid_transaction_id?: number | null;
  is_overdue: boolean;
  billing_cycle?: string | null;
  billing_period_start?: string | null;
  billing_period_end?: string | null;
  amount_paid: string;
  outstanding_amount: string;
  void_reason?: string | null;
  voided_at?: string | null;
  printed_at?: string | null;
  print_count: number;
  delivered_at?: string | null;
  qr_token?: string | null;
}

export interface OutstandingBalanceItem {
  id: number;
  display_name: string;
  outstanding_amount: string;
  overdue_count: number;
  pending_count: number;
}

export interface OutstandingBalance {
  tenants: OutstandingBalanceItem[];
  owners: OutstandingBalanceItem[];
  total_tenant_outstanding: string;
  total_owner_outstanding: string;
}

export interface FinancialDashboard {
  total_cash_balance: string;
  total_bank_balance: string;
  total_income_this_month: string;
  total_expense_this_month: string;
  total_tenant_outstanding: string;
  total_owner_outstanding: string;
  accounts: FinancialAccount[];
}

// ---------------- Phase 9: Maintenance ----------------
export type MaintenancePriority = "low" | "medium" | "high" | "urgent";
export type MaintenanceStatus = "reported" | "assigned" | "in_progress" | "on_hold" | "completed" | "cancelled";
export type PhotoType = "before" | "after";

export interface Contractor {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  contractor_code: string;
  company_name: string;
  contact_person?: string | null;
  phone?: string | null;
  email?: string | null;
  specialty?: string | null;
  hourly_rate?: string | null;
  notes?: string | null;
  technician_count: number;
}

export interface Technician {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  technician_code: string;
  first_name: string;
  last_name: string;
  full_name: string;
  phone?: string | null;
  email?: string | null;
  specialty?: string | null;
  contractor_id?: number | null;
  contractor_name?: string | null;
  hourly_rate?: string | null;
  notes?: string | null;
  is_in_house: boolean;
}

export interface MaintenanceMaterialItem {
  id: number;
  request_id: number;
  name: string;
  quantity: string;
  unit_cost: string;
  supplier?: string | null;
  total_cost: string;
}

export interface MaintenanceLaborItem {
  id: number;
  request_id: number;
  technician_id?: number | null;
  technician_name?: string | null;
  contractor_id?: number | null;
  work_date: string;
  hours: string;
  hourly_rate: string;
  description?: string | null;
  total_cost: string;
}

export interface MaintenancePhotoItem {
  id: number;
  request_id: number;
  photo_type: PhotoType;
  file_name: string;
  file_url?: string | null;
  file_size_bytes: number;
  mime_type: string;
  caption?: string | null;
}

export interface MaintenanceRequestListItem {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  request_number: string;
  property_id: number;
  property_title?: string | null;
  tenant_id?: number | null;
  tenant_display_name?: string | null;
  title: string;
  category?: string | null;
  priority: MaintenancePriority;
  maintenance_status: MaintenanceStatus;
  reported_date: string;
  scheduled_date?: string | null;
  completed_date?: string | null;
  contractor_name?: string | null;
  technician_name?: string | null;
  total_actual_cost: string;
  is_overdue: boolean;
}

export interface MaintenanceRequestDetail extends MaintenanceRequestListItem {
  rental_contract_id?: number | null;
  description?: string | null;
  assigned_contractor_id?: number | null;
  assigned_technician_id?: number | null;
  estimated_cost?: string | null;
  on_hold_reason?: string | null;
  cancellation_reason?: string | null;
  notes?: string | null;
  total_material_cost: string;
  total_labor_cost: string;
  materials: MaintenanceMaterialItem[];
  labor_entries: MaintenanceLaborItem[];
  photos: MaintenancePhotoItem[];
}

export interface MaintenanceDashboard {
  total_requests: number;
  reported_count: number;
  assigned_count: number;
  in_progress_count: number;
  on_hold_count: number;
  completed_count: number;
  cancelled_count: number;
  overdue_count: number;
  urgent_open_count: number;
  total_actual_cost_this_month: string;
}

// ---------------- Maintenance Contracts extension (recurring/annual
// service contracts: elevators, HVAC/AC, generators, fire safety, etc.) ----------------
export type MaintenanceContractStatus = "draft" | "active" | "expired" | "terminated" | "renewed";
export type ContractVisitFrequency = "monthly" | "quarterly" | "semi_annual" | "annual" | "custom";

export interface MaintenanceContractListItem {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  contract_number: string;
  property_id: number;
  property_title?: string | null;
  contractor_id: number;
  contractor_name?: string | null;
  service_type: string;
  title: string;
  start_date: string;
  end_date: string;
  visit_frequency: ContractVisitFrequency;
  next_service_due_date?: string | null;
  annual_cost: string;
  currency_id?: number | null;
  contract_status: MaintenanceContractStatus;
  is_expiring_soon: boolean;
  is_service_due_soon: boolean;
  is_service_overdue: boolean;
  days_until_expiry: number;
}

export interface MaintenanceContractDetail extends MaintenanceContractListItem {
  description?: string | null;
  signed_date?: string | null;
  visits_per_year?: number | null;
  is_renewable: boolean;
  renewal_notice_days: number;
  renewal_reminder_sent: boolean;
  renewed_from_contract_id?: number | null;
  terminated_date?: string | null;
  termination_reason?: string | null;
  notes?: string | null;
}

export interface MaintenanceContractDashboard {
  total_contracts: number;
  active_contracts: number;
  draft_contracts: number;
  expiring_soon: number;
  service_due_soon: number;
  terminated_contracts: number;
  upcoming: MaintenanceContractListItem[];
}

// ---------------- Phase 10: Accounting ----------------
export type GLAccountType = "asset" | "liability" | "equity" | "revenue" | "expense";
export type EntryStatus = "draft" | "posted" | "reversed";
export type SourceType = "manual" | "system";

export interface ChartOfAccountItem {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  account_code: string;
  account_name: string;
  account_type: GLAccountType;
  account_subtype?: string | null;
  parent_account_id?: number | null;
  parent_account_name?: string | null;
  allow_posting: boolean;
  description?: string | null;
  normal_balance: "debit" | "credit";
  balance?: string | null;
}

export interface CostCenterItem {
  id: number;
  cost_center_code: string;
  name: string;
  property_id?: number | null;
  property_title?: string | null;
  branch_id?: number | null;
  description?: string | null;
}

export interface VatRateItem {
  id: number;
  code: string;
  name: string;
  rate_percentage: string;
  gl_account_id?: number | null;
  gl_account_name?: string | null;
  is_default: boolean;
}

export interface PostingRuleItem {
  id: number;
  transaction_type: string;
  category?: string | null;
  offset_account_id: number;
  offset_account_name?: string | null;
  vat_rate_id?: number | null;
  cost_center_id?: number | null;
  description?: string | null;
}

export interface JournalEntryLineItem {
  id: number;
  journal_entry_id: number;
  account_id: number;
  account_code?: string | null;
  account_name?: string | null;
  cost_center_id?: number | null;
  debit_amount: string;
  credit_amount: string;
  description?: string | null;
  vat_rate_id?: number | null;
  vat_amount: string;
}

export interface JournalEntryListItem {
  id: number;
  entry_number: string;
  entry_date: string;
  description?: string | null;
  reference_number?: string | null;
  source_type: SourceType;
  source_transaction_id?: number | null;
  entry_status: EntryStatus;
  posted_at?: string | null;
  total_debit: string;
  total_credit: string;
}

export interface JournalEntryDetail extends JournalEntryListItem {
  reversed_entry_id?: number | null;
  lines: JournalEntryLineItem[];
}

export interface TrialBalanceLine {
  account_id: number;
  account_code: string;
  account_name: string;
  account_type: GLAccountType;
  debit_balance: string;
  credit_balance: string;
}

export interface TrialBalance {
  as_of_date: string;
  lines: TrialBalanceLine[];
  total_debit: string;
  total_credit: string;
  is_balanced: boolean;
}

export interface GeneralLedgerLine {
  journal_entry_id: number;
  entry_number: string;
  entry_date: string;
  description?: string | null;
  debit_amount: string;
  credit_amount: string;
  running_balance: string;
}

export interface GeneralLedger {
  account_id: number;
  account_code: string;
  account_name: string;
  opening_balance: string;
  lines: GeneralLedgerLine[];
  closing_balance: string;
}

export interface BalanceSheetSection {
  account_id: number;
  account_code: string;
  account_name: string;
  balance: string;
}

export interface BalanceSheet {
  as_of_date: string;
  assets: BalanceSheetSection[];
  liabilities: BalanceSheetSection[];
  equity: BalanceSheetSection[];
  total_assets: string;
  total_liabilities: string;
  total_equity: string;
  is_balanced: boolean;
}

export interface IncomeStatement {
  date_from: string;
  date_to: string;
  revenue: BalanceSheetSection[];
  expenses: BalanceSheetSection[];
  total_revenue: string;
  total_expenses: string;
  net_income: string;
}

export interface CashFlowLine {
  transaction_type: string;
  total_amount: string;
}

export interface CashFlow {
  date_from: string;
  date_to: string;
  operating_activities: CashFlowLine[];
  net_operating_cash_flow: string;
  net_change_in_cash: string;
  opening_cash_balance: string;
  closing_cash_balance: string;
}

export interface VatReportLine {
  vat_rate_id: number;
  vat_code: string;
  vat_name: string;
  rate_percentage: string;
  output_vat: string;
  input_vat: string;
  net_vat: string;
}

export interface VatReport {
  date_from: string;
  date_to: string;
  lines: VatReportLine[];
  total_output_vat: string;
  total_input_vat: string;
  total_net_vat: string;
}

// ---------------- Phase 11: Reports ----------------
export interface NamedAmount {
  label: string;
  total_amount: string;
  count: number;
}

export interface MonthlyAmount {
  month: string;
  total_amount: string;
}

export interface ReportPropertyAmount {
  property_id: number;
  property_code: string;
  property_title: string;
  total_amount: string;
}

export interface FinancialReport {
  date_from: string;
  date_to: string;
  total_income: string;
  total_expense: string;
  net_cash_flow: string;
  total_outstanding_tenant: string;
  total_outstanding_owner: string;
  collection_rate_percentage: string;
  transactions_by_type: NamedAmount[];
}

export interface TenantPaymentItem {
  tenant_id: number;
  display_name: string;
  total_paid: string;
  payment_count: number;
}

export interface TenantOutstandingItem {
  tenant_id: number;
  display_name: string;
  outstanding_amount: string;
}

export interface TenantReport {
  total_tenants: number;
  individual_tenants: number;
  company_tenants: number;
  blacklisted_tenants: number;
  average_rating?: string | null;
  contracts_expiring_soon: number;
  top_tenants_by_payment: TenantPaymentItem[];
  outstanding_tenants: TenantOutstandingItem[];
}

export interface OwnerPropertyCountItem {
  owner_id: number;
  display_name: string;
  property_count: number;
}

export interface OwnerOutstandingItem {
  owner_id: number;
  display_name: string;
  outstanding_amount: string;
}

export interface OwnerReport {
  total_owners: number;
  individual_owners: number;
  company_owners: number;
  total_paid_to_owners: string;
  top_owners_by_properties: OwnerPropertyCountItem[];
  outstanding_owners: OwnerOutstandingItem[];
}

export interface PropertyTypeCount {
  property_type: string;
  count: number;
}

export interface PropertyStatusCount {
  availability_status: string;
  count: number;
}

export interface PropertyReport {
  total_properties: number;
  by_type: PropertyTypeCount[];
  by_availability: PropertyStatusCount[];
  top_properties_by_revenue: ReportPropertyAmount[];
}

export interface VacantPropertyItem {
  property_id: number;
  property_code: string;
  title: string;
  property_type: string;
  days_vacant: number;
}

export interface VacancyReport {
  as_of_date: string;
  total_properties: number;
  vacant_count: number;
  leased_count: number;
  other_count: number;
  vacancy_rate_percentage: string;
  vacant_properties: VacantPropertyItem[];
}

export interface OccupancyByTypeItem {
  property_type: string;
  total: number;
  occupied: number;
  occupancy_rate_percentage: string;
}

export interface OccupancyTrendPoint {
  month: string;
  occupancy_rate_percentage: string;
}

export interface OccupancyReport {
  as_of_date: string;
  overall_occupancy_rate_percentage: string;
  by_property_type: OccupancyByTypeItem[];
  trend: OccupancyTrendPoint[];
}

export interface UnitReportItem {
  property_id: number;
  property_code: string;
  title: string;
  property_type: string;
  availability_status: string;
  building_title?: string | null;
  floor_label?: string | null;
  unit_number?: string | null;
  rent_price?: string | null;
}

export interface UnitReport {
  as_of_date: string;
  scoped_to_property_id?: number | null;
  scoped_to_property_title?: string | null;
  total_units: number;
  vacant_count: number;
  occupied_count: number;
  reserved_count: number;
  under_maintenance_count: number;
  by_status: { availability_status: string; count: number }[];
  by_type: { property_type: string; count: number }[];
  units: UnitReportItem[];
}

export interface IncomeReport {
  date_from: string;
  date_to: string;
  total_income: string;
  by_category: NamedAmount[];
  by_property: ReportPropertyAmount[];
  trend: MonthlyAmount[];
}

export interface ExpenseReport {
  date_from: string;
  date_to: string;
  total_expense: string;
  total_maintenance_cost: string;
  by_category: NamedAmount[];
  by_property: ReportPropertyAmount[];
  trend: MonthlyAmount[];
}

export interface ProfitByPropertyItem {
  property_id: number;
  property_code: string;
  property_title: string;
  income: string;
  expense: string;
  profit: string;
}

export interface ProfitTrendPoint {
  month: string;
  income: string;
  expense: string;
  profit: string;
}

export interface ProfitReport {
  date_from: string;
  date_to: string;
  total_income: string;
  total_expense: string;
  net_profit: string;
  profit_margin_percentage: string;
  by_property: ProfitByPropertyItem[];
  trend: ProfitTrendPoint[];
}

export interface DashboardKPIs {
  total_properties: number;
  occupied_properties: number;
  vacancy_rate_percentage: string;
  total_tenants: number;
  total_owners: number;
  active_rental_contracts: number;
  active_lease_agreements: number;
  open_maintenance_requests: number;
  total_income_this_month: string;
  total_expense_this_month: string;
  net_profit_this_month: string;
  total_outstanding_tenant: string;
  total_outstanding_owner: string;
  // Enterprise Dashboard extension (additive)
  total_units: number;
  occupied_units: number;
  vacant_units: number;
  occupancy_rate_percentage: string;
  contracts_expiring_soon: number;
}

export interface DashboardAnalytics {
  generated_at: string;
  kpis: DashboardKPIs;
  monthly_trend: ProfitTrendPoint[];
  top_properties_by_revenue: ReportPropertyAmount[];
  // Enterprise Dashboard extension (additive)
  properties_by_type: PropertyTypeCount[];
  properties_by_availability: PropertyStatusCount[];
  occupancy_by_type: OccupancyByTypeItem[];
  cash_flow_by_type: NamedAmount[];
}

// ---------------- Building Management (extends Property/Phase 4-5) ----------------
export interface BuildingSummary {
  floor_count: number;
  unit_count: number;
  occupied_units: number;
  vacant_units: number;
  other_units: number;
  residential_units: number;
  commercial_units: number;
  occupancy_rate: number;
  active_leases_count: number;
  expired_leases_count: number;
  contracts_expiring_soon: number;
  tenant_count: number;
  open_maintenance_requests_count: number;
}

// ---------------- Property Profit Center extension ----------------
export interface PropertyDashboardKPIs {
  availability_status: string;
  active_leases_count: number;
  open_maintenance_requests: number;
  total_income_this_month: string;
  total_expense_this_month: string;
  net_profit_this_month: string;
  total_income_ytd: string;
  total_expense_ytd: string;
  net_profit_ytd: string;
  total_outstanding_tenant: string;
}

export interface PropertyFinancialDashboard {
  property_id: number;
  property_code: string;
  property_title: string;
  generated_at: string;
  kpis: PropertyDashboardKPIs;
  monthly_trend: ProfitTrendPoint[];
}

export interface PropertyProfitAndLoss {
  property_id: number;
  property_code: string;
  property_title: string;
  date_from: string;
  date_to: string;
  total_income: string;
  total_expense: string;
  net_profit: string;
  profit_margin_percentage: string;
  income_by_category: NamedAmount[];
  expense_by_category: NamedAmount[];
  trend: ProfitTrendPoint[];
}

// ---------------- Enterprise Reporting extension ----------------
export interface ContractStatusCount {
  status: string;
  count: number;
  total_rent: string;
}

export interface RentalContractSummaryItem {
  id: number;
  contract_number: string;
  tenant_display_name?: string | null;
  property_id: number;
  property_title?: string | null;
  unit_number?: string | null;
  start_date: string;
  end_date: string;
  rent_amount: string;
  contract_status: string;
}

export interface LeaseAgreementSummaryItem {
  id: number;
  contract_number: string;
  owner_display_name?: string | null;
  property_id?: number | null;
  property_title?: string | null;
  unit_number?: string | null;
  start_date: string;
  end_date: string;
  rent_amount: string;
  contract_status: string;
}

export interface LeaseReport {
  rental_contracts_by_status: ContractStatusCount[];
  lease_agreements_by_status: ContractStatusCount[];
  rental_contracts: RentalContractSummaryItem[];
  lease_agreements: LeaseAgreementSummaryItem[];
}

export interface MaintenanceStatusCount { status: string; count: number; }
export interface MaintenancePriorityCount { priority: string; count: number; }
export interface MaintenanceCategoryCount { category: string; count: number; }
export interface MaintenanceContractorCount { contractor_id: number; contractor_name: string; request_count: number; }

export interface MaintenanceRequestSummaryItem {
  id: number;
  request_number: string;
  title: string;
  property_title?: string | null;
  category?: string | null;
  priority: string;
  maintenance_status: string;
  reported_date: string;
  completed_date?: string | null;
  total_actual_cost: string;
  contractor_name?: string | null;
}

export interface MaintenanceReport {
  date_from: string;
  date_to: string;
  total_requests: number;
  by_status: MaintenanceStatusCount[];
  by_priority: MaintenancePriorityCount[];
  by_category: MaintenanceCategoryCount[];
  by_contractor: MaintenanceContractorCount[];
  total_cost: string;
  average_resolution_days?: string | null;
  requests: MaintenanceRequestSummaryItem[];
}

export interface CollectionsMonthlyPoint {
  month: string;
  due: string;
  collected: string;
  collection_rate_percentage: string;
}

export interface CollectionsByPropertyItem {
  property_id: number;
  property_code: string;
  property_title: string;
  due: string;
  collected: string;
  collection_rate_percentage: string;
}

export interface CollectionsReport {
  date_from: string;
  date_to: string;
  total_due: string;
  total_collected: string;
  collection_rate_percentage: string;
  monthly_trend: CollectionsMonthlyPoint[];
  by_property: CollectionsByPropertyItem[];
}

export interface AgingBuckets {
  current: string;
  days_1_30: string;
  days_31_60: string;
  days_61_90: string;
  days_90_plus: string;
}

export interface OutstandingReport {
  as_of_date: string;
  tenant_outstanding_total: string;
  tenant_aging: AgingBuckets;
  tenant_outstanding_list: TenantOutstandingItem[];
  owner_outstanding_total: string;
  owner_aging: AgingBuckets;
  owner_outstanding_list: OwnerOutstandingItem[];
}

export interface ExpiringRentalContractItem {
  id: number;
  contract_number: string;
  tenant_display_name?: string | null;
  property_id: number;
  property_title?: string | null;
  unit_number?: string | null;
  end_date: string;
  days_remaining: number;
  rent_amount: string;
}

export interface ExpiringLeaseAgreementItem {
  id: number;
  contract_number: string;
  owner_display_name?: string | null;
  property_id?: number | null;
  property_title?: string | null;
  unit_number?: string | null;
  end_date: string;
  days_remaining: number;
  rent_amount: string;
}

export interface ContractExpirationReport {
  as_of_date: string;
  window_days: number;
  total_expiring: number;
  expiring_rental_contracts: ExpiringRentalContractItem[];
  expiring_lease_agreements: ExpiringLeaseAgreementItem[];
}

export type ReportExportFormat = "pdf" | "excel";
export type ReportFrequency = "daily" | "weekly" | "monthly";

export interface ReportSchedule {
  id: number;
  uuid: string;
  name: string;
  report_type: string;
  export_format: ReportExportFormat;
  frequency: ReportFrequency;
  filters?: Record<string, unknown> | null;
  is_active: boolean;
  next_run_at: string;
  last_run_at?: string | null;
  last_export_file_url?: string | null;
  last_export_file_name?: string | null;
  created_at: string;
}

// ---------------- Rental Receipt Module ----------------
// (RentalInstallment type itself lives above, merged with the base
// declaration — the receipt_number/printed_at/print_count fields this
// module adds are folded into it there.)

export interface RentalReceipt {
  installment_id: number;
  receipt_number: string;
  receipt_date: string;
  rental_month: string;
  tenant_name: string;
  tenant_address?: string | null;
  building_name?: string | null;
  building_number?: string | null;
  unit_name?: string | null;
  unit_number?: string | null;
  amount: string;
  amount_in_words_en: string;
  amount_in_words_ar: string;
  payment_method?: string | null;
  bank_name?: string | null;
  reference_number?: string | null;
  print_count: number;
  printed_at?: string | null;
}

export interface RentVoucher {
  id: number;
  uuid: string;
  status: string;
  created_at: string;
  voucher_number: string;
  transaction_id: number;
  copy_type: "tenant" | "company";
  rental_month: string;
  barcode_value: string;
  print_count: number;
  printed_at?: string | null;
  tenant_name?: string | null;
  tenant_code?: string | null;
  tenant_phone?: string | null;
  building_name?: string | null;
  unit_number?: string | null;
  property_address?: string | null;
  amount?: string | null;
  payment_method?: string | null;
  payment_method_label_en?: string | null;
  payment_method_label_ar?: string | null;
  transaction_number?: string | null;
  is_combined?: boolean;
  combined_transaction_count?: number;
}

export interface RentVoucherPrintData {
  voucher_id: number;
  voucher_number: string;
  copy_type: "tenant" | "company";
  copy_type_label_en: string;
  copy_type_label_ar: string;
  issue_date: string;
  rental_month_display_en: string;
  rental_month_display_ar: string;
  tenant_name: string;
  tenant_code?: string | null;
  tenant_national_id?: string | null;
  tenant_phone?: string | null;
  tenant_email?: string | null;
  building_name?: string | null;
  unit_number?: string | null;
  floor_unit_numbers?: string | null;
  unit_paci_number?: string | null;
  property_address?: string | null;
  amount: string;
  currency_code?: string | null;
  amount_in_words_en: string;
  amount_in_words_ar: string;
  payment_method?: string | null;
  payment_method_label_en: string;
  payment_method_label_ar: string;
  barcode_value: string;
  print_count: number;
  printed_at?: string | null;
}

export interface RentalReceiptSearchItem {
  installment_id: number;
  receipt_number: string;
  tenant_display_name?: string | null;
  property_title?: string | null;
  unit_number?: string | null;
  due_date: string;
  amount: string;
  payment_status: string;
  payment_method?: string | null;
  reference_number?: string | null;
  print_count: number;
}

export interface PaymentConfirmation {
  account_id: number;
  payment_method: string;
  reference_number?: string;
  transaction_date: string;
  notes?: string;
}

// ---------------- Rent Billing Engine ----------------
// (Invoice type itself lives above, merged with the base declaration —
// see the "Rent Billing Engine" fields folded into it there.)

export interface InvoicePrintData {
  invoice_id: number;
  invoice_number: string;
  issue_date: string;
  due_date: string;
  billing_period_start?: string | null;
  billing_period_end?: string | null;
  tenant_name?: string | null;
  tenant_address?: string | null;
  tenant_civil_id?: string | null;
  tenant_phone?: string | null;
  property_title?: string | null;
  property_code?: string | null;
  unit_number?: string | null;
  building_name?: string | null;
  building_number?: string | null;
  contract_number?: string | null;
  rent_amount?: string | null;
  discount_type?: string | null;
  discount_value?: string | null;
  tax_rate?: string | null;
  amount: string;
  amount_paid: string;
  outstanding_amount: string;
  company_name?: string | null;
  company_logo_url?: string | null;
  company_address?: string | null;
  company_phone?: string | null;
  company_email?: string | null;
  company_website?: string | null;
  qr_verification_url?: string | null;
  qr_code_data_uri?: string | null;
  print_count: number;
}

// ---------------- Property Hierarchy Tree (read-only) ----------------
export interface HierarchyContractSummary {
  id: number;
  contract_number: string;
  tenant_id: number;
  tenant_name: string;
  rent_amount: string;
  end_date: string;
}
export interface HierarchyUnitNode {
  id: number;
  unit_number?: string | null;
  unit_type: string;
  availability_status: string;
  active_contract: HierarchyContractSummary | null;
}
export interface HierarchyFloorNode {
  id: number | null;
  floor_number: string | null;
  floor_name?: string | null;
  units: HierarchyUnitNode[];
}
export interface HierarchyPropertyNode {
  id: number;
  title: string;
  property_code: string;
  property_type: string;
  floors: HierarchyFloorNode[];
  active_contract: HierarchyContractSummary | null;
}
export interface PropertyHierarchyTree {
  owner: { id: number; owner_code: string; display_name: string };
  properties: HierarchyPropertyNode[];
}

// ---------------- Occupancy cross-reference (for cascading property selector) ----------------
export interface UnitOccupancySummary {
  property_id: number;
  property_title: string;
  property_code: string;
  unit_number?: string | null;
  building_id?: number | null;
  building_title?: string | null;
  occupancy_status: string;
  status_reason: string;
  tenant_display_name?: string | null;
  rental_contract_id?: number | null;
  contract_end_date?: string | null;
  rent_amount?: string | null;
}

// ---------------- Pending Rent Slips (printed before collection) ----------------
export interface PendingRentSlip {
  id: number;
  uuid: string;
  created_at: string;
  slip_number: string;
  tenant_id: number;
  tenant_name?: string | null;
  tenant_code?: string | null;
  property_id: number;
  building_name?: string | null;
  unit_number?: string | null;
  copy_type: "tenant" | "company";
  rental_month: string;
  expected_amount: string;
  slip_status: "pending" | "collected" | "cancelled";
  collected_transaction_id?: number | null;
  collected_at?: string | null;
  print_count: number;
}
export interface PendingRentSlipDashboard {
  total_slips: number;
  pending_count: number;
  collected_count: number;
  cancelled_count: number;
}
