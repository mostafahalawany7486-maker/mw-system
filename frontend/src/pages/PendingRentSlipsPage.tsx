import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, EmptyState, Modal, FormField } from "@/components/ui";
import { Loader2, Printer, FileStack, CheckCircle2, XCircle, Receipt as ReceiptIcon } from "lucide-react";
import { PendingRentSlip, PendingRentSlipDashboard, PropertyListItem, RentalContractListItem, FinancialAccount, PaginatedResponse } from "@/types";

// Groups the flat slip list (tenant + company rows) back into pairs by
// (tenant_id, property_id, rental_month) — same idea as RentVouchersPage's
// groupIntoPairs, so "Print" always hands the print page a correctly
// ordered [tenant, company] id list for one A4 page.
interface SlipPair {
  key: string;
  tenant?: PendingRentSlip;
  company?: PendingRentSlip;
}
function groupIntoPairs(slips: PendingRentSlip[]): SlipPair[] {
  const byKey = new Map<string, SlipPair>();
  for (const s of slips) {
    const key = `${s.tenant_id}-${s.property_id}-${s.rental_month}`;
    const pair = byKey.get(key) || { key };
    if (s.copy_type === "tenant") pair.tenant = s; else pair.company = s;
    byKey.set(key, pair);
  }
  return Array.from(byKey.values());
}

const STATUS_TONE: Record<string, string> = { pending: "badge-warn", collected: "badge-active", cancelled: "badge-inactive" };

