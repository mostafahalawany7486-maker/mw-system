import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "@/api/client";
import { PageHeader } from "@/components/ui";
import { Loader2, ArrowLeft, CheckCircle2, Home } from "lucide-react";

interface VacantUnit {
  property_id: number;
  property_title: string;
  property_code: string;
  unit_number: string | null;
  building_title: string | null;
}

/**
 * "Set Vacant Unit Prices" — a one-time bulk fill-in-the-blanks screen,
 * requested directly: the Dashboard's Vacant Units Value card can only
 * count a vacant unit toward the potential-loss total if it has a
 * rent_price set, and going through every vacant unit's own edit form
 * one at a time was too slow. Reuses GET /properties/vacant-missing-price
 * (same list the Dashboard card already flags via its "+N with no
 * price" note) and POST /properties/vacant-missing-price/bulk-set.
 */
export default function SetVacantUnitPricesPage() {
  const navigate = useNavigate();
  const [units, setUnits] = useState<VacantUnit[]>([]);
  const [prices, setPrices] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedCount, setSavedCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient.get<VacantUnit[]>("/properties/vacant-missing-price")
      .then(({ data }) => setUnits(data))
      .catch(() => setError("Could not load vacant units."))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    const updates = Object.entries(prices)
      .filter(([, v]) => v && Number(v) > 0)
      .map(([property_id, rent_price]) => ({ property_id: Number(property_id), rent_price: Number(rent_price) }));
    if (updates.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      const { data } = await apiClient.post("/properties/vacant-missing-price/bulk-set", updates);
      setSavedCount(data.updated);
      setUnits((prev) => prev.filter((u) => !updates.some((up) => up.property_id === u.property_id)));
      setPrices({});
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not save prices.");
    } finally {
      setSaving(false);
    }
  };

  const filledCount = Object.values(prices).filter((v) => v && Number(v) > 0).length;

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-ink-400" size={28} /></div>;

  return (
    <div className="max-w-2xl">
      <button className="flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800 dark:hover:text-ink-100 mb-4" onClick={() => navigate("/dashboard")}>
        <ArrowLeft size={15} /> Back to Dashboard
      </button>
      <PageHeader title="Set Vacant Unit Prices" description="Every vacant unit with no asking rent set — fill in what applies, leave the rest blank." />

      {savedCount !== null && (
        <div className="flex items-center gap-2 text-sm bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-lg px-4 py-3 mb-4">
          <CheckCircle2 size={16} /> {savedCount} unit(s) updated. The Dashboard's Vacant Units Value will include them next time it loads.
        </div>
      )}

      {error && <div className="text-sm text-rust-500 bg-rust-50 dark:bg-rust-500/10 rounded-md px-3 py-2 mb-4">{error}</div>}

      {units.length === 0 ? (
        <div className="card p-8 text-center text-ink-500">
          <Home className="mx-auto mb-3 text-emerald-500" size={28} />
          Every vacant unit already has a price set — nothing left to fill in here.
        </div>
      ) : (
        <div className="card">
          <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
            {units.map((u) => (
              <div key={u.property_id} className="px-5 py-3 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{u.building_title ? `${u.building_title} — ` : ""}{u.unit_number ? `Unit ${u.unit_number}` : u.property_title}</p>
                  <p className="text-xs text-ink-400">{u.property_code}</p>
                </div>
                <input
                  className="input !w-36 shrink-0"
                  type="number" min="0" step="0.001" placeholder="Rent price"
                  value={prices[u.property_id] || ""}
                  onChange={(e) => setPrices((p) => ({ ...p, [u.property_id]: e.target.value }))}
                />
              </div>
            ))}
          </div>
          <div className="px-5 py-4 border-t border-ink-100 dark:border-ink-800 flex items-center justify-between">
            <span className="text-xs text-ink-400">{filledCount} of {units.length} filled in</span>
            <button className="btn-primary" disabled={saving || filledCount === 0} onClick={handleSave}>
              {saving ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
              Save {filledCount > 0 ? `(${filledCount})` : ""}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
