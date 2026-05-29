import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  getMe,
  login as apiLogin,
  logout as apiLogout,
  refreshSession,
} from "../api/auth";
import { ApiError, getAuthRefreshIntervalMs } from "../api/client";
import type { AuthUser } from "../types/auth";
import { isAdminRole } from "../types/auth";

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  updateUser: (user: AuthUser) => void;
}

const AuthContext = createContext<AuthState | null>(null);

async function loadSession(): Promise<AuthUser | null> {
  try {
    return await getMe();
  } catch (e) {
    if (e instanceof ApiError && e.code === "token_expired") {
      await refreshSession();
      return getMe();
    }
    if (import.meta.env.DEV) {
      console.warn(
        "[auth] session load failed:",
        e instanceof Error ? e.message : e,
      );
    }
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const me = await refreshSession();
      if (mounted.current) setUser(me);
    } catch (e) {
      if (mounted.current) setUser(null);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    loadSession()
      .then((data) => {
        if (mounted.current) setUser(data);
      })
      .finally(() => {
        if (mounted.current) setLoading(false);
      });
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (!user) return;

    const intervalMs = getAuthRefreshIntervalMs();
    const id = window.setInterval(() => {
      void refresh();
    }, intervalMs);

    const onVisible = () => {
      if (document.visibilityState === "visible") {
        void refresh();
      }
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [user, refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiLogin(email, password);
    setUser(res);
    return res;
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  const updateUser = useCallback((next: AuthUser) => {
    setUser(next);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      isAdmin: isAdminRole(user?.role),
      login,
      logout,
      refresh,
      updateUser,
    }),
    [user, loading, login, logout, refresh, updateUser],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
