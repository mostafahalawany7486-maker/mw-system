import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from "react";
import apiClient, { setTokens, clearTokens } from "@/api/client";
import { CurrentUser } from "@/types";

interface AuthContextValue {
  user: CurrentUser | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasPermission: (code: string) => boolean;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchMe = useCallback(async () => {
    try {
      const { data } = await apiClient.get<CurrentUser>("/auth/me");
      setUser(data);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("pms_access_token");
    if (token) {
      fetchMe();
    } else {
      setIsLoading(false);
    }
  }, [fetchMe]);

  const login = async (email: string, password: string) => {
    const { data } = await apiClient.post("/auth/login", { email, password });
    setTokens(data.access_token, data.refresh_token);
    await fetchMe();
  };

  const logout = async () => {
    try {
      await apiClient.post("/auth/logout");
    } catch {
      // Ignore network errors on logout — clear local session regardless.
    }
    clearTokens();
    setUser(null);
  };

  const hasPermission = (code: string) => {
    if (!user) return false;
    return user.is_superuser || user.permissions.includes("*") || user.permissions.includes(code);
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, hasPermission, refreshMe: fetchMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
