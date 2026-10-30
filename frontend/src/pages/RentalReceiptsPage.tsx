import { useEffect, useState, useCallback } from "react";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, EmptyState, ToolbarSearch, Modal, FormField } from "@/components/ui";
import { Loader2, Printer, CheckCircle2, CalendarPlus, Receipt as ReceiptIcon } from "lucide-react";
import { RentalReceiptSearchItem, PaginatedResponse, FinancialAccount } from "@/types";

const STATUS_TONE: Record<string, string> = {
  pending: "badge-warn", paid: "badge-active", overdue: "badge-inactive", cancelled: "badge-inactive",
};

export default function RentalReceiptsPage() {
  const { hasPermission } = useAuth();
  const [data, setData] = useState<PaginatedResponse<RentalReceiptSearchItem> | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [confirmTarget, setConfirmTarget] = useState<RentalReceiptSearchItem | null>(null);

  const canGenerate = hasPermission("rentals.create");
  const canConfirm = hasPermission("financial.edit");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<PaginatedResponse<RentalReceiptSearchItem>>("/rentals/receipts/search", {
      params: { page, page_size: 20, receipt_number: search || undefined },
    }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [page, search]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <PageHeader
        title="Rental Receipts"
        description="Monthly rental receipts — generated before payment, confirmed after. Printing never changes payment status; only Confirm Payment does."
        action={canGenerate && (
          <button className="btn-primary" onClick={() => setGenerateOpen(true)}>
            <CalendarPlus size={16} /> Generate Monthly Receipts
          </button>
        )}
      />

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800 flex flex-wrap gap-3 items-center">
          <ToolbarSearch value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search by receipt number…" />
        </div>

        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

        {!loading && data && data.items.length === 0 && (
          <EmptyState icon={ReceiptIcon} title="No rental receipts yet" description="Use Generate Monthly Receipts to prepare this month's receipts for active leases." />
        )}

        {!loading && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr>
                  <th>Receipt #</th><th>Tenant</th><th>Property</th><th>Rental Month</th><th>Amount</th><th>Status</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.installment_id}>
                    <td className="font-mono text-xs">{r.receipt_number}</td>
                    <td>{r.tenant_display_name}</td>
                    <td>{r.property_title}{r.unit_number ? ` · Unit ${r.unit_number}` : ""}</td>
                    <td>{r.due_date.slice(0, 7)}</td>
                    <td>{Number(r.amount).toLocaleString(undefined, { minimumFractionDigits: 3 })}</td>
                    <td><span className={STATUS_TONE[r.payment_status] || "badge-inactive"}>{r.payment_status}</span></td>
                    <td className="flex gap-1.5">
                      <a className="btn-secondary !px-2 !py-1" href={`/rentals/receipts/${r.installment_id}/print?copy=tenant`} target="_blank" rel="noreferrer" title="Print tenant copy">
                        <Printer size={13} />
                      </a>
                      {canConfirm && r.payment_status !== "paid" && (
                        <button className="btn-secondary !px-2 !py-1 text-brand-600" title="Confirm payment" onClick={() => setConfirmTarget(r)}>
                          <CheckCircle2 size={13} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {data && <Pagination page={page} totalPages={Math.ceil(data.total / 20)} onChange={setPage} />}
      </div>

      {generateOpen && <GenerateReceiptsModal onClose={() => setGenerateOpen(false)} onGenerated={load} />}
      {confirmTarget && <ConfirmPaymentModal item={confirmTarget} onClose={() => setConfirmTarget(null)} onConfirmed={load} />}
    </div>
  );
}

function GenerateReceiptsModal({ onClose, onGenerated }: { onClose: () => void; onGenerated: () => void }) {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<number | null>(null);

  const submit = async () => {
    setSubmitting(true);
    try {
      const { data } = await apiClient.post("/rentals/receipts/generate-monthly", { year, month });
      setResult(data.length);
      onGenerated();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Generate Monthly Receipts" footer={
      <>
        <button className="btn-secondary" onClick={onClose}>Close</button>
        {result === null && <button className="btn-primary" onClick={submit} disabled={submitting}>{submitting ? <Loader2 size={16} className="animate-spin" /> : <CalendarPlus size={16} />} Generate</button>}
      </>
    }>
      {result !== null ? (
        <div className="text-center py-4">
          <CheckCircle2 size={32} className="text-brand-500 mx-auto mb-2" />
          <p className="text-sm">{result} receipt{result === 1 ? "" : "s"} generated for {year}-{String(month).padStart(2, "0")}.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Year"><input className="input" type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} /></FormField>
          <FormField label="Month"><input className="input" type="number" min={1} max={12} value={month} onChange={(e) => setMonth(Number(e.target.value))} /></FormField>
          <p className="col-span-2 text-xs text-ink-400">
            Assigns a receipt number to every installment due this month for an active lease that doesn't already have one. Safe to run more than once — already-numbered receipts are skipped.
          </p>
        </div>
      )}
    </Modal>
  );
}

function ConfirmPaymentModal({ item, onClose, onConfirmed }: { item: RentalReceiptSearchItem; onClose: () => void; onConfirmed: () => void }) {
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [accountId, setAccountId] = useState<number | "">("");
  const [paymentMethod, setPaymentMethod] = useState("bank_transfer");
  const [referenceNumber, setReferenceNumber] = useState("");
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient.get<PaginatedResponse<FinancialAccount>>("/financial/accounts", { params: { page_size: 100 } })
      .then(({ data }) => setAccounts(data.items));
  }, []);

  const submit = async () => {
    if (!accountId) { setError("Select which account received the payment."); return; }
    setSubmitting(true);
    setError("");
    try {
      await apiClient.post(`/rentals/installments/${item.installment_id}/confirm-payment`, {
        account_id: accountId, payment_method: paymentMethod, reference_number: referenceNumber || undefined,
        transaction_date: transactionDate, notes: notes || undefined,
      });
      onConfirmed();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to confirm payment.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={`Confirm Payment — ${item.receipt_number}`} footer={
      <>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={submit} disabled={submitting}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />} Confirm Payment
        </button>
      </>
    }>
      <div className="space-y-3">
        <p className="text-xs text-ink-400 bg-ink-50 dark:bg-ink-800/60 rounded-md p-2">
          Only confirm once you have the signed company copy and payment proof (K-NET slip, bank reference, or cheque) in hand — this is the one action that makes the payment official.
        </p>
        {error && <p className="text-xs text-rust-500">{error}</p>}
        <FormField label="Amount" hint="From the receipt — not editable here.">
          <input className="input" value={Number(item.amount).toLocaleString(undefined, { minimumFractionDigits: 3 })} disabled />
        </FormField>
        <FormField label="Received Into Account" required>
          <select className="input" value={accountId} onChange={(e) => setAccountId(Number(e.target.value))}>
            <option value="">Select account…</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </FormField>
        <FormField label="Payment Method" required>
          <select className="input" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
            <option value="cash">Cash</option>
            <option value="bank_transfer">Bank Transfer</option>
            <option value="cheque">Cheque</option>
            <option value="knet">K-NET</option>
          </select>
        </FormField>
        <FormField
          label="Reference Number"
          hint={paymentMethod === "bank_transfer" ? "Include the bank name, e.g. \"NBK — TRF20394\"" : paymentMethod === "cheque" ? "Cheque number" : paymentMethod === "knet" ? "K-NET transaction reference" : undefined}
        >
          <input className="input" value={referenceNumber} onChange={(e) => setReferenceNumber(e.target.value)} />
        </FormField>
        <FormField label="Payment Date" required>
          <input className="input" type="date" value={transactionDate} onChange={(e) => setTransactionDate(e.target.value)} />
        </FormField>
        <FormField label="Notes (internal only)">
          <textarea className="input" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </FormField>
      </div>
    </Modal>
  );
}
