import { vi } from "vitest";

export interface Reply {
  status?: number;
  body?: unknown;
}

type Handler = Reply | ((body: unknown) => Reply);

const GUEST_SESSION = {
  authenticated: false,
  email: null,
  role: null,
  onboarding_required: false,
  csrf_token: "tok",
};

const AUTH_CONFIG = { telegram_bot_username: "", telegram_auth_url: "", yandex_enabled: false };

/**
 * Stubs `fetch` for a test. `handlers` is keyed by the URL path suffix (query string ignored) (e.g. "/auth/login");
 * `/me` and `/auth/config` have sensible defaults. Returns the mock to inspect calls.
 */
export function mockApi(handlers: Record<string, Handler> = {}) {
  const all: Record<string, Handler> = {
    "/me": { body: GUEST_SESSION },
    "/auth/config": { body: AUTH_CONFIG },
    ...handlers,
  };
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = url.split("?")[0] ?? url;
    const key = Object.keys(all).find((suffix) => path.endsWith(suffix));
    if (!key) return new Response(JSON.stringify({}), { status: 404 });
    const handler = all[key] as Handler;
    const body = init?.body ? (JSON.parse(String(init.body)) as unknown) : undefined;
    const reply = typeof handler === "function" ? handler(body) : handler;
    return new Response(JSON.stringify(reply.body ?? {}), { status: reply.status ?? 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** The parsed JSON body of the (last) request with a body sent to the URL ending with `suffix`. */
export function sentBody(fetchMock: ReturnType<typeof mockApi>, suffix: string): unknown {
  const call = fetchMock.mock.calls.findLast(([url, init]) => url.endsWith(suffix) && init?.body);
  return call?.[1]?.body ? JSON.parse(String(call[1].body)) : undefined;
}
