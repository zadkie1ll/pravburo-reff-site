import { afterEach, describe, expect, it, vi } from "vitest";

import { apiGet, apiPost, ApiError } from "./client";
import { setCsrfToken } from "./csrf";

function stubFetch(status: number, body?: unknown) {
  const fetchMock = vi.fn(
    async (_url: string, _init?: RequestInit) =>
      new Response(body === undefined ? null : JSON.stringify(body), { status }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("apiRequest", () => {
  it("does not send a CSRF header on GET", async () => {
    const fetchMock = stubFetch(200, { ok: true });
    await apiGet("/api/x");

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.headers).not.toHaveProperty("X-CSRF-Token");
  });

  it("sends the CSRF token and a JSON body on POST", async () => {
    setCsrfToken("tok");
    const fetchMock = stubFetch(200, { ok: true });
    await apiPost("/api/x", { a: 1 });

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.headers).toMatchObject({
      "X-CSRF-Token": "tok",
      "Content-Type": "application/json",
    });
    expect(init.body).toBe('{"a":1}');
  });

  it("turns the backend error format into an ApiError", async () => {
    stubFetch(403, {
      error: { code: "forbidden", message: "Недостаточно прав", fields: { a: "b" } },
    });

    const error = await apiGet("/api/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 403,
      code: "forbidden",
      message: "Недостаточно прав",
      fields: { a: "b" },
    });
  });

  it("survives a non-JSON error body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("<html>502</html>", { status: 502 })),
    );

    await expect(apiGet("/api/x")).rejects.toMatchObject({ status: 502, code: "http_error" });
  });

  it("returns undefined for 204", async () => {
    stubFetch(204);
    await expect(apiPost("/api/x")).resolves.toBeUndefined();
  });
});
