import { getCsrfToken } from "./csrf";

export interface ApiErrorBody {
  code: string;
  message: string;
  fields?: Record<string, string>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: Record<string, string>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.fields = body.fields ?? {};
  }
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface RequestOptions {
  body?: unknown;
  signal?: AbortSignal;
}

async function readError(response: Response): Promise<ApiErrorBody> {
  try {
    const data = (await response.json()) as { error?: ApiErrorBody };
    if (data.error) return data.error;
  } catch {
    // Not JSON (proxy error page, network layer): fall through to the generic error.
  }
  return { code: "http_error", message: `Ошибка запроса (${response.status})` };
}

export async function apiRequest<T>(
  method: Method,
  path: string,
  { body, signal }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRF-Token"] = getCsrfToken();

  const response = await fetch(path, {
    method,
    headers,
    credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw new ApiError(response.status, await readError(response));
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const apiGet = <T>(path: string, signal?: AbortSignal) =>
  apiRequest<T>("GET", path, { signal });

export const apiPost = <T>(path: string, body?: unknown) => apiRequest<T>("POST", path, { body });

export const apiPut = <T>(path: string, body?: unknown) => apiRequest<T>("PUT", path, { body });

export const apiDelete = <T>(path: string) => apiRequest<T>("DELETE", path);
