export class ApiRequestError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

type QueryValue = string | number | boolean | null | undefined;

export function queryString(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const serialised = search.toString();
  return serialised ? `?${serialised}` : "";
}

const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

function resolvePath(path: string): string {
  return DEMO_MODE ? path.replace(/^\/api\/v1/, "/demo-api/v1") : path;
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  refreshInFlight ??= fetch(resolvePath("/api/v1/auth/refresh"), {
    method: "POST",
    credentials: "include",
  })
    .then((response) => response.ok)
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  allowRetry = true,
): Promise<T> {
  const response = await fetch(resolvePath(path), {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  // A 15-minute access token will expire during normal use; rotate it once and retry.
  if (response.status === 401 && allowRetry) {
    const refreshed = await refreshSession();
    if (refreshed) {
      return request<T>(path, init, false);
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : "Something went wrong.";
    throw new ApiRequestError(detail, response.status, payload?.code);
  }

  return payload as T;
}

function body(value: unknown): BodyInit | undefined {
  return value === undefined ? undefined : JSON.stringify(value);
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, payload?: unknown) =>
    request<T>(path, { method: "POST", body: body(payload) }),
  patch: <T>(path: string, payload: unknown) =>
    request<T>(path, { method: "PATCH", body: body(payload) }),
  put: <T>(path: string, payload: unknown) =>
    request<T>(path, { method: "PUT", body: body(payload) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
