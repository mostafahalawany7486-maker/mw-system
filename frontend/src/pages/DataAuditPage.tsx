import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { PageHeader } from "@/components/ui";
import { Loader2, ArrowLeft, AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";

interface Finding {
  count: number;
  description: string;
  samples: any[];
}
type AuditReport = Record<string, Finding>;

const TITLES: Record<string, string> = {
  tenants_without_contracts: "Tenants Without Any Contract",
  duplicate_tenant_national_ids: "Duplicate Tenant National IDs",
  duplicate_units_same_floor: "Duplicate Unit Numbers (same building & floor)",
  multiple_active_contracts_per_property: "Multiple Active Contracts on the Same Property",
  contracts_with_invalid_dates: "Contracts With Invalid Dates",
  contracts_on_archived_properties: "Active Contracts on Archived Properties",
};

export default function DataAuditPage() {
  const navigate = useNavigate();
  const [report, setReport] = useState<AuditReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    apiClient.get<AuditReport>("/data-audit")
      .then(({ data }) => setReport(data))
      .catch(() => setError("Could not run the audit."))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const totalIssues = report ? Object.values(report).reduce((sum, f) => sum + f.count, 0) : 0;

  return (
    <div>
      <button className="flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-100 mb-4" onClick={() => navigate("/reports")}>
        <ArrowLeft size={15} /> Back to Reports
      </button>
      <PageHeader
        title="Data Integrity Audit"
        description="Read-only checks across Tenants, Properties, and Rental Contracts. Nothing here is ever changed automatically — this only reports what to review."
        action={
          <button className="btn-secondary" onClick={load} disabled={loading}>
            {loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />} Re-run
          </button>
        }
      />

      {loading && !report && <div className="flex justify-center py-16"><Loader2 className="animate-spin text-ink-400" /></div>}
      {error && <p className="text-sm text-rust-500 py-6 text-center">{error}</p>}

      {report && (
        <>
          <div className={`card p-4 mb-6 flex items-center gap-3 ${totalIssues === 0 ? "border-emerald-200 dark:border-emerald-500/30" : "border-amber-200 dark:border-amber-500/30"}`}>
            {totalIssues === 0 ? (
              <><CheckCircle2 className="text-emerald-500" size={20} /> <span className="font-medium text-sm">No issues found across any check.</span></>
            ) : (
              <><AlertTriangle className="text-amber-500" size={20} /> <span className="font-medium text-sm">{totalIssues} total item(s) flagged across {Object.values(report).filter((f) => f.count > 0).length} check(s) below.</span></>
            )}
          </div>

          <div className="space-y-4">
            {Object.entries(report).map(([key, finding]) => (
              <div key={key} className="card">
                <div className="p-4 border-b border-ink-100 dark:border-ink-800 flex items-center justify-between">
                  <div>
                    <p className="font-medium text-sm">{TITLES[key] || key}</p>
                    <p className="text-xs text-ink-400 mt-0.5">{finding.description}</p>
                  </div>
                  <span className={finding.count === 0 ? "badge-active" : "badge-warn"}>{finding.count}</span>
                </div>
                {finding.count > 0 && (
                  <div className="p-4 overflow-x-auto">
                    <pre className="text-xs text-ink-600 dark:text-ink-300 whitespace-pre-wrap font-mono">
                      {JSON.stringify(finding.samples, null, 2)}
                    </pre>
                    {finding.count > finding.samples.length && (
                      <p className="text-xs text-ink-400 mt-2">Showing {finding.samples.length} of {finding.count} — narrow this down from the relevant list page.</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
