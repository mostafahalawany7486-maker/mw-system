import { useState, FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/context/AuthContext";
import { KeyRound, Loader2 } from "lucide-react";
import LanguageSwitcher from "@/components/LanguageSwitcher";

export default function LoginPage() {
  const { login } = useAuth();
  const { t } = useTranslation("auth");
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err: any) {
      setError(err?.response?.data?.detail || t("genericLoginError"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-ink-950 p-4 relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(47,125,93,0.15),transparent_50%)] pointer-events-none" aria-hidden="true" />
      <div className="absolute top-4 right-4 rtl:right-auto rtl:left-4">
        <LanguageSwitcher />
      </div>
      <div className="w-full max-w-sm animate-scale-in relative">
        <div className="flex items-center gap-2 justify-center mb-8">
          <div className="w-10 h-10 rounded-lg bg-brand-500 flex items-center justify-center font-display font-bold text-ink-950">P</div>
          <span className="font-display font-bold text-xl text-white tracking-tight">{t("appName")}</span>
        </div>

        <div className="card p-6 bg-ink-900 border-ink-800">
          <h1 className="font-display font-semibold text-lg text-white mb-1">{t("signIn")}</h1>
          <p className="text-sm text-ink-400 mb-6">{t("signInSubtitle")}</p>

          {error && (
            <div className="mb-4 rounded-md bg-rust-500/10 border border-rust-500/30 text-rust-500 text-sm px-3 py-2">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label text-ink-300">{t("emailAddress")}</label>
              <input
                type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)}
                className="input bg-ink-800 border-ink-700 text-white placeholder:text-ink-500"
                placeholder="you@company.com"
              />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="label text-ink-300 !mb-0">{t("password")}</label>
                <Link to="/forgot-password" className="text-xs text-brand-400 hover:text-brand-300">{t("forgotPassword")}</Link>
              </div>
              <input
                type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                className="input bg-ink-800 border-ink-700 text-white placeholder:text-ink-500"
                placeholder="••••••••"
              />
            </div>
            <button type="submit" disabled={loading} className="btn-primary w-full mt-2">
              {loading ? <Loader2 size={16} className="animate-spin" /> : <KeyRound size={16} />}
              {t("signInButton")}
            </button>
          </form>
        </div>
        <p className="text-center text-xs text-ink-500 mt-6">
          {t("footerTagline")}
        </p>
      </div>
    </div>
  );
}
