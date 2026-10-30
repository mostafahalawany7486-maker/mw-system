import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { PageHeader } from "@/components/ui";
import PropertyHierarchySelector from "@/components/PropertyHierarchySelector";
import TenantFormModal from "@/components/TenantFormModal";
import {
  Loader2, ArrowLeft, ArrowRight, Check, CheckCircle2, AlertCircle, User, Building2,
  FileSignature, Wallet, ClipboardCheck, PartyPopper, Plus, Search,
} from "lucide-react";
import { PropertyListItem, TenantListItem, FinancialAccount, PaginatedResponse } from "@/types";

/**
 * New Lease Wizard — a UI-only feature. Every step reuses an existing
 * endpoint/component exactly as-is (PropertyHierarchySelector for step
 * 1, TenantFormModal for "create new tenant" in step 2, the same
 * POST /rentals -> /activate -> /installments/generate ->
 * /installments/{id}/confirm-payment -> /rent-vouchers/generate
 * sequence CollectRentPage and RentalFormModal already use elsewhere).
 * Nothing here is a new business rule or a new table — it's a guided
 * front end for work that was already possible across several pages.
 * The old multi-page flow (Contracts -> Add Contract, Payment
 * Schedule tab -> Auto-Generate, Rent Collection) is completely
 * untouched and still works exactly as before.
 */

const STEPS = [
  { key: "property", label: "Property", icon: Building2 },
  { key: "tenant", label: "Tenant", icon: User },
  { key: "contract", label: "Contract", icon: FileSignature },
  { key: "payment", label: "Initial Payment", icon: Wallet },
  { key: "review", label: "Review", icon: ClipboardCheck },
] as const;

const FREQUENCY_MONTHS: Record<string, number> = { monthly: 1, quarterly: 3, semi_annual: 6, annual: 12 };
const FREQUENCY_LABELS: Record<string, string> = { monthly: "per month", quarterly: "per quarter", semi_annual: "per 6 months", annual: "per year" };

const DRAFT_KEY = "new_lease_wizard_draft";

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}
function addMonths(dateStr: string, months: number) {
  const d = new Date(dateStr);
  d.setMonth(d.getMonth() + months);
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
}

