import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, FormField } from "@/components/ui";
import { Loader2, ArrowLeft, CheckCircle2, AlertCircle, CalendarClock } from "lucide-react";
import { TenantListItem, FinancialAccount, PaginatedResponse, RentalInstallment } from "@/types";

// This page ORCHESTRATES already-existing, already-working endpoints
// (POST /rentals/installments/{id}/confirm-payment or, as a fallback,
// POST /financial/transactions, then POST /rent-vouchers/generate),
// then hands off to the existing RentVoucherPrintPage.
//
// The "Full (with invoice)" path that used to exist here was removed
// following a confirmed architecture decision: the Rent Billing
// Engine's Invoice system and the Rent Cycle Engine's
// RentalPaymentInstallment schedule were two separate, never-
// reconciled ways of tracking "what's due, when" for the same
// contract. Rent Cycles — what this page, the dashboard's outstanding
// totals, and every recent fix in this codebase are actually built on
// — won out. See FinancialPage.tsx's TABS comment and README.md for
// the full reasoning. The Invoice backend code and any historical
// Invoice data are untouched; only this page's UI was simplified.

const PAYMENT_METHODS = ["cash", "bank_transfer", "cheque", "card", "online", "knet"];

function firstOfCurrentMonth(): string {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}
function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

type Step = "" | "creating_transaction" | "generating_vouchers";

const STEP_LABELS: Record<Step, string> = {
  "": "",
  creating_transaction: "Recording payment transaction…",
  generating_vouchers: "Generating rent voucher…",
};

