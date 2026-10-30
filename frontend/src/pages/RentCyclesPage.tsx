import { useEffect, useState, useCallback } from "react";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, EmptyState, Modal, FormField } from "@/components/ui";
import { Loader2, Plus, PlayCircle, Lock, Unlock, Ban, CalendarClock, TrendingUp, Receipt as ReceiptIcon } from "lucide-react";
import { RentCycle, RentCycleDashboard, RentCycleGenerateResult, PaginatedResponse } from "@/types";

const STATUS_TONE: Record<string, string> = {
  draft: "badge-inactive", generated: "badge-warn", printed: "badge-warn", distributed: "badge-warn",
  collecting: "badge-warn", partially_collected: "badge-warn", completed: "badge-active",
  closed: "badge-active", cancelled: "badge-inactive",
};

function money(v: string | number) {
  return Number(v).toLocaleString(undefined, { minimumFractionDigits: 3 });
}

export default function RentCyclesPage() {
  const { hasPermission, user } = useAuth();
  const canCreate = hasPermission("rent_cycles.create");
  const canEdit = hasPermission("rent_cycles.edit");

  const [dashboard, setDashboard] = useState<RentCycleDashboard | null>(null);
  const [data, setData] = useState<PaginatedResponse<RentCycle> | null>(null);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiClient.get<RentCycleDashboard>("/rent-cycles/dashboard/summary"),
      apiClient.get<PaginatedResponse<RentCycle>>("/rent-cycles", { params: { page, page_size: 20, cycle_status: statusFilter || undefined } }),
    ]).then(([d, c]) => { setDashboard(d.data); setData(c.data); }).finally(() => setLoading(false));
  }, [page, statusFilter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <PageHeader
        title="Rent Cycles"
        description="The monthly rent collection cycle — generates invoices and receipts for every active lease, then tracks collection through to close."
        action={canCreate && (
          <button className="btn-primary" onClick={() => setCreateOpen(true)}>
            <Plus size={16} /> Create Cycle
          </button>
        )}
      />

      {dashboard && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <SummaryCard icon={CalendarClock} label="Open Cycles" value={String(dashboard.open_cycles)} />
          <SummaryCard icon={ReceiptIcon} label="Receipts (Current Cycle)" value={String(dashboard.total_receipts)} />
          <SummaryCard icon={TrendingUp} label="Expected Income (Current)" value={money(dashboard.total_expected_income)} />
          <SummaryCard icon={TrendingUp} label="Collection Progress" value={`${money(dashboard.collection_progress_percent)}%`} />
        </div>
      )}

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800 flex flex-wrap gap-3 items-center">
          <select className="input max-w-[200px]" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            {Object.keys(STATUS_TONE).map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
          </select>
        </div>

        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

        {!loading && data && data.items.length === 0 && (
          <EmptyState icon={CalendarClock} title="No rent cycles yet" description="Create a cycle for a given month, then Generate to create invoices and receipts for every active lease." />
        )}

        {!loading && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr><th>Cycle #</th><th>Period</th><th>Start</th><th>Due</th><th>Status</th></tr>
              </thead>
              <tbody>
                {data.items.map((c) => (
                  <tr key={c.id} className="cursor-pointer" onClick={() => setDetailId(c.id)}>
                    <td className="font-mono text-xs">{c.cycle_number}</td>
                    <td className="font-medium">{c.year}-{String(c.month).padStart(2, "0")}</td>
                    <td className="text-ink-500">{c.start_date}</td>
                    <td className="text-ink-500">{c.due_date}</td>
                    <td><span className={STATUS_TONE[c.cycle_status] || "badge-inactive"}>{c.cycle_status.replace(/_/g, " ")}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {data && <Pagination page={page} totalPages={Math.ceil(data.total / 20)} onChange={setPage} />}
      </div>

      {createOpen && <CreateCycleModal onClose={() => setCreateOpen(false)} onCreated={(id) => { load(); setCreateOpen(false); setDetailId(id); }} />}
      {detailId !== null && (
        <CycleDetailModal
          cycleId={detailId} canEdit={canEdit} isSuperuser={!!user?.is_superuser}
          onClose={() => setDetailId(null)} onChanged={load}
        />
      )}
    </div>
  );
}

function SummaryCard({ icon: Icon, label, value }: { icon: typeof CalendarClock; label: string; value: string }) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-1.5 text-ink-500"><Icon size={14} /><p className="text-xs">{label}</p></div>
      <p className="text-lg font-display font-bold mt-1">{value}</p>
    </div>
  );
}

function CreateCycleModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: number) => void }) {
  const today = new Date();
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [year, setYear] = useState(today.getFullYear());
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setSubmitting(true);
    setError("");
    try {
      const { data } = await apiClient.post<RentCycle>("/rent-cycles", { month, year, notes: notes || undefined });
      onCreated(data.id);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not create this cycle — a cycle for this period may already exist.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Create Rent Cycle" footer={
      <>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={submit} disabled={submitting}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />} Create
        </button>
      </>
    }>
      <div className="space-y-3">
        <p className="text-xs text-ink-400 bg-ink-50 dark:bg-ink-800/60 rounded-md p-2">
          Start/due dates default to the 1st of the month and 15 days later — you can generate the cycle right after creating it.
        </p>
        {error && <p className="text-xs text-rust-500">{error}</p>}
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Month" required>
            <select className="input" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </FormField>
          <FormField label="Year" required>
            <input className="input" type="number" value={year} onChange={(e) => setYear(Number(e.target.value))} />
          </FormField>
        </div>
        <FormField label="Notes">
          <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </FormField>
      </div>
    </Modal>
  );
}

