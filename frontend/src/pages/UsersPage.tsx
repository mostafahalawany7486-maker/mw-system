import { useEffect, useState, useCallback } from "react";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Pagination, StatusBadge, Modal, EmptyState, ToolbarSearch } from "@/components/ui";
import { Plus, Pencil, Trash2, Loader2, Ban, CheckCircle } from "lucide-react";
import { User, Role, PaginatedResponse } from "@/types";

const emptyForm = { first_name: "", last_name: "", email: "", phone: "", password: "", role_id: null as number | null };

export default function UsersPage() {
  const { hasPermission } = useAuth();
  const [data, setData] = useState<PaginatedResponse<User> | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<any>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const canCreate = hasPermission("users.create");
  const canEdit = hasPermission("users.edit");
  const canDelete = hasPermission("users.delete");

  const load = useCallback(() => {
    setLoading(true);
    apiClient
      .get<PaginatedResponse<User>>("/users", { params: { page, page_size: 10, search: search || undefined } })
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false));
  }, [page, search]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    apiClient.get<PaginatedResponse<Role>>("/roles", { params: { page_size: 100 } }).then(({ data }) => setRoles(data.items)).catch(() => {});
  }, []);

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm);
    setFormError(null);
    setModalOpen(true);
  };

  const openEdit = (u: User) => {
    setEditingId(u.id);
    setForm({ first_name: u.first_name, last_name: u.last_name, email: u.email, phone: u.phone || "", role_id: u.role_id });
    setFormError(null);
    setModalOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    setFormError(null);
    try {
      if (editingId) {
        const { password, email, ...editable } = form;
        await apiClient.put(`/users/${editingId}`, editable);
      } else {
        await apiClient.post("/users", form);
      }
      setModalOpen(false);
      load();
    } catch (err: any) {
      setFormError(err?.response?.data?.detail || "Unable to save this user. Please review the form.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this user?")) return;
    await apiClient.delete(`/users/${id}`);
    load();
  };

  const toggleActive = async (u: User) => {
    await apiClient.post(`/users/${u.id}/${u.is_active ? "deactivate" : "activate"}`);
    load();
  };

  return (
    <div>
      <PageHeader
        title="User Management"
        description="Manage staff accounts, roles, and access."
        action={canCreate && (
          <button className="btn-primary" onClick={openCreate}><Plus size={16} /> Add User</button>
        )}
      />

      <div className="card">
        <div className="p-4 border-b border-ink-100 dark:border-ink-800">
          <ToolbarSearch value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search users…" />
        </div>

        {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-ink-400" /></div>}

        {!loading && data && data.items.length === 0 && (
          <EmptyState title="No users yet" description="Add your first team member to get started." />
        )}

        {!loading && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-shell">
              <thead>
                <tr>
                  <th>Name</th><th>Email</th><th>Role</th><th>Status</th><th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((u) => (
                  <tr key={u.id}>
                    <td className="font-medium">{u.first_name} {u.last_name}</td>
                    <td className="text-ink-500">{u.email}</td>
                    <td>{u.role?.name || "—"}</td>
                    <td>
                      {u.is_active ? <StatusBadge status="active" /> : <StatusBadge status="inactive" />}
                    </td>
                    <td className="text-right">
                      <div className="flex justify-end gap-1">
                        {canEdit && (
                          <button className="btn-secondary !px-2 !py-1" onClick={() => toggleActive(u)} title={u.is_active ? "Deactivate" : "Activate"}>
                            {u.is_active ? <Ban size={14} /> : <CheckCircle size={14} />}
                          </button>
                        )}
                        {canEdit && (
                          <button className="btn-secondary !px-2 !py-1" onClick={() => openEdit(u)} aria-label="Edit">
                            <Pencil size={14} />
                          </button>
                        )}
                        {canDelete && (
                          <button className="btn-secondary !px-2 !py-1 text-rust-500" onClick={() => handleDelete(u.id)} aria-label="Delete">
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
        title={editingId ? "Edit User" : "Add User"}
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
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">First Name *</label>
            <input className="input" required value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
          </div>
          <div>
            <label className="label">Last Name *</label>
            <input className="input" required value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
          </div>
          <div className="col-span-2">
            <label className="label">Email *</label>
            <input className="input" type="email" required disabled={!!editingId} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          {!editingId && (
            <div className="col-span-2">
              <label className="label">Temporary Password *</label>
              <input className="input" type="password" required minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </div>
          )}
          <div className="col-span-2">
            <label className="label">Phone</label>
            <input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </div>
          <div className="col-span-2">
            <label className="label">Role</label>
            <select className="input" value={form.role_id ?? ""} onChange={(e) => setForm({ ...form, role_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">No role assigned</option>
              {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </div>
        </div>
      </Modal>
    </div>
  );
}
