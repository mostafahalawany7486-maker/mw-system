import { useEffect, useState, useCallback } from "react";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, Modal, EmptyState } from "@/components/ui";
import { Plus, Pencil, Trash2, Loader2, Lock } from "lucide-react";
import { Role, Permission, PaginatedResponse } from "@/types";

export default function RolesPage() {
  const { hasPermission } = useAuth();
  const [data, setData] = useState<PaginatedResponse<Role> | null>(null);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<{ name: string; description: string; permission_ids: number[] }>({
    name: "", description: "", permission_ids: [],
  });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const canCreate = hasPermission("roles.create");
  const canEdit = hasPermission("roles.edit");
  const canDelete = hasPermission("roles.delete");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get<PaginatedResponse<Role>>("/roles", { params: { page, page_size: 10 } })
      .then(({ data }) => setData(data)).finally(() => setLoading(false));
  }, [page]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    apiClient.get<Permission[]>("/roles/permissions").then(({ data }) => setPermissions(data));
  }, []);

  const permsByModule = permissions.reduce<Record<string, Permission[]>>((acc, p) => {
    (acc[p.module] ||= []).push(p);
    return acc;
  }, {});

  const openCreate = () => {
    setEditingId(null);
    setForm({ name: "", description: "", permission_ids: [] });
    setFormError(null);
    setModalOpen(true);
  };

  const openEdit = (r: Role) => {
    setEditingId(r.id);
    setForm({ name: r.name, description: r.description || "", permission_ids: r.permissions.map((p) => p.id) });
    setFormError(null);
    setModalOpen(true);
  };

  const togglePermission = (id: number) => {
    setForm((f) => ({
      ...f,
      permission_ids: f.permission_ids.includes(id) ? f.permission_ids.filter((x) => x !== id) : [...f.permission_ids, id],
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setFormError(null);
    try {
      if (editingId) {
        await apiClient.put(`/roles/${editingId}`, form);
      } else {
        await apiClient.post("/roles", form);
      }
      setModalOpen(false);
      load();
    } catch (err: any) {
      setFormError(err?.response?.data?.detail || "Unable to save this role.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this role?")) return;
    try {
      await apiClient.delete(`/roles/${id}`);
      load();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Unable to delete this role.");
    }
  };

  return (
    <div>
      <PageHeader
        title="Roles & Permissions"
        description="Define what each role can see and do across the system."
        action={canCreate && <button className="btn-primary" onClick={openCreate}><Plus size={16} /> Add Role</button>}
      />

      <div className="card">
        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

        {!loading && data && data.items.length === 0 && <EmptyState title="No roles yet" />}

        {!loading && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr><th>Role</th><th>Description</th><th>Permissions</th><th className="text-right">Actions</th></tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id}>
                    <td className="font-medium flex items-center gap-1.5">
                      {r.name}
                      {r.is_system_role && <Lock size={12} className="text-ink-400" aria-label="Built-in role" />}
                    </td>
                    <td className="text-ink-500">{r.description || "—"}</td>
                    <td className="text-ink-500">{r.permissions.length} permission(s)</td>
                    <td className="text-right">
                      <div className="flex justify-end gap-1">
                        {canEdit && (
                          <button className="btn-secondary !px-2 !py-1" onClick={() => openEdit(r)} aria-label="Edit">
                            <Pencil size={14} />
                          </button>
                        )}
                        {canDelete && !r.is_system_role && (
                          <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(r.id)} aria-label="Delete">
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
        title={editingId ? "Edit Role" : "Add Role"}
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
          <div>
            <label className="label">Role Name *</label>
            <input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label">Description</label>
            <input className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div>
            <label className="label">Permissions</label>
            <div className="space-y-3 max-h-64 overflow-y-auto border border-ink-100 dark:border-ink-800 rounded-md p-3">
              {Object.entries(permsByModule).map(([module, perms]) => (
                <div key={module}>
                  <div className="text-xs font-semibold uppercase text-ink-400 mb-1">{module}</div>
                  <div className="flex flex-wrap gap-3">
                    {perms.map((p) => (
                      <label key={p.id} className="flex items-center gap-1.5 text-sm">
                        <input type="checkbox" checked={form.permission_ids.includes(p.id)} onChange={() => togglePermission(p.id)} />
                        {p.action}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
