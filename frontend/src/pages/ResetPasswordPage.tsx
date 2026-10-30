import { useState, FormEvent } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import apiClient from "@/api/client";
import { CheckCircle2, Loader2 } from "lucide-react";

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await apiClient.post("/auth/reset-password", { token, new_password: password });
      setSuccess(true);
      setTimeout(() => navigate("/login"), 2000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "This reset link is invalid or has expired.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-ink-950 p-4">
      <div className="w-full max-w-sm">
        <div className="card p-6 bg-ink-900 border-ink-800">
          <h1 className="font-display font-semibold text-lg text-white mb-1">Set a new password</h1>
          <p className="text-sm text-ink-400 mb-6">Choose a strong password with at least 8 characters.</p>

          {success ? (
            <div className="flex flex-col items-center text-center py-4">
              <CheckCircle2 className="text-brand-400 mb-2" size={28} />
              <p className="text-sm text-ink-200">Password updated. Redirecting to sign in…</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && <div className="text-rust-500 text-sm">{error}</div>}
              <div>
                <label className="label text-ink-300">New password</label>
                <input
                  type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                  className="input bg-ink-800 border-ink-700 text-white" minLength={8}
                />
              </div>
              <div>
                <label className="label text-ink-300">Confirm password</label>
                <input
                  type="password" required value={confirm} onChange={(e) => setConfirm(e.target.value)}
                  className="input bg-ink-800 border-ink-700 text-white" minLength={8}
                />
              </div>
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading && <Loader2 size={16} className="animate-spin" />}
                Reset password
              </button>
            </form>
          )}
          <Link to="/login" className="block text-center text-xs text-ink-400 hover:text-ink-200 mt-6">Back to sign in</Link>
        </div>
      </div>
    </div>
  );
}
