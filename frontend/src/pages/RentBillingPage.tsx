import { useEffect, useState, useCallback } from "react";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, EmptyState, ToolbarSearch, Modal, FormField } from "@/components/ui";
import { Loader2, Printer, CalendarPlus, CheckCircle2, XCircle, FileWarning, FileText } from "lucide-react";
import { Invoice, PaginatedResponse } from "@/types";

const STATUS_TONE: Record<string, string> = {
  draft: "badge-inactive", sent: "badge-warn", paid: "badge-active",
  partially_paid: "badge-warn", overdue: "badge-inactive", cancelled: "badge-inactive", void: "badge-inactive",
};

export default function RentBillingPage() {
  const { hasPermission } = useAuth();
  const [data, setData] = useState<PaginatedResponse<Invoice> | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [voidTarget, setVoidTarget] = useState<Invoice | null>(null);

  const canCreate = hasPermission("financial.create");
  const canEdit = hasPermission("financial.edit");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<PaginatedResponse<Invoice>>("/financial/invoices/search", {
      params: { page, page_size: 20, invoice_number: search || undefined, invoice_status: statusFilter || undefined },
    }).then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [page, search, statusFilter]);

  useEffect(() => { load(); }, [load]);

  const toggleSelected = (id: number) => {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  };

  const bulkApprove = async () => {
    if (selected.length === 0) return;
    await apiClient.post("/financial/invoices/bulk-approve", { invoice_ids: selected });
    setSelected([]);
    load();
  };

  const bulkPrint = () => {
    if (selected.length === 0) return;
    selected.forEach((id) => window.open(`/financial/invoices/${id}/print?copy=tenant`, "_blank"));
  };

  return (
    <div>
      <PageHeader
        title="Rent Billing"
        description="Generate, approve, print, and track rent invoices — separate from Payment Receipts, which are only issued after payment."
        action={canCreate && (
          <button className="btn-primary" onClick={() => setGenerateOpen(true)}>
            <CalendarPlus size={16} /> Generate Invoices
          </button>
        )}
      />

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800 flex flex-wrap gap-3 items-center justify-between">
          <div className="flex flex-wrap gap-3 items-center">
            <ToolbarSearch value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search by invoice number…" />
            <select className="input max-w-[160px]" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
              <option value="">All statuses</option>
              <option value="draft">Draft</option>
              <option value="sent">Sent</option>
              <option value="paid">Paid</option>
              <option value="partially_paid">Partially Paid</option>
              <option value="overdue">Overdue</option>
              <option value="cancelled">Cancelled</option>
              <option value="void">Void</option>
            </select>
          </div>
          {selected.length > 0 && (
            <div className="flex gap-2 items-center">
              <span className="text-xs text-ink-500">{selected.length} selected</span>
              {canEdit && <button className="btn-secondary !px-3 !py-1.5 text-xs" onClick={bulkApprove}><CheckCircle2 size={13} /> Approve</button>}
              <button className="btn-secondary !px-3 !py-1.5 text-xs" onClick={bulkPrint}><Printer size={13} /> Print Selected</button>
            </div>
          )}
        </div>

        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

        {!loading && data && data.items.length === 0 && (
          <EmptyState icon={FileText} title="No invoices yet" description="Use Generate Invoices to bill active leases for the current period." />
        )}

        {!loading && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr>
                  <th></th><th>Invoice #</th><th>Tenant</th><th>Property</th><th>Due</th><th>Amount</th><th>Outstanding</th><th>Status</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((inv) => (
                  <tr key={inv.id}>
                    <td><input type="checkbox" checked={selected.includes(inv.id)} onChange={() => toggleSelected(inv.id)} /></td>
                    <td className="font-mono text-xs">{inv.invoice_number}</td>
                    <td>{inv.tenant_display_name}</td>
                    <td>{inv.property_title}{inv.unit_number ? ` · Unit ${inv.unit_number}` : ""}</td>
                    <td className={inv.is_overdue ? "text-rust-500 font-medium" : ""}>{inv.due_date}</td>
                    <td>{Number(inv.amount).toLocaleString(undefined, { minimumFractionDigits: 3 })}</td>
                    <td>{Number(inv.outstanding_amount).toLocaleString(undefined, { minimumFractionDigits: 3 })}</td>
                    <td><span className={STATUS_TONE[inv.invoice_status] || "badge-inactive"}>{inv.invoice_status.replace(/_/g, " ")}</span></td>
                    <td className="flex gap-1.5">
                      <a className="btn-secondary !px-2 !py-1" href={`/financial/invoices/${inv.id}/print?copy=tenant`} target="_blank" rel="noreferrer" title="Print">
                        <Printer size={13} />
                      </a>
                      {canEdit && !["paid", "void", "cancelled"].includes(inv.invoice_status) && (
                        <button className="btn-secondary !px-2 !py-1 text-rust-500" title="Void" onClick={() => setVoidTarget(inv)}>
                          <XCircle size={13} />
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

      {generateOpen && <GenerateInvoicesModal onClose={() => setGenerateOpen(false)} onGenerated={load} />}
      {voidTarget && <VoidInvoiceModal invoice={voidTarget} onClose={() => setVoidTarget(null)} onVoided={load} />}
    </div>
  );
}

function GenerateInvoicesModal({ onClose, onGenerated }: { onClose: () => void; onGenerated: () => void }) {
  const [periodStart, setPeriodStart] = useState(new Date().toISOString().slice(0, 8) + "01");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<number | null>(null);

  const submit = async () => {
    setSubmitting(true);
    try {
      const { data } = await apiClient.post("/financial/invoices/bulk-generate", { billing_period_start: periodStart });
      setResult(data.length);
      onGenerated();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Generate Invoices" footer={
      <>
        <button className="btn-secondary" onClick={onClose}>Close</button>
        {result === null && <button className="btn-primary" onClick={submit} disabled={submitting}>{submitting ? <Loader2 size={16} className="animate-spin" /> : <CalendarPlus size={16} />} Generate</button>}
      </>
    }>
      {result !== null ? (
        <div className="text-center py-4">
          <CheckCircle2 size={32} className="text-brand-500 mx-auto mb-2" />
          <p className="text-sm">{result} invoice{result === 1 ? "" : "s"} generated as drafts.</p>
        </div>
      ) : (
        <div className="space-y-3">
          <FormField label="Billing Period Start" hint="Each active lease is billed using its own cycle (monthly, quarterly, etc.) starting from this date.">
            <input className="input" type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
          </FormField>
          <p className="text-xs text-ink-400">
            Generates one draft invoice per active lease that doesn't already have one for this exact period. Safe to run more than once.
          </p>
        </div>
      )}
    </Modal>
  );
}

function VoidInvoiceModal({ invoice, onClose, onVoided }: { invoice: Invoice; onClose: () => void; onVoided: () => void }) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!reason.trim()) { setError("A reason is required to void an invoice."); return; }
    setSubmitting(true);
    setError("");
    try {
      await apiClient.post(`/financial/invoices/${invoice.id}/void`, { reason });
      onVoided();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to void this invoice.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={`Void Invoice — ${invoice.invoice_number}`} footer={
      <>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-danger" onClick={submit} disabled={submitting}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <FileWarning size={16} />} Void Invoice
        </button>
      </>
    }>
      <div className="space-y-3">
        <p className="text-xs text-ink-400 bg-ink-50 dark:bg-ink-800/60 rounded-md p-2">
          Invoices are never deleted — voiding permanently marks this one invalid while keeping it on record for audit purposes.
        </p>
        {error && <p className="text-xs text-rust-500">{error}</p>}
        <FormField label="Reason" required>
          <textarea className="input" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Generated in error, duplicate billing period" />
        </FormField>
      </div>
    </Modal>
  );
}
