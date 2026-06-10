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
import { getAuthRefreshIntervalMs } from "../api/client";
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

const REFRESH_RETRY_ATTEMPTS = 3;
const REFRESH_RETRY_DELAY_MS = 1000;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function refreshSessionWithRetry(): Promise<AuthUser> {
  let lastError: unknown;
  for (let attempt = 0; attempt < REFRESH_RETRY_ATTEMPTS; attempt++) {
    try {
      return await refreshSession();
    } catch (e) {
      lastError = e;
      if (attempt < REFRESH_RETRY_ATTEMPTS - 1) {
        await sleep(REFRESH_RETRY_DELAY_MS * (attempt + 1));
      }
    }
  }
  throw lastError;
}

async function loadSession(): Promise<AuthUser | null> {
  try {
    const user = await getMe();
    if (user) {
      return user;
    }
  } catch (e) {
    if (import.meta.env.DEV) {
      console.warn(
        "[auth] session load failed:",
        e instanceof Error ? e.message : e,
      );
    }
  }

  try {
    return await refreshSessionWithRetry();
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const me = await refreshSessionWithRetry();
      if (mounted.current) setUser(me);
    } catch {
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
