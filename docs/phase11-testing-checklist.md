# Phase 11 — Reports: Testing Checklist

Legend: [ ] not tested · [x] pass · [!] fail (log in Bug Checklist)

Prerequisite: Phases 1–10 running. **No new migration** — Phase 11 adds
no persisted tables; everything is computed live from existing data. Run
`python seed.py` as usual for baseline data (existing sample properties,
tenants, owners, transactions from Phases 1–10 are enough to exercise
every report).

## 1. Permissions & Setup
- [ ] `python seed.py` registers the `reports` module — Administrator (all), Branch Manager (`reports.view`), Staff (`reports.view`)
- [ ] All 10 endpoints require authentication (401 without a token)
- [ ] No new database tables or migration — confirm `alembic upgrade head` shows no pending revision beyond `0010`

## 2. Financial Reports (`GET /reports/financial`)
- [ ] Without date params, defaults to "this month to date"
- [ ] `total_income` and `total_expense` reflect Phase 8 transactions of the relevant types within the range
- [ ] `net_cash_flow == total_income - total_expense`
- [ ] `total_outstanding_tenant`/`total_outstanding_owner` match Phase 8's outstanding-balance figures
- [ ] `collection_rate_percentage` reflects paid vs. total-due Rental Payment Installments due within the range
- [ ] `transactions_by_type` sums correctly per type with accurate counts

## 3. Tenant Reports (`GET /reports/tenants`)
- [ ] Counts (`total_tenants`, `individual_tenants`, `company_tenants`, `blacklisted_tenants`) match the Tenant table
- [ ] `top_tenants_by_payment` correctly ranks tenants by `tenant_payment` transaction totals within the date range
- [ ] `outstanding_tenants` matches Phase 8's tenant outstanding-balance logic
- [ ] `contracts_expiring_soon` counts active Rental Contracts ending within 30 days
- [ ] `average_rating` is `null` when no TenantRating records exist, not an error

## 4. Owner Reports (`GET /reports/owners`)
- [ ] Counts match the Owner table
- [ ] `top_owners_by_properties` correctly counts properties per owner
- [ ] `outstanding_owners` matches Phase 8's owner outstanding-balance logic
- [ ] `total_paid_to_owners` sums `owner_payment` transactions within the range

## 5. Property Reports (`GET /reports/properties`)
- [ ] `by_type` and `by_availability` counts sum to `total_properties`
- [ ] `top_properties_by_revenue` correctly attributes income transactions to properties — either via `Transaction.property_id` directly, or resolved through `rental_contract_id → RentalContract.property_id` when `property_id` wasn't set directly

## 6. Vacancy Reports (`GET /reports/vacancy`)
- [ ] `vacant_count + leased_count + other_count == total_properties`
- [ ] `property_type == "building"` rows are **excluded** from all vacancy math (buildings are parent containers per Phase 4/5, not directly leasable units)
- [ ] `vacant_properties` list shows only `availability_status == "available"` properties, with `days_vacant` computed from the most recent rental contract's `end_date` (or `created_at` if the property has never been rented)
- [ ] `vacancy_rate_percentage` is between 0 and 100

## 7. Occupancy Reports (`GET /reports/occupancy`)
- [ ] `overall_occupancy_rate_percentage` matches `leased_count / total_properties` from the Vacancy report (same underlying counts, same building exclusion)
- [ ] `by_property_type` breaks down occupancy per type, each between 0–100%
- [ ] `trend` returns exactly `months` data points (default 6, configurable via `?months=`)
- [ ] Trend is a simplified approximation — documented clearly as using **current** property counts against historical contract date ranges, not true historical property-count snapshots (which aren't tracked)

## 8. Income Reports (`GET /reports/income`)
- [ ] `total_income` matches the Financial report's income figure for the same range
- [ ] `by_category` groups by `category` when set, falling back to `transaction_type` when not — verify both cases
- [ ] `by_property` correctly attributes and sorts by amount descending
- [ ] `trend` always returns exactly 6 months regardless of data presence (zero-filled where no income exists)

## 9. Expense Reports (`GET /reports/expenses`)
- [ ] `total_expense` (Financial transactions) and `total_maintenance_cost` (Phase 9 materials + labor) are reported **separately**, not summed — documented in the UI to avoid double-counting confusion, since maintenance costs may or may not already be recorded as Financial expense transactions depending on how each request was invoiced
- [ ] `by_category` and `by_property` behave the same as Income's equivalents
- [ ] `trend` always returns exactly 6 months

## 10. Profit Reports (`GET /reports/profit`)
- [ ] `net_profit == total_income - total_expense`
- [ ] `profit_margin_percentage == net_profit / total_income * 100` (0 when there's no income, not a division error)
- [ ] `by_property` merges income and expense per property correctly, even when a property has income but no expense (or vice versa) — sorted by profit descending
- [ ] `trend` merges the 6-month income and expense trends into per-month profit figures

## 11. Dashboard Analytics (`GET /reports/analytics/dashboard`)
- [ ] `kpis.net_profit_this_month == kpis.total_income_this_month - kpis.total_expense_this_month`
- [ ] `kpis.vacancy_rate_percentage` matches the Vacancy report
- [ ] `kpis.active_rental_contracts`/`active_lease_agreements`/`open_maintenance_requests` match their respective module counts
- [ ] `monthly_trend` covers the same 6-month window as the Profit report's trend
- [ ] `top_properties_by_revenue` covers the last 6 months

## 12. Cross-report consistency
- [ ] Financial report's `total_income`/`total_expense` for a given range match Income/Expense report totals for the same range
- [ ] Profit report's totals equal Income total minus Expense total for the same range
- [ ] Vacancy and Occupancy reports agree on total/leased/vacant counts

## 13. Permissions
- [ ] Staff and Branch Manager can view all reports (read-only business intelligence, consistent with their existing `financial.view` access from Phase 8)
- [ ] No role can create/edit/delete anything under Reports — every endpoint is a GET

## 14. Automated tests
- [ ] `pytest backend/tests/test_reports.py` passes all cases (all 10 report categories, cross-checks like net_cash_flow/net_profit computation, building-exclusion in vacancy, category/property attribution, dashboard KPI consistency, and the auth requirement)
