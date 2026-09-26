"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { getMe, logout, ApiError } from "@/lib/api";
import type { AuthUser } from "@/lib/types";

type AuthStatus = "loading" | "signedIn" | "signedOut";

interface AuthContextValue {
  user: AuthUser | null;
  status: AuthStatus;
  /** True when /auth/me failed for a reason other than being signed out. */
  connectionError: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [connectionError, setConnectionError] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const me = await getMe();
      setUser(me);
      setStatus("signedIn");
      setConnectionError(false);
    } catch (error) {
      setUser(null);
      setConnectionError(
        !(error instanceof ApiError && (error.status === 401 || error.status === 503)),
      );
      setStatus("signedOut");
    }
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logout();
    } catch {
      // Clearing local state is enough even if the API call fails.
    }
    setUser(null);
    setStatus("signedOut");
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({ user, status, connectionError, refresh, signOut }),
    [user, status, connectionError, refresh, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