export default function CollectRentPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();

  const [tenantSearch, setTenantSearch] = useState("");
  const [tenants, setTenants] = useState<TenantListItem[]>([]);
  const [selectedTenant, setSelectedTenant] = useState<TenantListItem | null>(null);
  const [tenantsLoading, setTenantsLoading] = useState(false);

  // Building filter — confirmed directly: with more buildings and
  // tenants coming, picking a building first narrows the tenant search
  // down instead of searching the whole portfolio by name every time.
  const [buildings, setBuildings] = useState<{ id: number; title: string; property_code: string }[]>([]);
  const [buildingFilter, setBuildingFilter] = useState<number | "">("");

  useEffect(() => {
    apiClient.get<PaginatedResponse<{ id: number; title: string; property_code: string }>>("/properties", { params: { top_level_only: true, page_size: 200 } })
      .then(({ data }) => setBuildings(data.items))
      .catch(() => {});
  }, []);

  const [accounts, setAccounts] = useState<FinancialAccount[]>([]);
  const [accountsLoaded, setAccountsLoaded] = useState(false);
  const [accountId, setAccountId] = useState<number | "">("");
  const [paymentMethod, setPaymentMethod] = useState("knet");
  const [paymentDate, setPaymentDate] = useState(todayStr());
  const [referenceNumber, setReferenceNumber] = useState("");
  const [amount, setAmount] = useState("");
  const [rentalMonth, setRentalMonth] = useState(firstOfCurrentMonth());

  // Which pending installment (if any) this payment is for — added
  // specifically to stop the same month being collectable twice. See
  // the module comment above and README.md for the full history.
  const [pendingInstallments, setPendingInstallments] = useState<RentalInstallment[]>([]);
  const [loadingInstallments, setLoadingInstallments] = useState(false);
  const [installmentsLoadError, setInstallmentsLoadError] = useState<string | null>(null);
  const [selectedInstallmentId, setSelectedInstallmentId] = useState<number | "" | "other">("");

  // A tenant with more than one active contract used to be a dead end
  // here — a warning telling the user to go pick a contract from the
  // Contracts page instead. Now the contracts are listed right here so
  // the whole flow (tenant → contract → installment → payment) stays on
  // one page, per request ("نعم المستاجر لديه عقدين").
  const [contractChoices, setContractChoices] = useState<{
    id: number; contract_number: string; unit_number: string | null; property_title: string | null; rent_amount: string;
  }[]>([]);
  const [selectedContractId, setSelectedContractId] = useState<number | "">("");

  const [step, setStep] = useState<Step>("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canAct = hasPermission("financial.create") && hasPermission("rent_vouchers.create");

  useEffect(() => {
    apiClient.get<PaginatedResponse<FinancialAccount>>("/financial/accounts", { params: { page_size: 100 } })
      .then(({ data }) => { setAccounts(data.items); if (data.items.length) setAccountId(data.items.find((a) => a.is_default)?.id ?? data.items[0].id); })
      .finally(() => setAccountsLoaded(true));
  }, []);

  useEffect(() => {
    const handle = setTimeout(() => {
      setTenantsLoading(true);
      apiClient.get<PaginatedResponse<TenantListItem>>("/tenants", { params: { search: tenantSearch || undefined, building_id: buildingFilter || undefined, page_size: 15 } })
        .then(({ data }) => setTenants(data.items))
        .finally(() => setTenantsLoading(false));
    }, 300);
    return () => clearTimeout(handle);
  }, [tenantSearch, buildingFilter]);

  const loadInstallmentsForContract = useCallback((contractId: number) => {
    setLoadingInstallments(true);
    setSelectedInstallmentId("");
    setInstallmentsLoadError(null);
    apiClient.get<{ installments: RentalInstallment[] }>(`/rentals/${contractId}`)
      .then(({ data }) => {
        setPendingInstallments((data.installments || []).filter((i) => i.payment_status === "pending" || i.payment_status === "overdue"));
      })
      .catch((err) => {
        setInstallmentsLoadError(err?.response?.data?.detail || err?.message || "Could not check this contract's payment schedule.");
        setPendingInstallments([]);
      })
      .finally(() => setLoadingInstallments(false));
  }, []);

  const loadPendingInstallments = useCallback((tenantId: number) => {
    setLoadingInstallments(true);
    setSelectedInstallmentId("");
    setInstallmentsLoadError(null);
    setContractChoices([]);
    setSelectedContractId("");
    apiClient.get<PaginatedResponse<{ id: number; contract_number: string; unit_number: string | null; property_title: string | null; rent_amount: string }>>(
      "/rentals", { params: { tenant_id: tenantId, contract_status: "active", page_size: 5 } }
    )
      .then(async ({ data }) => {
        if (data.items.length > 1) {
          // Used to be a dead end (silently grabbing data.items[0], or
          // later a blocking warning telling the user to go pick a
          // contract from the Contracts page instead). Now every active
          // contract is listed right here so the correct one can be
          // picked without leaving this page.
          setContractChoices(data.items);
          setLoadingInstallments(false);
          return;
        }
        const contract = data.items[0];
        if (!contract) { setPendingInstallments([]); setLoadingInstallments(false); return; }
        setSelectedContractId(contract.id);
        const { data: detail } = await apiClient.get<{ installments: RentalInstallment[] }>(`/rentals/${contract.id}`);
        setPendingInstallments((detail.installments || []).filter((i) => i.payment_status === "pending" || i.payment_status === "overdue"));
        setLoadingInstallments(false);
      })
      .catch((err) => {
        // Previously swallowed silently and just showed "no schedule
        // found" even when the real cause was something else entirely
        // (permissions, a failed request, etc.) — now the actual error
        // shows instead of a misleading generic fallback.
        setInstallmentsLoadError(err?.response?.data?.detail || err?.message || "Could not check this tenant's payment schedule.");
        setPendingInstallments([]);
        setLoadingInstallments(false);
      });
  }, []);

  useEffect(() => {
    if (selectedTenant) loadPendingInstallments(selectedTenant.id);
  }, [selectedTenant, loadPendingInstallments]);

  const resetAfterTenantChange = () => {
    setPendingInstallments([]); setSelectedInstallmentId("");
    setContractChoices([]); setSelectedContractId("");
    setAmount(""); setError(null);
  };

  const handleSubmit = async () => {
    if (!selectedTenant || !accountId) return;
    setSubmitting(true);
    setError(null);
    try {
      const amt = Number(amount);
      if (!amt || amt <= 0) throw new Error("Enter an amount greater than zero.");

      let transactionId: number;
      setStep("creating_transaction");
      if (selectedInstallmentId && selectedInstallmentId !== "other") {
        // Routed through the same protected endpoint the Payment
        // Schedule tab itself would use — refuses an already-paid
        // installment (409) instead of silently creating a second
        // real payment for the same month.
        const { data: confirmed } = await apiClient.post(`/rentals/installments/${selectedInstallmentId}/confirm-payment`, {
          account_id: Number(accountId), payment_method: paymentMethod,
          reference_number: referenceNumber || undefined, transaction_date: paymentDate,
        });
        transactionId = confirmed.transaction_id;
      } else {
        const { data: txn } = await apiClient.post("/financial/transactions", {
          transaction_type: "tenant_payment",
          amount: amt,
          account_id: Number(accountId),
          tenant_id: selectedTenant.id,
          payment_method: paymentMethod,
          reference_number: referenceNumber || undefined,
          transaction_date: paymentDate,
          description: `Rent payment — ${selectedTenant.display_name}`,
        });
        transactionId = txn.id;
      }

      setStep("generating_vouchers");
      const { data: result } = await apiClient.post("/rent-vouchers/generate", {
        transaction_ids: [transactionId],
        rental_month: rentalMonth,
      });
      const voucherIds: number[] = result.vouchers.map((v: any) => v.id);

      navigate(`/rent-vouchers/print?ids=${voucherIds.join(",")}`);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      // Was backwards before — err.message (axios's generic "Request
      // failed with status code 409") is basically NEVER empty for a
      // failed request, so the real backend detail message (e.g.
      // "This receipt has already been confirmed as paid" vs. "already
      // has a voucher...") was never actually reaching the screen.
      setError((typeof detail === "string" ? detail : null) || err?.message || "Something went wrong — nothing further was created after this step.");
    } finally {
      setSubmitting(false);
      setStep("");
    }
  };

  const canSubmit =
    !!selectedTenant && !!accountId && !submitting &&
    (contractChoices.length === 0 || !!selectedContractId) &&
    Number(amount) > 0 && (pendingInstallments.length === 0 || !!selectedInstallmentId);

  if (!canAct) {
    return (
      <div className="card p-8 text-center text-ink-500">
        <AlertCircle className="mx-auto mb-3 text-amber-500" size={28} />
        You need "Financial — Create" and "Rent Vouchers — Create" permissions to use this page.
      </div>
    );
  }

  if (accountsLoaded && accounts.length === 0) {
    return (
      <div className="card p-8 text-center text-ink-500">
        <AlertCircle className="mx-auto mb-3 text-amber-500" size={28} />
        <p className="mb-3">No financial account exists yet (e.g. a cash box or bank account) — one is required before any payment can be recorded.</p>
        <button className="btn-primary" onClick={() => navigate("/financial")}>Go to Financial → Add Account</button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <button className="flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-100 mb-4" onClick={() => navigate("/payments")}>
        <ArrowLeft size={15} /> Back to Payments
      </button>
      <PageHeader title="Collect Rent & Print Voucher" description="Record a tenant payment and generate the printable rent voucher in one place." />

      <div className="card p-5 space-y-5">
        {/* Tenant */}
        <FormField label="Tenant" required>
          {!selectedTenant ? (
            <div>
              <select className="input mb-2" value={buildingFilter} onChange={(e) => setBuildingFilter(e.target.value ? Number(e.target.value) : "")}>
                <option value="">All buildings</option>
                {buildings.map((b) => <option key={b.id} value={b.id}>{b.property_code} — {b.title}</option>)}
              </select>
              <input className="input" placeholder="Search tenant by name, code, phone…" value={tenantSearch} onChange={(e) => setTenantSearch(e.target.value)} />
              {tenantsLoading && <div className="text-xs text-ink-400 mt-1.5 flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> Searching…</div>}
              {!tenantsLoading && tenants.length > 0 && (
                <div className="mt-2 border border-ink-100 dark:border-ink-800 rounded-lg divide-y divide-ink-100 dark:divide-ink-800 max-h-52 overflow-y-auto">
                  {tenants.map((t) => (
                    <button key={t.id} type="button" className="w-full text-left px-3 py-2 text-sm hover:bg-ink-50 dark:hover:bg-ink-800/50"
                      onClick={() => { setSelectedTenant(t); resetAfterTenantChange(); }}>
                      <div className="font-medium">{t.display_name}</div>
                      <div className="text-xs text-ink-400">{t.tenant_code}{t.primary_phone ? ` · ${t.primary_phone}` : ""}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-between rounded-lg border border-ink-100 dark:border-ink-800 px-3 py-2">
              <div>
                <div className="font-medium text-sm">{selectedTenant.display_name}</div>
                <div className="text-xs text-ink-400">{selectedTenant.tenant_code}</div>
              </div>
              <button className="text-xs font-medium text-brand-600 dark:text-brand-400 hover:underline" onClick={() => { setSelectedTenant(null); resetAfterTenantChange(); }}>
                Change
              </button>
            </div>
          )}
        </FormField>

        {selectedTenant && (
          <>
            {contractChoices.length > 0 && (
              <FormField label="Which contract is this for?" required hint="This tenant has more than one active contract — pick the right one before choosing the month.">
                <div className="border border-ink-100 dark:border-ink-800 rounded-lg divide-y divide-ink-100 dark:divide-ink-800">
                  {contractChoices.map((c) => (
                    <label key={c.id} className="flex items-center justify-between px-3 py-2 text-sm cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/50">
                      <span className="flex items-center gap-2">
                        <input type="radio" name="contract" checked={selectedContractId === c.id}
                          onChange={() => { setSelectedContractId(c.id); loadInstallmentsForContract(c.id); }} />
                        <span>
                          <span className="font-medium">{c.contract_number}</span>
                          <span className="text-ink-400"> · {c.property_title || "—"}{c.unit_number ? ` #${c.unit_number}` : ""}</span>
                        </span>
                      </span>
                      <span className="font-medium">{Number(c.rent_amount).toLocaleString()}</span>
                    </label>
                  ))}
                </div>
              </FormField>
            )}

            <FormField label="Which month is this for?" required>
              {loadingInstallments && <div className="text-xs text-ink-400 flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> Checking this tenant's payment schedule…</div>}
              {!loadingInstallments && installmentsLoadError && (
                <div className="flex items-start gap-2 text-xs text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2 mb-2">
                  <AlertCircle size={14} className="shrink-0 mt-0.5" />
                  <span>{installmentsLoadError}</span>
                </div>
              )}
              {!loadingInstallments && contractChoices.length > 0 && !selectedContractId && (
                <div className="text-xs text-ink-400">Pick a contract above first.</div>
              )}
              {!loadingInstallments && (!contractChoices.length || selectedContractId) && (
                <div className="space-y-2">
                  {pendingInstallments.length > 0 && (
                    <div className="border border-ink-100 dark:border-ink-800 rounded-lg divide-y divide-ink-100 dark:divide-ink-800 max-h-52 overflow-y-auto">
                      {pendingInstallments.map((inst) => (
                        <label key={inst.id} className="flex items-center justify-between px-3 py-2 text-sm cursor-pointer hover:bg-ink-50 dark:hover:bg-ink-800/50">
                          <span className="flex items-center gap-2">
                            <input type="radio" name="installment" checked={selectedInstallmentId === inst.id}
                              onChange={() => { setSelectedInstallmentId(inst.id); setAmount(inst.total_payable); setRentalMonth(inst.due_date); }} />
                            <span className="flex items-center gap-1.5">
                              <CalendarClock size={13} className="text-ink-400" />
                              <span>Installment #{inst.installment_number} · due {inst.due_date}</span>
                              {inst.payment_status === "overdue" && <span className="text-rust-500 text-xs font-medium">overdue</span>}
                            </span>
                          </span>
                          <span className="font-medium">{Number(inst.total_payable).toLocaleString()}</span>
                        </label>
                      ))}
                    </div>
                  )}
                  <label className="flex items-center gap-2 text-xs text-ink-500 cursor-pointer">
                    <input type="radio" name="installment" checked={selectedInstallmentId === "other" || (pendingInstallments.length === 0 && selectedInstallmentId === "")}
                      onChange={() => { setSelectedInstallmentId("other"); setAmount(""); }} />
                    {pendingInstallments.length > 0 ? "Something else (not one of the installments above)" : "No active contract schedule found for this tenant — enter an amount manually"}
                  </label>
                </div>
              )}
            </FormField>

            <div className="grid grid-cols-2 gap-4">
              <FormField label="Amount" required>
                <input className="input" type="number" min="0" step="0.001" value={amount} onChange={(e) => setAmount(e.target.value)}
                  disabled={!!selectedInstallmentId && selectedInstallmentId !== "other"} />
              </FormField>
              <FormField label="Account" required>
                <select className="input" value={accountId} onChange={(e) => setAccountId(Number(e.target.value))}>
                  {accounts.map((a) => <option key={a.id} value={a.id}>{a.account_code} — {a.name}</option>)}
                </select>
              </FormField>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <FormField label="Payment Method">
                <select className="input" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
                  {PAYMENT_METHODS.map((m) => <option key={m} value={m}>{m.replace("_", " ")}</option>)}
                </select>
              </FormField>
              <FormField label="Payment Date">
                <input className="input" type="date" value={paymentDate} onChange={(e) => setPaymentDate(e.target.value)} />
              </FormField>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <FormField label="Reference Number" hint="Cheque #, transfer ref, etc. (optional)">
                <input className="input" value={referenceNumber} onChange={(e) => setReferenceNumber(e.target.value)} />
              </FormField>
              <FormField label="Voucher Month" hint="Which month this voucher is for">
                <input className="input" type="month" value={rentalMonth.slice(0, 7)} onChange={(e) => setRentalMonth(`${e.target.value}-01`)} />
              </FormField>
            </div>
          </>
        )}

        {error && (
          <div className="flex items-start gap-2 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">
            <AlertCircle size={16} className="shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {submitting && step && (
          <div className="flex items-center gap-2 text-sm text-ink-500">
            <Loader2 size={14} className="animate-spin" /> {STEP_LABELS[step]}
          </div>
        )}

        <button className="btn-primary w-full justify-center" disabled={!canSubmit} onClick={handleSubmit}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
          Collect Payment &amp; Generate Voucher
        </button>
        <p className="text-xs text-ink-400 text-center">
          Nothing is created until you press this button.
        </p>
      </div>
    </div>
  );
}