function CycleDetailModal({
  cycleId, canEdit, isSuperuser, onClose, onChanged,
}: { cycleId: number; canEdit: boolean; isSuperuser: boolean; onClose: () => void; onChanged: () => void }) {
  const [cycle, setCycle] = useState<RentCycle | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RentCycleGenerateResult | null>(null);
  const [error, setError] = useState("");
  const [actionOpen, setActionOpen] = useState<"close" | "cancel" | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<RentCycle>(`/rent-cycles/${cycleId}`).then(({ data }) => setCycle(data)).finally(() => setLoading(false));
  }, [cycleId]);

  useEffect(() => { load(); }, [load]);

  const generate = async (force = false) => {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const { data } = await apiClient.post<RentCycleGenerateResult>(`/rent-cycles/${cycleId}/generate`, { force });
      setResult(data);
      setCycle(data.cycle);
      onChanged();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not generate this cycle.");
    } finally {
      setBusy(false);
    }
  };

  const reopen = async () => {
    setBusy(true);
    setError("");
    try {
      await apiClient.post(`/rent-cycles/${cycleId}/reopen`);
      load();
      onChanged();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not reopen this cycle.");
    } finally {
      setBusy(false);
    }
  };

  if (loading || !cycle) {
    return <Modal open onClose={onClose} title="Rent Cycle"><div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div></Modal>;
  }

  const alreadyGenerated = cycle.cycle_status !== "draft";
  const isTerminal = cycle.cycle_status === "closed" || cycle.cycle_status === "cancelled";

  return (
    <Modal open onClose={onClose} title={`Rent Cycle ${cycle.cycle_number}`} footer={<button className="btn-secondary" onClick={onClose}>Close</button>}>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className={STATUS_TONE[cycle.cycle_status] || "badge-inactive"}>{cycle.cycle_status.replace(/_/g, " ")}</span>
          <span className="text-sm text-ink-500">{cycle.year}-{String(cycle.month).padStart(2, "0")} · Due {cycle.due_date}</span>
        </div>

        {error && <p className="text-xs text-rust-500">{error}</p>}
        {result && (
          <p className="text-xs text-brand-600 bg-brand-50 dark:bg-brand-500/10 rounded-md p-2">
            {result.message} ({result.invoices_generated} invoice(s), {result.receipts_generated} receipt(s))
          </p>
        )}

        {canEdit && !isTerminal && (
          <div className="flex flex-wrap gap-2">
            {!alreadyGenerated && (
              <button className="btn-primary" onClick={() => generate(false)} disabled={busy}>
                {busy ? <Loader2 size={15} className="animate-spin" /> : <PlayCircle size={15} />} Generate
              </button>
            )}
            {alreadyGenerated && isSuperuser && (
              <button className="btn-secondary" onClick={() => generate(true)} disabled={busy} title="Administrator override — regenerates">
                <PlayCircle size={15} /> Regenerate (Admin)
              </button>
            )}
            {["collecting", "partially_collected", "completed"].includes(cycle.cycle_status) && (
              <button className="btn-secondary" onClick={() => setActionOpen("close")} disabled={busy}>
                <Lock size={15} /> Close
              </button>
            )}
            {cycle.cycle_status === "closed" && (
              <button className="btn-secondary" onClick={reopen} disabled={busy}>
                <Unlock size={15} /> Reopen
              </button>
            )}
            <button className="btn-secondary text-rust-500" onClick={() => setActionOpen("cancel")} disabled={busy}>
              <Ban size={15} /> Cancel
            </button>
          </div>
        )}

        <div>
          <p className="text-xs text-ink-400 mb-1">Records ({cycle.records.length})</p>
          {cycle.records.length === 0 ? (
            <p className="text-sm text-ink-400 py-2">No records yet — Generate this cycle to create invoices and receipts for every active lease.</p>
          ) : (
            <div className="border border-ink-100 dark:border-ink-800 rounded-md divide-y divide-ink-100 dark:divide-ink-800 max-h-64 overflow-y-auto">
              {cycle.records.map((r) => (
                <div key={r.id} className="flex items-center justify-between px-3 py-2 text-sm">
                  <div>
                    <p className="font-medium">{r.tenant_display_name}</p>
                    <p className="text-xs text-ink-400">{r.property_title}{r.unit_number ? ` · Unit ${r.unit_number}` : ""}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-medium">{money(r.amount)}</p>
                    <p className={`text-xs ${r.record_status === "failed" ? "text-rust-500" : "text-ink-400"}`}>{r.invoice_status || r.record_status}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {cycle.notes && <div><p className="text-xs text-ink-400">Notes</p><p className="text-sm">{cycle.notes}</p></div>}
        {cycle.cancellation_reason && <div><p className="text-xs text-ink-400">Cancellation Reason</p><p className="text-sm">{cycle.cancellation_reason}</p></div>}
      </div>

      {actionOpen && (
        <CycleActionModal
          cycleId={cycleId} action={actionOpen} onClose={() => setActionOpen(null)}
          onDone={() => { setActionOpen(null); load(); onChanged(); }}
        />
      )}
    </Modal>
  );
}

function CycleActionModal({ cycleId, action, onClose, onDone }: { cycleId: number; action: "close" | "cancel"; onClose: () => void; onDone: () => void }) {
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    if (action === "cancel" && !text.trim()) { setError("A reason is required to cancel a cycle."); return; }
    setSubmitting(true);
    setError("");
    try {
      if (action === "close") await apiClient.post(`/rent-cycles/${cycleId}/close`, { notes: text || undefined });
      else await apiClient.post(`/rent-cycles/${cycleId}/cancel`, { reason: text });
      onDone();
    } catch (err: any) {
      setError(err?.response?.data?.detail || `Could not ${action} this cycle.`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={action === "close" ? "Close Cycle" : "Cancel Cycle"} footer={
      <>
        <button className="btn-secondary" onClick={onClose}>Back</button>
        <button className="btn-primary" onClick={submit} disabled={submitting}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : null} Confirm
        </button>
      </>
    }>
      <div className="space-y-3">
        {error && <p className="text-xs text-rust-500">{error}</p>}
        <FormField label={action === "close" ? "Closing Notes" : "Cancellation Reason"} required={action === "cancel"}>
          <input className="input" value={text} onChange={(e) => setText(e.target.value)} />
        </FormField>
      </div>
    </Modal>
  );
}
