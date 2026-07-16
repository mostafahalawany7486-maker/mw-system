import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { ReactNode } from "react";

export function ProtectedRoute({ children, permission }: { children: ReactNode; permission?: string }) {
  const { user, isLoading, hasPermission } = useAuth();

  if (isLoading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-ink-50 dark:bg-ink-950">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  if (permission && !hasPermission(permission)) {
    return (
      <div className="p-10 text-center">
        <h2 className="text-lg font-semibold">Access denied</h2>
        <p className="text-ink-500 mt-1">You don't have permission to view this page.</p>
      </div>
    );
  }

  return <>{children}</>;
}
