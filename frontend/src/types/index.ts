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
