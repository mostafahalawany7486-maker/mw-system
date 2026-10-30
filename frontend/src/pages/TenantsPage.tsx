import { useEffect, useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, StatusBadge, EmptyState, ToolbarSearch } from "@/components/ui";
import { Plus, Loader2, User, Building2, Users, ShieldBan, Star } from "lucide-react";
import { TenantListItem, TenantDashboard, PaginatedResponse } from "@/types";
import TenantFormModal from "@/components/TenantFormModal";

export default function TenantsPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<PaginatedResponse<TenantListItem> | null>(null);
  const [dashboard, setDashboard] = useState<TenantDashboard | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [tenantType, setTenantType] = useState("");
  const [blacklistFilter, setBlacklistFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [searchParams] = useSearchParams();
  useEffect(() => { if (searchParams.get("new") === "true") setModalOpen(true); }, [searchParams]);

  const canCreate = hasPermission("tenants.create");

  const load = useCallback(() => {
    setLoading(true);
    apiClient
      .get<PaginatedResponse<TenantListItem>>("/tenants", {
        params: {
          page, page_size: 10, search: search || undefined, tenant_type: tenantType || undefined,
          is_blacklisted: blacklistFilter === "" ? undefined : blacklistFilter === "true",
        },
      })
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false));
  }, [page, search, tenantType, blacklistFilter]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    apiClient.get<TenantDashboard>("/tenants/dashboard/summary").then(({ data }) => setDashboard(data));
  }, [data]);

  return (
    <div>
      <PageHeader
        title="Tenants"
        description="Individuals and companies the company subleases properties to."
        action={canCreate && (
          <button className="btn-primary" onClick={() => setModalOpen(true)}>
            <Plus size={16} /> Add Tenant
          </button>
        )}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Total Tenants</span>
            <Users size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.total_tenants : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Individuals / Companies</span>
            <User size={16} className="text-ink-400" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? `${dashboard.individual_tenants} / ${dashboard.company_tenants}` : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Blacklisted</span>
            <ShieldBan size={16} className="text-rust-500" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard ? dashboard.blacklisted_tenants : "—"}</div>
        </div>
        <div className="card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-ink-500 dark:text-ink-400">Avg. Rating</span>
            <Star size={16} className="text-amber-500" />
          </div>
          <div className="font-display text-2xl font-bold">{dashboard?.average_rating_overall ?? "—"}</div>
        </div>
      </div>

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800 flex flex-wrap gap-3 items-center">
          <ToolbarSearch value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search by name, code, ID, email, phone…" />
          <select className="input max-w-[160px]" value={tenantType} onChange={(e) => { setTenantType(e.target.value); setPage(1); }}>
            <option value="">All types</option>
            <option value="individual">Individual</option>
            <option value="company">Company</option>
          </select>
          <select className="input max-w-[160px]" value={blacklistFilter} onChange={(e) => { setBlacklistFilter(e.target.value); setPage(1); }}>
            <option value="">All tenants</option>
            <option value="false">Not blacklisted</option>
            <option value="true">Blacklisted only</option>
          </select>
        </div>

        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

        {!loading && data && data.items.length === 0 && (
          <EmptyState title="No tenants yet" description="Add your first tenant to get started." />
        )}

        {!loading && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr>
                  <th>Code</th><th>Name</th><th>Type</th><th>Email</th><th>Phone</th><th>Rating</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((t) => (
                  <tr key={t.id} className="cursor-pointer" onClick={() => navigate(`/tenants/${t.id}`)}>
                    <td className="font-mono text-xs">{t.tenant_code}</td>
                    <td className="font-medium">
                      <div className="flex items-center gap-1.5">
                        {t.display_name}
                        {t.is_blacklisted && <span className="badge-warn"><ShieldBan size={10} /> Blacklisted</span>}
                      </div>
                    </td>
                    <td className="capitalize">
                      <span className="inline-flex items-center gap-1.5">
                        {t.tenant_type === "company" ? <Building2 size={13} /> : <User size={13} />}
                        {t.tenant_type}
                      </span>
                    </td>
                    <td className="text-ink-500">{t.primary_email || "—"}</td>
                    <td className="text-ink-500">{t.primary_phone || "—"}</td>
                    <td className="text-ink-500">{t.average_rating != null ? `${t.average_rating} / 5` : "—"}</td>
                    <td><StatusBadge status={t.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />}
      </div>

      <TenantFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={(created) => { setModalOpen(false); navigate(`/tenants/${created.id}`); }}
      />
    </div>
  );
}
