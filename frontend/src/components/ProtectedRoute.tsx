import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { ReactNode } from "react";
import { ShieldAlert } from "lucide-react";

export function ProtectedRoute({ children, permission }: { children: ReactNode; permission?: string }) {
  const { user, isLoading, hasPermission } = useAuth();

  if (isLoading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-ink-50 dark:bg-ink-950">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" role="status" aria-label="Loading" />
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  if (permission && !hasPermission(permission)) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center animate-fade-in">
        <div className="w-12 h-12 rounded-full bg-rust-50 dark:bg-rust-500/10 flex items-center justify-center mb-3">
          <ShieldAlert size={20} className="text-rust-500" aria-hidden="true" />
        </div>
        <h2 className="font-display text-lg font-semibold text-ink-800 dark:text-ink-100">Access denied</h2>
        <p className="text-sm text-ink-500 dark:text-ink-400 mt-1">You don't have permission to view this page.</p>
      </div>
    );
  }

  return <>{children}</>;
}