export default function NewLeaseWizardPage() {
  const navigate = useNavigate();

  const [stepIndex, setStepIndex] = useState(0);
  const [ownerId, setOwnerId] = useState<number | "">("");
  const [selectedUnit, setSelectedUnit] = useState<PropertyListItem | null>(null);

  const [selectedTenant, setSelectedTenant] = useState<TenantListItem | null>(null);
  const [tenantSearch, setTenantSearch] = useState("");
  const [tenants, setTenants] = useState<TenantListItem[]>([]);
  const [tenantsLoading, setTenantsLoading] = useState(false);
  const [tenantModalOpen, setTenantModalOpen] = useState(false);

  const [contractForm, setContractForm] = useState({
    start_date: todayStr(),
    end_date: addMonths(todayStr(), 12),
    rent_amount: "",
    payment_frequency: "monthly",
    security_deposit_amount: "",
    notes_summary: "",
  });

  const [wantsPayment, setWantsPayment] = useState<boolean | null>(null);
  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [paymentForm, setPaymentForm] = useState({ account_id: "" as number | "", payment_method: "knet", reference_number: "" });

  const [submitting, setSubmitting] = useState(false);
  const [submitStage, setSubmitStage] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<{ contractId: number; voucherIds: number[] } | null>(null);

  // Auto-save draft — property/tenant selections involve live objects
  // that don't survive JSON round-trips meaningfully, so only the
  // plain-value contract form and current step are restored; picking
  // the property/tenant again takes a few seconds and is far safer
  // than silently resurrecting a stale unit/tenant reference.
  useEffect(() => {
    try {
      const saved = localStorage.getItem(DRAFT_KEY);
      if (saved) {
        const draft = JSON.parse(saved);
        if (draft.contractForm) setContractForm(draft.contractForm);
      }
    } catch { /* ignore */ }
  }, []);
  useEffect(() => {
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify({ contractForm })); } catch { /* ignore */ }
  }, [contractForm]);

  useEffect(() => {
    apiClient.get<PaginatedResponse<FinancialAccount>>("/financial/accounts", { params: { page_size: 100 } })
      .then(({ data }) => { setAccounts(data.items); if (data.items.length) setPaymentForm((f) => ({ ...f, account_id: data.items.find((a) => a.is_default)?.id ?? data.items[0].id })); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (stepIndex !== 1) return;
    const handle = setTimeout(() => {
      setTenantsLoading(true);
      apiClient.get<PaginatedResponse<TenantListItem>>("/tenants", { params: { search: tenantSearch || undefined, page_size: 10 } })
        .then(({ data }) => setTenants(data.items))
        .finally(() => setTenantsLoading(false));
    }, 300);
    return () => clearTimeout(handle);
  }, [tenantSearch, stepIndex]);

  const scheduleEstimate = useCallback(() => {
    if (!contractForm.start_date || !contractForm.end_date || !contractForm.rent_amount) return null;
    const start = new Date(contractForm.start_date);
    const end = new Date(contractForm.end_date);
    const stepMonths = FREQUENCY_MONTHS[contractForm.payment_frequency] || 1;
    let count = 0;
    let cursor = new Date(start);
    while (cursor <= end) { count++; cursor.setMonth(cursor.getMonth() + stepMonths); }
    return { count, total: count * Number(contractForm.rent_amount) };
  }, [contractForm]);

  const canAdvance = (): boolean => {
    switch (STEPS[stepIndex].key) {
      case "property": return !!selectedUnit;
      case "tenant": return !!selectedTenant;
      case "contract": return !!(contractForm.start_date && contractForm.end_date && Number(contractForm.rent_amount) > 0);
      case "payment": return wantsPayment !== null && (!wantsPayment || !!paymentForm.account_id);
      default: return true;
    }
  };

  const goNext = () => { if (canAdvance() && stepIndex < STEPS.length - 1) setStepIndex((i) => i + 1); };
  const goBack = () => { if (stepIndex > 0) setStepIndex((i) => i - 1); };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !(e.target as HTMLElement).matches("textarea")) { e.preventDefault(); if (canAdvance()) goNext(); }
  };

  const handleFinish = async () => {
    if (!selectedUnit || !selectedTenant) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      setSubmitStage("Creating contract…");
      const { data: contract } = await apiClient.post("/rentals", {
        tenant_id: selectedTenant.id,
        property_id: selectedUnit.id,
        start_date: contractForm.start_date,
        end_date: contractForm.end_date,
        rent_amount: Number(contractForm.rent_amount),
        payment_frequency: contractForm.payment_frequency,
        security_deposit_amount: contractForm.security_deposit_amount ? Number(contractForm.security_deposit_amount) : 0,
        notes_summary: contractForm.notes_summary || undefined,
      });

      setSubmitStage("Activating contract…");
      await apiClient.post(`/rentals/${contract.id}/activate`);

      setSubmitStage("Generating payment schedule…");
      const { data: installments } = await apiClient.post(`/rentals/${contract.id}/installments/generate`, {});

      let voucherIds: number[] = [];
      if (wantsPayment && installments.length > 0) {
        const first = installments[0];
        setSubmitStage("Recording first payment…");
        const { data: confirmed } = await apiClient.post(`/rentals/installments/${first.id}/confirm-payment`, {
          account_id: Number(paymentForm.account_id),
          payment_method: paymentForm.payment_method,
          reference_number: paymentForm.reference_number || undefined,
          transaction_date: todayStr(),
        });
        setSubmitStage("Generating receipt…");
        const { data: voucherResult } = await apiClient.post("/rent-vouchers/generate", {
          transaction_ids: [confirmed.transaction_id],
          rental_month: contractForm.start_date,
        });
        voucherIds = voucherResult.vouchers.map((v: any) => v.id);
      }

      try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
      setResult({ contractId: contract.id, voucherIds });
    } catch (err: any) {
      setSubmitError(err?.response?.data?.detail || "Something went wrong — check what was already created under Contracts before retrying.");
    } finally {
      setSubmitting(false);
      setSubmitStage("");
    }
  };

  const resetWizard = () => {
    setStepIndex(0);
    setSelectedUnit(null);
    setSelectedTenant(null);
    setContractForm({ start_date: todayStr(), end_date: addMonths(todayStr(), 12), rent_amount: "", payment_frequency: "monthly", security_deposit_amount: "", notes_summary: "" });
    setWantsPayment(null);
    setResult(null);
    setSubmitError(null);
  };

  // ==================== Success screen (Step 6 + Smart Navigation) ====================
  if (result) {
    return (
      <div className="max-w-xl mx-auto text-center py-10 animate-fade-in-up">
        <div className="mx-auto mb-4 w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center">
          <PartyPopper className="text-emerald-500" size={30} />
        </div>
        <h2 className="font-display text-xl font-bold mb-1">Lease created</h2>
        <p className="text-sm text-ink-500 mb-6">{selectedTenant?.display_name} is now on an active contract for {selectedUnit?.unit_number ? `Unit ${selectedUnit.unit_number}` : selectedUnit?.title}.</p>
        <div className="grid grid-cols-2 gap-2 max-w-sm mx-auto">
          <button className="btn-primary col-span-2" onClick={() => navigate(`/rentals/${result.contractId}`)}>View Contract</button>
          <button className="btn-secondary" onClick={() => navigate(`/tenants/${selectedTenant?.id}`)}>View Tenant</button>
          <button className="btn-secondary" onClick={() => navigate(`/properties/${selectedUnit?.id}`)}>View Unit</button>
          {result.voucherIds.length > 0 && (
            <button className="btn-secondary col-span-2" onClick={() => navigate(`/rent-vouchers/print?ids=${result.voucherIds.join(",")}`)}>Print Receipt</button>
          )}
          <button className="btn-secondary" onClick={resetWizard}>Create Another</button>
          <button className="btn-secondary" onClick={() => navigate("/dashboard")}>Return to Dashboard</button>
        </div>
      </div>
    );
  }

  const estimate = scheduleEstimate();

  return (
    <div className="max-w-2xl mx-auto" onKeyDown={handleKeyDown}>
      <button className="flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-100 mb-4" onClick={() => navigate("/rentals")}>
        <ArrowLeft size={15} /> Back to Contracts
      </button>
      <PageHeader title="New Lease Wizard" description="Set up a tenant's contract, schedule, and first payment in one guided flow." />

      {/* Progress indicator */}
      <div className="flex items-center mb-6">
        {STEPS.map((s, i) => (
          <div key={s.key} className="flex items-center flex-1 last:flex-none">
            <div className={`flex items-center justify-center w-8 h-8 rounded-full text-xs font-semibold shrink-0 transition-colors ${
              i < stepIndex ? "bg-emerald-500 text-white" : i === stepIndex ? "bg-brand-500 text-white" : "bg-ink-100 dark:bg-ink-800 text-ink-400"
            }`}>
              {i < stepIndex ? <Check size={14} /> : i + 1}
            </div>
            <span className={`text-xs ml-1.5 mr-1 hidden sm:inline whitespace-nowrap ${i === stepIndex ? "font-semibold text-ink-800 dark:text-ink-100" : "text-ink-400"}`}>{s.label}</span>
            {i < STEPS.length - 1 && <div className={`flex-1 h-0.5 mx-1 ${i < stepIndex ? "bg-emerald-500" : "bg-ink-100 dark:bg-ink-800"}`} />}
          </div>
        ))}
      </div>

      <div className="card p-5 min-h-[22rem]">
        {/* ---------- Step 1: Property ---------- */}
        {STEPS[stepIndex].key === "property" && (
          <div className="animate-fade-in-up">
            <h3 className="font-display font-semibold mb-4">Which unit is this lease for?</h3>
            <PropertyHierarchySelector ownerId={ownerId} onOwnerChange={setOwnerId} onUnitSelect={setSelectedUnit} allowWholeFloorChoice />
          </div>
        )}

        {/* ---------- Step 2: Tenant ---------- */}
        {STEPS[stepIndex].key === "tenant" && (
          <div className="animate-fade-in-up">
            <h3 className="font-display font-semibold mb-4">Who's the tenant?</h3>
            {selectedTenant ? (
              <div className="flex items-center justify-between rounded-lg border border-ink-100 dark:border-ink-800 px-4 py-3">
                <div>
                  <div className="font-medium text-sm">{selectedTenant.display_name}</div>
                  <div className="text-xs text-ink-400">{selectedTenant.tenant_code}</div>
                </div>
                <button className="text-xs font-medium text-brand-600 dark:text-brand-400 hover:underline" onClick={() => setSelectedTenant(null)}>Change</button>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="relative">
                  <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
                  <input className="input pl-9" placeholder="Search existing tenant by name, code, phone…" value={tenantSearch} onChange={(e) => setTenantSearch(e.target.value)} />
                </div>
                {tenantsLoading && <div className="text-xs text-ink-400 flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> Searching…</div>}
                {!tenantsLoading && tenants.length > 0 && (
                  <div className="border border-ink-100 dark:border-ink-800 rounded-lg divide-y divide-ink-100 dark:divide-ink-800 max-h-48 overflow-y-auto">
                    {tenants.map((t) => (
                      <button key={t.id} type="button" className="w-full text-left px-3 py-2 text-sm hover:bg-ink-50 dark:hover:bg-ink-800/50" onClick={() => setSelectedTenant(t)}>
                        <div className="font-medium">{t.display_name}</div>
                        <div className="text-xs text-ink-400">{t.tenant_code}{t.primary_phone ? ` · ${t.primary_phone}` : ""}</div>
                      </button>
                    ))}
                  </div>
                )}
                <button className="btn-secondary w-full justify-center" onClick={() => setTenantModalOpen(true)}>
                  <Plus size={15} /> Create New Tenant
                </button>
              </div>
            )}
          </div>
        )}

        {/* ---------- Step 3: Contract ---------- */}
        {STEPS[stepIndex].key === "contract" && (
          <div className="animate-fade-in-up space-y-4">
            <h3 className="font-display font-semibold mb-1">Contract terms</h3>
            <p className="text-xs text-ink-400">A contract number is assigned automatically once you finish — nothing to fill in here.</p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Start Date *</label>
                <input className="input" type="date" value={contractForm.start_date} onChange={(e) => setContractForm((f) => ({ ...f, start_date: e.target.value }))} />
              </div>
              <div>
                <label className="label">End Date *</label>
                <input className="input" type="date" value={contractForm.end_date} onChange={(e) => setContractForm((f) => ({ ...f, end_date: e.target.value }))} />
              </div>
              <div>
                <label className="label">Monthly Rent {FREQUENCY_LABELS[contractForm.payment_frequency] ? `(${FREQUENCY_LABELS[contractForm.payment_frequency]}) ` : ""}*</label>
                <input className="input" type="number" min="0" step="0.001" value={contractForm.rent_amount} onChange={(e) => setContractForm((f) => ({ ...f, rent_amount: e.target.value }))} />
              </div>
              <div>
                <label className="label">Payment Frequency</label>
                <select className="input" value={contractForm.payment_frequency} onChange={(e) => setContractForm((f) => ({ ...f, payment_frequency: e.target.value }))}>
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="semi_annual">Semi-Annual</option>
                  <option value="annual">Annual</option>
                </select>
              </div>
              <div className="col-span-2">
                <label className="label">Security Deposit</label>
                <input className="input" type="number" min="0" step="0.001" value={contractForm.security_deposit_amount} onChange={(e) => setContractForm((f) => ({ ...f, security_deposit_amount: e.target.value }))} />
              </div>
              <div className="col-span-2">
                <label className="label">Notes</label>
                <textarea className="input" rows={2} value={contractForm.notes_summary} onChange={(e) => setContractForm((f) => ({ ...f, notes_summary: e.target.value }))} />
              </div>
            </div>
            {estimate && (
              <p className="text-xs text-ink-400">
                {estimate.count} installment(s) of {Number(contractForm.rent_amount).toLocaleString()} each ≈ <strong>{estimate.total.toLocaleString()}</strong> total over the contract's full term.
              </p>
            )}
          </div>
        )}

        {/* ---------- Step 4: Initial Payment ---------- */}
        {STEPS[stepIndex].key === "payment" && (
          <div className="animate-fade-in-up space-y-4">
            <h3 className="font-display font-semibold mb-1">First payment</h3>
            <p className="text-xs text-ink-400 mb-3">Optional — you can always collect the first month later from Rent Collection instead.</p>
            <div className="grid grid-cols-2 gap-3">
              <button className={`card p-4 text-left border-2 transition-colors ${wantsPayment === false ? "border-brand-500" : "border-transparent"}`} onClick={() => setWantsPayment(false)}>
                <div className="font-medium text-sm">Skip</div>
                <div className="text-xs text-ink-400 mt-0.5">Collect rent later</div>
              </button>
              <button className={`card p-4 text-left border-2 transition-colors ${wantsPayment === true ? "border-brand-500" : "border-transparent"}`} onClick={() => setWantsPayment(true)}>
                <div className="font-medium text-sm">Receive First Payment</div>
                <div className="text-xs text-ink-400 mt-0.5">Record it right now</div>
              </button>
            </div>
            {wantsPayment && (
              <div className="grid grid-cols-2 gap-4 pt-2">
                <div>
                  <label className="label">Account *</label>
                  <select className="input" value={paymentForm.account_id} onChange={(e) => setPaymentForm((f) => ({ ...f, account_id: Number(e.target.value) }))}>
                    {accounts.map((a) => <option key={a.id} value={a.id}>{a.account_code} — {a.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Payment Method</label>
                  <select className="input" value={paymentForm.payment_method} onChange={(e) => setPaymentForm((f) => ({ ...f, payment_method: e.target.value }))}>
                    <option value="knet">K-Net</option>
                    <option value="cash">Cash</option>
                    <option value="bank_transfer">Bank Transfer</option>
                    <option value="cheque">Cheque</option>
                    <option value="card">Card</option>
                    <option value="online">Online</option>
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="label">Reference Number</label>
                  <input className="input" value={paymentForm.reference_number} onChange={(e) => setPaymentForm((f) => ({ ...f, reference_number: e.target.value }))} placeholder="Cheque #, transfer ref, etc. (optional)" />
                </div>
              </div>
            )}
          </div>
        )}

        {/* ---------- Step 5: Review ---------- */}
        {STEPS[stepIndex].key === "review" && (
          <div className="animate-fade-in-up space-y-3">
            <h3 className="font-display font-semibold mb-1">Review before saving</h3>
            <p className="text-xs text-ink-400 mb-3">Nothing is created until you press Finish below.</p>
            <div className="rounded-lg border border-ink-100 dark:border-ink-800 divide-y divide-ink-100 dark:divide-ink-800 text-sm">
              <ReviewRow label="Property" value={selectedUnit ? `${selectedUnit.property_code} — ${selectedUnit.unit_number ? `Unit ${selectedUnit.unit_number}` : selectedUnit.title}` : "—"} />
              <ReviewRow label="Tenant" value={selectedTenant?.display_name || "—"} />
              <ReviewRow label="Term" value={`${contractForm.start_date} → ${contractForm.end_date}`} />
              <ReviewRow label="Rent" value={`${Number(contractForm.rent_amount || 0).toLocaleString()} ${FREQUENCY_LABELS[contractForm.payment_frequency] || ""}`} />
              <ReviewRow label="Deposit" value={contractForm.security_deposit_amount ? Number(contractForm.security_deposit_amount).toLocaleString() : "None"} />
              <ReviewRow label="First Payment" value={wantsPayment ? `Yes — ${accounts.find((a) => a.id === paymentForm.account_id)?.name || ""}, ${paymentForm.payment_method}` : "Skipped — collect later"} />
            </div>
            {submitError && (
              <div className="flex items-start gap-2 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">
                <AlertCircle size={15} className="shrink-0 mt-0.5" /> <span>{submitError}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Previous / Next / Finish */}
      <div className="flex items-center justify-between mt-4">
        <button className="btn-secondary" disabled={stepIndex === 0 || submitting} onClick={goBack}>
          <ArrowLeft size={15} /> Previous
        </button>
        {STEPS[stepIndex].key === "review" ? (
          <button className="btn-primary" disabled={submitting} onClick={handleFinish}>
            {submitting ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
            {submitting ? submitStage : "Finish"}
          </button>
        ) : (
          <button className="btn-primary" disabled={!canAdvance()} onClick={goNext}>
            Next <ArrowRight size={15} />
          </button>
        )}
      </div>

      <TenantFormModal
        open={tenantModalOpen}
        onClose={() => setTenantModalOpen(false)}
        onSaved={(tenant) => { setSelectedTenant(tenant as any); setTenantModalOpen(false); }}
      />
    </div>
  );
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-4 py-2.5">
      <span className="text-ink-400">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