export default function PendingRentSlipsPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const canGenerate = hasPermission("rent_vouchers.create");
  const canConfirm = hasPermission("financial.create");

  const [data, setData] = useState<PaginatedResponse<PendingRentSlip> | null>(null);
  const [dashboard, setDashboard] = useState<PendingRentSlipDashboard | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [confirmTarget, setConfirmTarget] = useState<SlipPair | null>(null);
  const [rentalMonth, setRentalMonth] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<PaginatedResponse<PendingRentSlip>>("/pending-rent-slips", { params: { page, page_size: 60, rental_month: rentalMonth || undefined } })
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false));
  }, [page, rentalMonth]);

  const loadDashboard = useCallback(() => {
    apiClient.get<PendingRentSlipDashboard>("/pending-rent-slips/dashboard/summary").then(({ data }) => setDashboard(data));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadDashboard(); }, [loadDashboard, data]);

  const pairs = data ? groupIntoPairs(data.items) : [];

  const printPair = (pair: SlipPair) => {
    const ids: number[] = [];
    if (pair.tenant) ids.push(pair.tenant.id);
    if (pair.company) ids.push(pair.company.id);
    if (ids.length === 0) return;
    navigate(`/rent-vouchers/print?ids=${ids.join(",")}&source=pending`);
  };

  return (
    <div>
      <PageHeader
        title="Pending Rent Slips"
        description="Printed at the start of the month, before collection — identical to a real Rent Voucher, but creates no transaction until you confirm collection actually happened."
        action={canGenerate && (
          <button className="btn-primary" onClick={() => setGenerateOpen(true)}>
            <FileStack size={16} /> Generate Slips
          </button>
        )}
      />

      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="card p-4">
          <span className="text-xs font-medium text-ink-500">Pending</span>
          <div className="font-display text-2xl font-bold text-amber-600">{dashboard ? dashboard.pending_count : "—"}</div>
        </div>
        <div className="card p-4">
          <span className="text-xs font-medium text-ink-500">Collected</span>
          <div className="font-display text-2xl font-bold text-emerald-600">{dashboard ? dashboard.collected_count : "—"}</div>
        </div>
        <div className="card p-4">
          <span className="text-xs font-medium text-ink-500">Cancelled</span>
          <div className="font-display text-2xl font-bold text-ink-400">{dashboard ? dashboard.cancelled_count : "—"}</div>
        </div>
      </div>

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800 flex items-center gap-3">
          <label className="text-sm text-ink-500 font-medium">Rental Month</label>
          <input type="month" className="input max-w-[160px]" value={rentalMonth ? rentalMonth.slice(0, 7) : ""}
            onChange={(e) => { setRentalMonth(e.target.value ? `${e.target.value}-01` : ""); setPage(1); }} />
        </div>

        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

        {!loading && pairs.length === 0 && (
          <EmptyState icon={ReceiptIcon} title="No pending rent slips" description="Use Generate Slips to create printable slips for a building before collection." />
        )}

        {!loading && pairs.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr><th>Slip #</th><th>Tenant</th><th>Property</th><th>Rental Month</th><th>Expected Amount</th><th>Status</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {pairs.map((pair) => {
                  const primary = pair.tenant || pair.company;
                  if (!primary) return null;
                  const status = primary.slip_status;
                  return (
                    <tr key={pair.key}>
                      <td className="font-mono text-xs">{primary.slip_number}</td>
                      <td>{primary.tenant_name}</td>
                      <td>{primary.building_name}{primary.unit_number ? ` · Unit ${primary.unit_number}` : ""}</td>
                      <td>{primary.rental_month}</td>
                      <td>{Number(primary.expected_amount).toLocaleString()}</td>
                      <td><span className={STATUS_TONE[status] || "badge-inactive"}>{status}</span></td>
                      <td className="whitespace-nowrap">
                        <button className="text-xs font-medium text-brand-600 dark:text-brand-400 hover:underline mr-3" onClick={() => printPair(pair)}>
                          <Printer size={13} className="inline -mt-0.5 mr-1" /> Print
                        </button>
                        {status === "pending" && canConfirm && (
                          <button className="text-xs font-medium text-emerald-600 hover:underline" onClick={() => setConfirmTarget(pair)}>
                            <CheckCircle2 size={13} className="inline -mt-0.5 mr-1" /> Confirm Collection
                          </button>
                        )}
                        {status === "collected" && primary.collected_transaction_id && (
                          <span className="text-xs text-ink-400">Transaction #{primary.collected_transaction_id}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />}
      </div>

      {generateOpen && <GenerateSlipsModal onClose={() => setGenerateOpen(false)} onGenerated={() => { setGenerateOpen(false); load(); loadDashboard(); }} />}
      {confirmTarget && (
        <ConfirmCollectionModal
          pair={confirmTarget}
          onClose={() => setConfirmTarget(null)}
          onConfirmed={(voucherIds) => {
            setConfirmTarget(null);
            load();
            loadDashboard();
            if (voucherIds.length) navigate(`/rent-vouchers/print?ids=${voucherIds.join(",")}`);
          }}
        />
      )}
    </div>
  );
}

function GenerateSlipsModal({ onClose, onGenerated }: { onClose: () => void; onGenerated: () => void }) {
  const [buildings, setBuildings] = useState<PropertyListItem[]>([]);
  const [buildingId, setBuildingId] = useState<number | "">("");
  const [rentalMonth, setRentalMonth] = useState(() => {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
  });
  const [contracts, setContracts] = useState<RentalContractListItem[]>([]);
  const [loadingContracts, setLoadingContracts] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ created_count: number; already_existed_count: number } | null>(null);

  useEffect(() => {
    apiClient.get<PaginatedResponse<PropertyListItem>>("/properties", { params: { top_level_only: true, page_size: 200 } })
      .then(({ data }) => setBuildings(data.items)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!buildingId) { setContracts([]); return; }
    setLoadingContracts(true);
    apiClient.get<PaginatedResponse<RentalContractListItem>>("/rentals", { params: { building_id: buildingId, contract_status: "active", page_size: 200 } })
      .then(({ data }) => setContracts(data.items))
      .finally(() => setLoadingContracts(false));
  }, [buildingId]);

  const handleGenerate = async () => {
    if (!buildingId || contracts.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      const { data } = await apiClient.post("/pending-rent-slips/generate", {
        rental_month: rentalMonth,
        entries: contracts.map((c) => ({ tenant_id: c.tenant_id, property_id: c.property_id, expected_amount: c.rent_amount })),
      });
      setResult({ created_count: data.created_count, already_existed_count: data.already_existed_count });
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to generate slips for this building.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="Generate Pending Rent Slips"
      footer={
        result ? (
          <button className="btn-primary" onClick={onGenerated}>Done</button>
        ) : (
          <>
            <button className="btn-secondary" onClick={onClose}>Cancel</button>
            <button className="btn-primary" disabled={saving || !buildingId || contracts.length === 0} onClick={handleGenerate}>
              {saving && <Loader2 size={14} className="animate-spin" />} Generate for {contracts.length} tenant(s)
            </button>
          </>
        )
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      {result ? (
        <div className="flex items-start gap-2 text-sm text-emerald-600 bg-emerald-50 dark:bg-emerald-500/10 rounded-md px-3 py-2.5">
          <CheckCircle2 size={16} className="shrink-0 mt-0.5" />
          <span>{result.created_count} new slip(s) created{result.already_existed_count > 0 ? `, ${result.already_existed_count} already existed for this month and were left as-is` : ""}.</span>
        </div>
      ) : (
        <div className="space-y-4">
          <FormField label="Building" required>
            <select className="input" value={buildingId} onChange={(e) => setBuildingId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Select a building…</option>
              {buildings.map((b) => <option key={b.id} value={b.id}>{b.property_code} — {b.title}</option>)}
            </select>
          </FormField>
          <FormField label="Rental Month" required>
            <input className="input" type="month" value={rentalMonth.slice(0, 7)} onChange={(e) => setRentalMonth(`${e.target.value}-01`)} />
          </FormField>
          {loadingContracts && <div className="text-xs text-ink-400 flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> Loading active tenants…</div>}
          {!loadingContracts && buildingId && (
            <p className="text-xs text-ink-400">
              {contracts.length === 0 ? "No active rental contracts found for this building." : `Will create a slip pair (tenant + company copy) for ${contracts.length} active tenant(s), using each one's current rent amount.`}
            </p>
          )}
        </div>
      )}
    </Modal>
  );
}

function ConfirmCollectionModal({ pair, onClose, onConfirmed }: { pair: SlipPair; onClose: () => void; onConfirmed: (voucherIds: number[]) => void }) {
  const primary = pair.tenant || pair.company;
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [accountId, setAccountId] = useState<number | "">("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().slice(0, 10));
  const [referenceNumber, setReferenceNumber] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient.get<PaginatedResponse<FinancialAccount>>("/financial/accounts", { params: { page_size: 100 } })
      .then(({ data }) => { setAccounts(data.items); if (data.items.length) setAccountId(data.items.find((a) => a.is_default)?.id ?? data.items[0].id); });
  }, []);

  const handleConfirm = async () => {
    if (!primary || !accountId) return;
    setSaving(true);
    setError(null);
    try {
      const anchorId = (pair.tenant || pair.company)!.id;
      const { data } = await apiClient.post(`/pending-rent-slips/${anchorId}/confirm-collection`, {
        account_id: Number(accountId), payment_method: paymentMethod, payment_date: paymentDate, reference_number: referenceNumber || undefined,
      });
      onConfirmed(data.voucher_ids || []);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to confirm collection.");
    } finally {
      setSaving(false);
    }
  };

  if (!primary) return null;

  return (
    <Modal
      open
      onClose={onClose}
      title={`Confirm Collection — ${primary.tenant_name}`}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" disabled={saving} onClick={handleConfirm}>
            {saving && <Loader2 size={14} className="animate-spin" />} Confirm — Amount {Number(primary.expected_amount).toLocaleString()}
          </button>
        </>
      }
    >
      {error && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{error}</div>}
      <p className="text-sm text-ink-500 mb-4">This records the real payment transaction and generates the official Rent Voucher — only do this once the guard has confirmed the tenant actually paid.</p>
      <div className="space-y-4">
        <FormField label="Account" required>
          <select className="input" value={accountId} onChange={(e) => setAccountId(Number(e.target.value))}>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.account_code} — {a.name}</option>)}
          </select>
        </FormField>
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Payment Method">
            <select className="input" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank Transfer</option>
              <option value="cheque">Cheque</option>
              <option value="card">Card</option>
              <option value="online">Online</option>
              <option value="knet">K-Net</option>
            </select>
          </FormField>
          <FormField label="Payment Date">
            <input className="input" type="date" value={paymentDate} onChange={(e) => setPaymentDate(e.target.value)} />
          </FormField>
        </div>
        <FormField label="Reference Number" hint="Optional">
          <input className="input" value={referenceNumber} onChange={(e) => setReferenceNumber(e.target.value)} />
        </FormField>
      </div>
    </Modal>
  );
}
