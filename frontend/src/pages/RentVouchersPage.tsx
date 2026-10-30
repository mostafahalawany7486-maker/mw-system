import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, EmptyState, Modal, FormField } from "@/components/ui";
import { Loader2, Printer, FileStack, Eye, Receipt as ReceiptIcon } from "lucide-react";
import { RentVoucher, FinancialTransaction, PaginatedResponse, PropertyListItem } from "@/types";

// Groups the flat voucher list (tenant + company rows) back into pairs
// by transaction_id — this is what lets "Print Selected" always hand
// the print page a correctly ordered [tenant, company, tenant, company]
// id list (per spec's PAGE STRUCTURE) without the user having to think
// about ordering at all.
interface VoucherPair {
  transactionId: number;
  tenant?: RentVoucher;
  company?: RentVoucher;
}

function groupIntoPairs(vouchers: RentVoucher[]): VoucherPair[] {
  const byTxn = new Map<number, VoucherPair>();
  for (const v of vouchers) {
    const pair = byTxn.get(v.transaction_id) || { transactionId: v.transaction_id };
    if (v.copy_type === "tenant") pair.tenant = v; else pair.company = v;
    byTxn.set(v.transaction_id, pair);
  }
  return Array.from(byTxn.values());
}

export default function RentVouchersPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const canGenerate = hasPermission("rent_vouchers.create");

  const [data, setData] = useState<PaginatedResponse<RentVoucher> | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [selectedTxnIds, setSelectedTxnIds] = useState<Set<number>>(new Set());
  const [rentalMonth, setRentalMonth] = useState(""); // YYYY-MM-DD, first of month

  const load = useCallback(() => {
    setLoading(true);
    apiClient
      // A month filter is a "give me everything for this month" query,
      // not a paged browse — page_size bumped so grouping-by-building
      // below sees the whole month, not just the first page of it.
      .get<PaginatedResponse<RentVoucher>>("/rent-vouchers", { params: { page: rentalMonth ? 1 : page, page_size: rentalMonth ? 500 : 40, rental_month: rentalMonth || undefined } })
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false));
  }, [page, rentalMonth]);

  useEffect(() => { load(); }, [load]);

  const pairs = data ? groupIntoPairs(data.items) : [];

  // Building-Based Printing: when a Rental Month is selected, group that
  // month's voucher pairs by building so a whole building's vouchers can
  // be printed in one click — each building printed as its own separate
  // run (its own set of A4 pages), never mixed with another building's.
  const buildingGroups = (() => {
    if (!rentalMonth) return null;
    const groups = new Map<string, VoucherPair[]>();
    for (const pair of pairs) {
      const key = (pair.tenant || pair.company)?.building_name || "No building (standalone property)";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(pair);
    }
    // Guard, per request: never print two vouchers for the same tenant
    // in the same rental month within one building's "Print All" run —
    // if a tenant somehow ended up with more than one voucher pair for
    // this month (e.g. a correction payment created a second one),
    // only one prints; the rest are reported, not silently dropped.
    return Array.from(groups.entries()).map(([buildingName, groupPairs]) => {
      const seenTenants = new Map<string, VoucherPair>();
      let duplicatesSkipped = 0;
      for (const pair of groupPairs) {
        const tenantKey = (pair.tenant || pair.company)?.tenant_code;
        if (!tenantKey) { seenTenants.set(`__no_tenant_${pair.transactionId}`, pair); continue; }
        if (seenTenants.has(tenantKey)) { duplicatesSkipped++; continue; }
        seenTenants.set(tenantKey, pair);
      }
      return { buildingName, pairs: Array.from(seenTenants.values()), duplicatesSkipped };
    });
  })();

  const printPairs = (pairsToPrint: VoucherPair[]) => {
    const ids: number[] = [];
    for (const pair of pairsToPrint) {
      if (pair.tenant) ids.push(pair.tenant.id);
      if (pair.company) ids.push(pair.company.id);
    }
    if (ids.length === 0) return;
    navigate(`/rent-vouchers/print?ids=${ids.join(",")}`);
  };

  const toggleSelect = (transactionId: number) => {
    setSelectedTxnIds((prev) => {
      const next = new Set(prev);
      // No cap needed anymore — the print page now auto-splits into as
      // many 2-voucher A4 pages as needed (was capped at 2 pairs / 4
      // vouchers back when a page held a fixed 4 slots).
      if (next.has(transactionId)) next.delete(transactionId); else next.add(transactionId);
      return next;
    });
  };

  const printSelected = () => {
    printPairs(pairs.filter((p) => selectedTxnIds.has(p.transactionId)));
  };

  return (
    <div>
      <PageHeader
        title="Rent Vouchers"
        description="Bilingual Arabic/English rent payment vouchers — Tenant Copy and Company Copy, linked directly to the underlying payment transaction."
        action={canGenerate && (
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={() => navigate("/pending-rent-slips")}>
              <FileStack size={16} /> Pending Slips (Before Collection)
            </button>
            <button className="btn-secondary" onClick={() => navigate("/payments/collect-rent")}>
              <ReceiptIcon size={16} /> Collect Rent &amp; Print Voucher
            </button>
            <button className="btn-primary" onClick={() => setGenerateOpen(true)}>
              <FileStack size={16} /> Generate Vouchers
            </button>
          </div>
        )}
      />

      <div className="card mb-4">
        <div className="p-4 flex items-center gap-3 flex-wrap">
          <label className="text-sm text-ink-500 font-medium">Rental Month</label>
          <input
            type="month"
            className="input max-w-[160px]"
            value={rentalMonth ? rentalMonth.slice(0, 7) : ""}
            onChange={(e) => { setRentalMonth(e.target.value ? `${e.target.value}-01` : ""); setPage(1); }}
          />
          {rentalMonth && <button className="text-xs font-medium text-ink-500 hover:underline" onClick={() => setRentalMonth("")}>Clear</button>}
          <span className="text-xs text-ink-400">Pick a month to group that month's vouchers by building below, with one-click printing per building.</span>
        </div>
        {rentalMonth && buildingGroups && (
          <div className="border-t border-ink-100 dark:border-ink-800 divide-y divide-ink-50 dark:divide-ink-800/60">
            {buildingGroups.length === 0 && <div className="px-4 py-6 text-center text-sm text-ink-400">No vouchers for this month yet.</div>}
            {buildingGroups.map((g) => (
              <div key={g.buildingName} className="px-4 py-3 flex items-center justify-between flex-wrap gap-2">
                <div>
                  <p className="text-sm font-medium">{g.buildingName}</p>
                  <p className="text-xs text-ink-400">{g.pairs.length} tenant pair(s) — {g.pairs.length} A4 page(s)</p>
                  {g.duplicatesSkipped > 0 && (
                    <p className="text-xs text-amber-600 mt-0.5">{g.duplicatesSkipped} duplicate voucher(s) for the same tenant + month skipped — only one printed per tenant.</p>
                  )}
                </div>
                <button className="btn-secondary" onClick={() => printPairs(g.pairs)}>
                  <Printer size={15} /> Print All for This Building
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800 flex items-center justify-between flex-wrap gap-2">
          <span className="text-sm text-ink-500">Select rows to print together — each tenant's pair (their copy + the company's copy) prints as its own A4 page.</span>
          <button className="btn-secondary" onClick={printSelected} disabled={selectedTxnIds.size === 0}>
            <Printer size={16} /> Print Selected ({selectedTxnIds.size})
          </button>
        </div>

        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

        {!loading && pairs.length === 0 && (
          <EmptyState icon={ReceiptIcon} title="No rent vouchers yet" description="Use Generate Vouchers to create a Tenant + Company copy pair for a rent payment transaction." />
        )}

        {!loading && pairs.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr>
                  <th></th><th>Voucher #</th><th>Tenant</th><th>Property</th><th>Rental Month</th><th>Amount</th><th>Payment Method</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {pairs.map((pair) => {
                  const primary = pair.tenant || pair.company;
                  if (!primary) return null;
                  return (
                    <tr key={pair.transactionId}>
                      <td>
                        <input
                          type="checkbox"
                          className="w-4 h-4"
                          checked={selectedTxnIds.has(pair.transactionId)}
                          onChange={() => toggleSelect(pair.transactionId)}
                          disabled={!selectedTxnIds.has(pair.transactionId) && selectedTxnIds.size >= 2}
                        />
                      </td>
                      <td className="font-mono text-xs">{pair.tenant?.voucher_number} / {pair.company?.voucher_number}</td>
                      <td>{primary.tenant_name}</td>
                      <td>{[primary.building_name, primary.unit_number].filter(Boolean).join(" / ") || "—"}</td>
                      <td>{primary.rental_month?.slice(0, 7)}</td>
                      <td>{primary.amount ? Number(primary.amount).toLocaleString(undefined, { minimumFractionDigits: 3 }) : "—"}</td>
                      <td>{primary.payment_method_label_en || "—"}</td>
                      <td className="flex gap-1.5">
                        {pair.tenant && (
                          <a className="btn-secondary !px-2 !py-1" href={`/rent-vouchers/print?ids=${pair.tenant.id}`} target="_blank" rel="noreferrer" title="Preview tenant copy">
                            <Eye size={13} />
                          </a>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {data && <Pagination page={page} totalPages={Math.ceil(data.total / 40)} onChange={setPage} />}
      </div>

      {generateOpen && <GenerateVouchersModal onClose={() => setGenerateOpen(false)} onGenerated={load} />}
    </div>
  );
}

function GenerateVouchersModal({ onClose, onGenerated }: { onClose: () => void; onGenerated: () => void }) {
  const today = new Date();
  const [rentalMonth, setRentalMonth] = useState(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`);
  const [scopeId, setScopeId] = useState<string>("");
  const [properties, setProperties] = useState<PropertyListItem[]>([]);
  const [transactions, setTransactions] = useState<FinancialTransaction[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [combine, setCombine] = useState(false);
  const [loadingTxns, setLoadingTxns] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ created: number; existed: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Step 1: pick a property to scope by — a whole building (every one
  // of its units at once) or a single standalone unit, your choice.
  // Picking a building is what makes "just add the property and get
  // every receipt" possible instead of hunting down each tenant's
  // payment one at a time.
  useEffect(() => {
    apiClient.get<PaginatedResponse<PropertyListItem>>("/properties", { params: { page_size: 300 } })
      .then(({ data }) => setProperties(data.items.filter((p) => ["building", "villa", "commercial_building", "commercial_complex", "warehouse", "mixed_use", "apartment", "office", "commercial_unit", "shop"].includes(p.property_type))));
  }, []);
  const containerTypes = new Set(["building", "villa", "commercial_building", "commercial_complex", "warehouse", "mixed_use"]);
  const selectedIsBuilding = containerTypes.has(properties.find((p) => String(p.id) === scopeId)?.property_type || "");

  // Step 2: every eligible tenant rent payment under that scope — the
  // whole building's units at once if a building was picked (via
  // building_id, which the backend expands to that building + every
  // one of its units), or just the one unit otherwise. Every result is
  // selected by default — "generate all for this property" needs zero
  // extra clicks; deselecting one you don't want is still one click.
  const loadTransactions = useCallback(() => {
    setLoadingTxns(true);
    const params: any = { page: 1, page_size: 200, transaction_type: "tenant_payment" };
    if (scopeId) {
      if (selectedIsBuilding) params.building_id = scopeId; else params.property_id = scopeId;
    }
    apiClient.get<PaginatedResponse<FinancialTransaction>>("/financial/transactions", { params })
      .then(({ data }) => {
        setTransactions(data.items);
        setSelectedIds(new Set(data.items.map((t) => t.id)));
      })
      .finally(() => setLoadingTxns(false));
  }, [scopeId, selectedIsBuilding]);

  useEffect(() => { loadTransactions(); }, [loadTransactions]);

  const toggleTxn = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };
  const allSelected = transactions.length > 0 && selectedIds.size === transactions.length;
  const toggleSelectAll = () => setSelectedIds(allSelected ? new Set() : new Set(transactions.map((t) => t.id)));

  const submit = async () => {
    if (selectedIds.size === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      const [year, month] = rentalMonth.split("-");
      const { data } = await apiClient.post("/rent-vouchers/generate", {
        transaction_ids: Array.from(selectedIds),
        rental_month: `${year}-${month}-01`,
        combine,
      });
      setResult({ created: data.created_count, existed: data.already_existed_count });
      onGenerated();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not generate vouchers.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="Generate Rent Vouchers"
      footer={
        result ? (
          <button className="btn-primary" onClick={onClose}>Done</button>
        ) : (
          <>
            <button className="btn-secondary" onClick={onClose}>Cancel</button>
            <button className="btn-primary" onClick={submit} disabled={submitting || selectedIds.size === 0 || (combine && selectedIds.size < 2)}>
              {submitting ? <Loader2 size={16} className="animate-spin" /> : <FileStack size={16} />} {combine ? "Generate 1 Combined Voucher" : `Generate (${selectedIds.size})`}
            </button>
          </>
        )
      }
    >
      {result ? (
        <p className="text-sm text-ink-600">
          {result.created} voucher(s) generated{result.existed > 0 ? `, ${result.existed} already existed and were reused` : ""}.
          {combine ? " The selected payments were combined into a single Tenant Copy + Company Copy pair." : " Each selected payment produced a Tenant Copy + Company Copy pair."}
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          <FormField label="Rental Month" hint="Only the rental month is shown on the voucher — no from/to period.">
            <input type="month" className="input" value={rentalMonth} onChange={(e) => setRentalMonth(e.target.value)} />
          </FormField>

          <FormField label="Property" hint="Pick a whole building to pull in every one of its units' payments at once, or a single unit for just that one.">
            <select className="input" value={scopeId} onChange={(e) => setScopeId(e.target.value)}>
              <option value="">All properties</option>
              {properties.map((p) => (
                <option key={p.id} value={p.id}>
                  {containerTypes.has(p.property_type) ? "🏢 " : ""}{p.title}{p.unit_number ? ` — ${p.unit_number}` : ""}
                </option>
              ))}
            </select>
          </FormField>

          <FormField
            label="Payment Transaction(s)"
            hint={selectedIsBuilding ? "Every eligible payment across this building's units is selected — untick any you don't want." : "Select the tenant rent payment(s) to generate vouchers for."}
          >
            {loadingTxns ? (
              <div className="flex justify-center py-4"><Loader2 className="animate-spin text-ink-400" size={18} /></div>
            ) : transactions.length === 0 ? (
              <p className="text-sm text-ink-400">No tenant payment transactions found for this filter. A payment must be Verified (see the Payments page) before it can back a voucher.</p>
            ) : (
              <div className="border border-ink-100 dark:border-ink-800 rounded-md">
                <label className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-ink-500 border-b border-ink-100 dark:border-ink-800 cursor-pointer">
                  <input type="checkbox" className="w-4 h-4" checked={allSelected} onChange={toggleSelectAll} />
                  {allSelected ? "Deselect all" : "Select all"} ({transactions.length})
                </label>
                <div className="max-h-56 overflow-y-auto divide-y divide-ink-100 dark:divide-ink-800">
                  {transactions.map((t) => (
                    <label key={t.id} className="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800">
                      <input type="checkbox" className="w-4 h-4" checked={selectedIds.has(t.id)} onChange={() => toggleTxn(t.id)} />
                      <span className="font-mono text-xs text-ink-400">{t.transaction_number}</span>
                      <span>{t.tenant_display_name}</span>
                      <span className="ml-auto font-medium">{Number(t.amount).toLocaleString(undefined, { minimumFractionDigits: 3 })}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </FormField>

          {selectedIds.size >= 2 && (
            <label className="flex items-start gap-2 text-sm cursor-pointer">
              <input type="checkbox" className="w-4 h-4 mt-0.5" checked={combine} onChange={(e) => setCombine(e.target.checked)} />
              <span>
                Combine the {selectedIds.size} selected payments into <strong>one voucher</strong> (their total amount, one printed period covering that many months) instead of one voucher per payment.
                <span className="block text-xs text-ink-400 mt-0.5">All selected payments must be for the same tenant.</span>
              </span>
            </label>
          )}

          {error && <p className="text-xs text-rust-500">{error}</p>}
        </div>
      )}
    </Modal>
  );
}
