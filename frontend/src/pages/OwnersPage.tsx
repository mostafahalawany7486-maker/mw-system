import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, StatusBadge, EmptyState, ToolbarSearch } from "@/components/ui";
import { Plus, Loader2, User, Building2, Users, AlertTriangle } from "lucide-react";
import { OwnerListItem, OwnerDashboard, PaginatedResponse } from "@/types";
import OwnerFormModal from "@/components/OwnerFormModal";

export default function OwnersPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<PaginatedResponse<OwnerListItem> | null>(null);
  const [dashboard, setDashboard] = useState<OwnerDashboard | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [ownerType, setOwnerType] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  const canCreate = hasPermission("owners.create");

  const load = useCallback(() => {
    setLoading(true);
    apiClient
      .get<PaginatedResponse<OwnerListItem>>("/owners", {
        params: { page, page_size: 10, search: search || undefined, owner_type: ownerType || undefined },
      })
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false));
  }, [page, search, ownerType]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    apiClient.get<OwnerDashboard>("/owners/dashboard/summary").then(({ data }) => setDashboard(data));
  }, [data]);

  return (
    <div>
      <PageHeader
        title="Property Owners"
        description="Individuals and companies the company leases properties from."
        action={canCreate && (
          <button className="btn-primary" onClick={() => setModalOpen(true)}>
            <Plus size={16} /> Add Owner
          </button>
        )}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Total Owners</span>
            <Users size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.total_owners : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Individuals</span>
            <User size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.individual_owners : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Companies</span>
            <Building2 size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.company_owners : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Missing Bank Details</span>
            <AlertTriangle size={16} className="text-amber-500" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.owners_missing_bank_details : "—"}</div>
        </div>
      </div>

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800 flex flex-wrap gap-3 items-center">
          <ToolbarSearch value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search by name, code, email, phone…" />
          <select
            className="input max-w-[160px]"
            value={ownerType}
            onChange={(e) => { setOwnerType(e.target.value); setPage(1); }}
          >
            <option value="">All types</option>
            <option value="individual">Individual</option>
            <option value="company">Company</option>
          </select>
        </div>

        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

        {!loading && data && data.items.length === 0 && (
          <EmptyState title="No owners yet" description="Add your first property owner to get started." />
        )}

        {!loading && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr>
                  <th>Code</th><th>Name</th><th>Type</th><th>Email</th><th>Phone</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((o) => (
                  <tr key={o.id} className="cursor-pointer" onClick={() => navigate(`/owners/${o.id}`)}>
                    <td className="font-mono text-xs">{o.owner_code}</td>
                    <td className="font-medium">{o.display_name}</td>
                    <td className="capitalize">
                      <span className="inline-flex items-center gap-1.5">
                        {o.owner_type === "company" ? <Building2 size={13} /> : <User size={13} />}
                        {o.owner_type}
                      </span>
                    </td>
                    <td className="text-ink-500">{o.primary_email || "—"}</td>
                    <td className="text-ink-500">{o.primary_phone || "—"}</td>
                    <td><StatusBadge status={o.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />}
      </div>

      <OwnerFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={(created) => { setModalOpen(false); navigate(`/owners/${created.id}`); }}
      />
    </div>
  );
}
