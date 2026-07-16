import { useState, FormEvent } from "react";
import { Link } from "react-router-dom";
import apiClient from "@/api/client";
import { MailCheck, Loader2, ArrowLeft } from "lucide-react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { data } = await apiClient.post("/auth/forgot-password", { email });
      setMessage(data.message);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-ink-950 p-4">
      <div className="w-full max-w-sm">
        <div className="card p-6 bg-ink-900 border-ink-800">
          <h1 className="font-display font-semibold text-lg text-white mb-1">Reset your password</h1>
          <p className="text-sm text-ink-400 mb-6">We'll send a reset link to your email address.</p>

          {message ? (
            <div className="flex flex-col items-center text-center py-4">
              <MailCheck className="text-brand-400 mb-2" size={28} />
              <p className="text-sm text-ink-200">{message}</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && <div className="text-rust-500 text-sm">{error}</div>}
              <div>
                <label className="label text-ink-300">Email address</label>
                <input
                  type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)}
                  className="input bg-ink-800 border-ink-700 text-white placeholder:text-ink-500"
                  placeholder="you@company.com"
                />
              </div>
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading && <Loader2 size={16} className="animate-spin" />}
                Send reset link
              </button>
            </form>
          )}
          <Link to="/login" className="flex items-center gap-1 justify-center text-xs text-ink-400 hover:text-ink-200 mt-6">
            <ArrowLeft size={14} /> Back to sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
