import { useEffect, useState } from "react";
import apiClient from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, EmptyState } from "@/components/ui";
import { SystemSetting } from "@/types";
import { Loader2, Save } from "lucide-react";

export default function SettingsPage() {
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("settings.edit");
  const [settings, setSettings] = useState<SystemSetting[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    apiClient.get<SystemSetting[]>("/settings").then(({ data }) => setSettings(data)).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const updateValue = (key: string, value: string) => {
    setSettings((prev) => prev.map((s) => (s.key === key ? { ...s, value } : s)));
  };

  const saveSetting = async (setting: SystemSetting) => {
    setSavingKey(setting.key);
    try {
      await apiClient.put(`/settings/${setting.key}`, { value: setting.value });
    } finally {
      setSavingKey(null);
    }
  };

  const grouped = settings.reduce<Record<string, SystemSetting[]>>((acc, s) => {
    (acc[s.category] ||= []).push(s);
    return acc;
  }, {});

  if (loading) return <div className="flex justify-center py-16"><Loader2 className="animate-spin text-ink-400" /></div>;

  return (
    <div>
      <PageHeader title="System Settings" description="Global configuration values that control system behavior." />
      {settings.length === 0 && <EmptyState title="No settings configured" />}
      <div className="space-y-6">
        {Object.entries(grouped).map(([category, items]) => (
          <div key={category} className="card">
            <div className="px-5 py-3 border-b border-ink-100 dark:border-ink-800">
              <h2 className="font-display font-semibold text-sm capitalize">{category}</h2>
            </div>
            <div className="divide-y divide-ink-50 dark:divide-ink-800/60">
              {items.map((s) => (
                <div key={s.key} className="px-5 py-4 flex items-center gap-4 flex-wrap">
                  <div className="flex-1 min-w-[200px]">
                    <div className="text-sm font-medium">{s.key}</div>
                    {s.description && <div className="text-xs text-ink-400 mt-0.5">{s.description}</div>}
                  </div>
                  <input
                    className="input max-w-xs"
                    disabled={!canEdit || !s.is_editable}
                    value={s.value ?? ""}
                    onChange={(e) => updateValue(s.key, e.target.value)}
                  />
                  {canEdit && s.is_editable && (
                    <button className="btn-secondary !px-2 !py-2" onClick={() => saveSetting(s)} disabled={savingKey === s.key}>
                      {savingKey === s.key ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
