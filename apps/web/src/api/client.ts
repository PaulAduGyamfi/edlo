export type ApiError = {
    name: "ApiError";
    status: number;
    detail: string;
    traceId: string | null;
    retryable: boolean;
  };
  
  const RETRYABLE = new Set([408, 429, 500, 502, 503, 504]);
  
  export function isApiError(e: unknown): e is ApiError {
    return (
      typeof e === "object" && e !== null && (e as ApiError).name === "ApiError"
    );
  }
  
  export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
    const res = await fetch(`${import.meta.env.VITE_API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${localStorage.getItem("edlo_token") ?? ""}`,
        ...init.headers,
      },
    });
  
    const traceId = res.headers.get("X-Trace-Id");
  
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw {
        name: "ApiError",
        status: res.status,
        detail: body.detail ?? "Request failed",
        traceId,
        retryable: RETRYABLE.has(res.status),
      } satisfies ApiError;
    }
  
    return res.status === 204 ? (undefined as T) : res.json();
  }