import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/ui";
import { CompanyProfile, Country, City, Currency, PaginatedResponse } from "@/types";
import { Loader2, Save, CheckCircle2 } from "lucide-react";

export default function CompanyProfilePage() {
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("company.edit");
  const [form, setForm] = useState<Partial<CompanyProfile>>({});
  const [countries, setCountries] = useState<Country[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [currencies, setCurrencies] = useState<Currency[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    Promise.all([
      apiClient.get<CompanyProfile>("/company-profile").catch(() => ({ data: null })),
      apiClient.get<PaginatedResponse<Country>>("/countries", { params: { page_size: 200 } }),
      apiClient.get<PaginatedResponse<City>>("/cities", { params: { page_size: 200 } }),
      apiClient.get<PaginatedResponse<Currency>>("/currencies", { params: { page_size: 200 } }),
    ]).then(([profile, c, ci, cu]) => {
      if (profile.data) setForm(profile.data);
      setCountries(c.data.items);
      setCities(ci.data.items);
      setCurrencies(cu.data.items);
      setLoading(false);
    });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const { data } = await apiClient.put("/company-profile", form);
      setForm(data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-ink-400" /></div>;

  return (
    <div>
      <PageHeader title="Company Profile" description="This information appears on lease documents, invoices, and official correspondence." />
      <div className="card p-6 max-w-2xl">
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <label className="label">Legal Name *</label>
            <input className="input" disabled={!canEdit} value={form.legal_name || ""} onChange={(e) => setForm({ ...form, legal_name: e.target.value })} />
          </div>
          <div>
            <label className="label">Trade Name</label>
            <input className="input" disabled={!canEdit} value={form.trade_name || ""} onChange={(e) => setForm({ ...form, trade_name: e.target.value })} />
          </div>
          <div>
            <label className="label">Registration Number</label>
            <input className="input" disabled={!canEdit} value={form.registration_number || ""} onChange={(e) => setForm({ ...form, registration_number: e.target.value })} />
          </div>
          <div>
            <label className="label">Tax Number</label>
            <input className="input" disabled={!canEdit} value={form.tax_number || ""} onChange={(e) => setForm({ ...form, tax_number: e.target.value })} />
          </div>
          <div>
            <label className="label">Email</label>
            <input className="input" type="email" disabled={!canEdit} value={form.email || ""} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <label className="label">Phone</label>
            <input className="input" disabled={!canEdit} value={form.phone || ""} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </div>
          <div className="col-span-2">
            <label className="label">Website</label>
            <input className="input" disabled={!canEdit} value={form.website || ""} onChange={(e) => setForm({ ...form, website: e.target.value })} />
          </div>
          <div className="col-span-2">
            <label className="label">Address Line 1</label>
            <input className="input" disabled={!canEdit} value={form.address_line1 || ""} onChange={(e) => setForm({ ...form, address_line1: e.target.value })} />
          </div>
          <div className="col-span-2">
            <label className="label">Address Line 2</label>
            <input className="input" disabled={!canEdit} value={form.address_line2 || ""} onChange={(e) => setForm({ ...form, address_line2: e.target.value })} />
          </div>
          <div>
            <label className="label">Country</label>
            <select className="input" disabled={!canEdit} value={form.country_id ?? ""} onChange={(e) => setForm({ ...form, country_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Select…</option>
              {countries.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">City</label>
            <select className="input" disabled={!canEdit} value={form.city_id ?? ""} onChange={(e) => setForm({ ...form, city_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Select…</option>
              {cities.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Base Currency</label>
            <select className="input" disabled={!canEdit} value={form.base_currency_id ?? ""} onChange={(e) => setForm({ ...form, base_currency_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Select…</option>
              {currencies.map((c) => <option key={c.id} value={c.id}>{c.code} — {c.name}</option>)}
            </select>
          </div>
        </div>

        {canEdit && (
          <div className="flex items-center gap-3 mt-6">
            <button className="btn-primary" disabled={saving} onClick={handleSave}>
              {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              Save Changes
            </button>
            {saved && <span className="flex items-center gap-1 text-sm text-brand-600"><CheckCircle2 size={16} /> Saved</span>}
          </div>
        )}
      </div>
    </div>
  );
}
