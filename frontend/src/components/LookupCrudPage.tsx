import { useEffect, useState, useCallback } from "react";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, StatusBadge, Modal, EmptyState, ToolbarSearch } from "@/components/ui";
import { Plus, Pencil, Trash2, Loader2 } from "lucide-react";
import { PaginatedResponse } from "@/types";

export interface FieldConfig {
  name: string;
  label: string;
  type?: "text" | "number" | "select" | "checkbox";
  required?: boolean;
  options?: { label: string; value: number | string }[];
}

export interface ColumnConfig<T> {
  header: string;
  render: (row: T) => React.ReactNode;
}

interface LookupCrudPageProps<T extends { id: number; status: string }> {
  title: string;
  description?: string;
  endpoint: string; // e.g. "/countries"
  permissionModule: string; // e.g. "countries"
  columns: ColumnConfig<T>[];
  fields: FieldConfig[];
  emptyDefaults: Record<string, any>;
}

export default function LookupCrudPage<T extends { id: number; status: string }>({
  title, description, endpoint, permissionModule, columns, fields, emptyDefaults,
}: LookupCrudPageProps<T>) {
  const { hasPermission } = useAuth();
  const [data, setData] = useState<PaginatedResponse<T> | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<Record<string, any>>(emptyDefaults);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const canCreate = hasPermission(`${permissionModule}.create`);
  const canEdit = hasPermission(`${permissionModule}.edit`);
  const canDelete = hasPermission(`${permissionModule}.delete`);

  const load = useCallback(() => {
    setLoading(true);
    apiClient
      .get<PaginatedResponse<T>>(endpoint, { params: { page, page_size: 10, search: search || undefined } })
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false));
  }, [endpoint, page, search]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyDefaults);
    setFormError(null);
    setModalOpen(true);
  };

  const openEdit = (row: T) => {
    setEditingId(row.id);
    setForm(row as any);
    setFormError(null);
    setModalOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    setFormError(null);
    try {
      if (editingId) {
        await apiClient.put(`${endpoint}/${editingId}`, form);
      } else {
        await apiClient.post(endpoint, form);
      }
      setModalOpen(false);
      load();
    } catch (err: any) {
      setFormError(err?.response?.data?.detail || "Unable to save. Please check the form and try again.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this record? This action can be reversed by an administrator.")) return;
    await apiClient.delete(`${endpoint}/${id}`);
    load();
  };

  return (
    <div>
      <PageHeader
        title={title}
        description={description}
        action={
          canCreate && (
            <button className="btn-primary" onClick={openCreate}>
              <Plus size={16} /> Add {title.replace(/s$/, "")}
            </button>
          )
        }
      />

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800">
          <ToolbarSearch value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder={`Search ${title.toLowerCase()}…`} />
        </div>

        {loading && (
          <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>
        )}

        {!loading && data && data.items.length === 0 && (
          <EmptyState title={`No ${title.toLowerCase()} yet`} description={`Add your first ${title.toLowerCase().replace(/s$/, "")} to get started.`} />
        )}

        {!loading && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr>
                  {columns.map((c) => <th key={c.header}>{c.header}</th>)}
                  <th>Status</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={row.id}>
                    {columns.map((c) => <td key={c.header}>{c.render(row)}</td>)}
                    <td><StatusBadge status={row.status} /></td>
                    <td className="text-right">
                      <div className="flex justify-end gap-1">
                        {canEdit && (
                          <button className="btn-secondary !px-2 !py-1" onClick={() => openEdit(row)} aria-label="Edit">
                            <Pencil size={14} />
                          </button>
                        )}
                        {canDelete && (
                          <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(row.id)} aria-label="Delete">
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {data && <Pagination page={data.page} totalPages={data.total_pages} onChange={setPage} />}
      </div>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingId ? `Edit ${title.replace(/s$/, "")}` : `Add ${title.replace(/s$/, "")}`}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
            <button className="btn-primary" disabled={saving} onClick={handleSave}>
              {saving && <Loader2 size={14} className="animate-spin" />} Save
            </button>
          </>
        }
      >
        {formError && <div className="mb-3 text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2">{formError}</div>}
        <div className="space-y-4">
          {fields.map((f) => (
            <div key={f.name}>
              {f.type !== "checkbox" && <label className="label">{f.label}{f.required && " *"}</label>}
              {f.type === "select" ? (
                <select
                  className="input"
                  value={form[f.name] ?? ""}
                  onChange={(e) => setForm({ ...form, [f.name]: e.target.value ? Number(e.target.value) : null })}
                >
                  <option value="">Select…</option>
                  {f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              ) : f.type === "checkbox" ? (
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={!!form[f.name]}
                    onChange={(e) => setForm({ ...form, [f.name]: e.target.checked })}
                  />
                  {f.label}
                </label>
              ) : (
                <input
                  className="input"
                  type={f.type === "number" ? "number" : "text"}
                  required={f.required}
                  value={form[f.name] ?? ""}
                  onChange={(e) => setForm({ ...form, [f.name]: f.type === "number" ? Number(e.target.value) : e.target.value })}
                />
              )}
            </div>
          ))}
        </div>
      </Modal>
    </div>
  );
}
