// Thin fetch wrapper. Every failure becomes an ApiError so the UI has one
// shape to render: a status, a human detail, and the trace id to quote.

export type ApiError = {
  name: "ApiError";
  status: number; // 0 = never reached the server
  detail: string;
  traceId: string | null;
  retryable: boolean;
};

const RETRYABLE = new Set([0, 408, 429, 500, 502, 503, 504]);

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "";

export const NETWORK_DETAIL =
  "Can't reach the Edlo server. Check it is running and that you are online.";

const TOKEN_KEY = "edlo_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Private mode or blocked storage: the session simply won't survive a reload.
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore
  }
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// The session provider registers a handler so a 401 anywhere signs the user out.
let unauthorizedHandler: (() => void) | null = null;

export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

export function notifyUnauthorized(): void {
  unauthorizedHandler?.();
}

export function isApiError(e: unknown): e is ApiError {
  return (
    typeof e === "object" && e !== null && (e as ApiError).name === "ApiError"
  );
}

export function makeError(
  status: number,
  detail: string,
  traceId: string | null,
): ApiError {
  return {
    name: "ApiError",
    status,
    detail,
    traceId,
    retryable: RETRYABLE.has(status),
  };
}

/** Anything thrown → ApiError, so catch blocks never have to special-case. */
export function toApiError(e: unknown): ApiError {
  if (isApiError(e)) return e;
  const message = e instanceof Error ? e.message : "Something went wrong";
  return makeError(0, message, null);
}

/**
 * FastAPI puts a string in `detail` for HTTPException and a list of
 * {loc, msg} objects for validation errors. Flatten both to one sentence.
 */
export function detailOf(body: unknown, fallback: string): string {
  if (typeof body === "string" && body) return body;
  if (body && typeof body === "object") {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail) return detail;
    if (Array.isArray(detail)) {
      const parts = detail.map((item) => {
        const loc = Array.isArray(item?.loc)
          ? item.loc
              .filter((x: unknown) => typeof x === "string" && x !== "body")
              .join(".")
          : "";
        const msg = typeof item?.msg === "string" ? item.msg : "invalid value";
        return loc ? `${loc}: ${msg}` : msg;
      });
      if (parts.length) return parts.join("; ");
    }
  }
  return fallback;
}

export async function handleResponse<T>(res: Response): Promise<T> {
  const traceId = res.headers.get("X-Trace-Id");
  if (!res.ok) {
    const body: unknown = await res.json().catch(() => null);
    if (res.status === 401) notifyUnauthorized();
    throw makeError(
      res.status,
      detailOf(body, res.statusText || "Request failed"),
      traceId,
    );
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

type Init = Omit<RequestInit, "headers"> & { headers?: Record<string, string> };

export async function api<T>(path: string, init: Init = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
        ...init.headers,
      },
    });
  } catch {
    throw makeError(0, NETWORK_DETAIL, null);
  }
  return handleResponse<T>(res);
}
