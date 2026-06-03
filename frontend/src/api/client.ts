const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

/** Access token lifetime on server (minutes) — keep refresh interval below this. */
const ACCESS_TOKEN_MINUTES = Number(
  import.meta.env.VITE_JWT_ACCESS_EXPIRE_MINUTES ?? "15",
);
const REFRESH_INTERVAL_MS = Math.max(
  15_000,
  ACCESS_TOKEN_MINUTES * 60 * 1000 - 10_000,
);

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public retryAfterSeconds?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let refreshInFlight: Promise<void> | null = null;

/** Refresh access token using the httpOnly refresh cookie. */
export async function refreshAccessToken(): Promise<void> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const res = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as {
          error?: string;
          message?: string;
        };
        throw new ApiError(
          body.message ?? "Session expired. Please sign in again.",
          res.status,
          body.error,
        );
      }
      await res.json().catch(() => undefined);
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  await refreshInFlight;
}

const AUTH_NO_RETRY_PATHS = new Set([
  "/api/auth/login",
  "/api/auth/refresh",
  "/api/auth/logout",
]);

type ApiFetchOptions = RequestInit & {
  /** Internal: skip refresh retry (refresh endpoint itself). */
  _skipAuthRetry?: boolean;
};

export async function apiFetch<T>(
  path: string,
  init?: ApiFetchOptions,
): Promise<T> {
  const { _skipAuthRetry, ...requestInit } = init ?? {};

  const doFetch = () =>
    fetch(`${API_BASE}${path}`, {
      ...requestInit,
      credentials: "include",
      headers: {
        ...(!(requestInit.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...requestInit.headers,
      },
    });

  let res = await doFetch();

  if (
    res.status === 401 &&
    !_skipAuthRetry &&
    !AUTH_NO_RETRY_PATHS.has(path)
  ) {
    try {
      await refreshAccessToken();
      res = await doFetch();
    } catch {
      throw new ApiError(
        "Session expired. Please sign in again.",
        401,
        "session_expired",
      );
    }
  }

  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      error?: string;
      message?: string;
      retry_after_seconds?: number;
    };
    throw new ApiError(
      body.message ?? res.statusText,
      res.status,
      body.error,
      body.retry_after_seconds,
    );
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

export function getAuthRefreshIntervalMs(): number {
  return REFRESH_INTERVAL_MS;
}
