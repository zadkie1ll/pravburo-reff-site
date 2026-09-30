import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SessionInfo } from "@/features/session/types";

import { RequireAuth } from "./RequireAuth";

const replace = vi.fn();

function renderGuard(session: Partial<SessionInfo>, guard: Parameters<typeof RequireAuth>[0] = {}) {
  vi.stubGlobal("location", { replace });
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            authenticated: true,
            role: "agent",
            onboarding_required: false,
            csrf_token: "t",
            ...session,
          }),
          { status: 200 },
        ),
    ),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Routes>
          <Route element={<RequireAuth {...guard} />}>
            <Route path="/" element={<p>secret</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  replace.mockReset();
});

describe("RequireAuth", () => {
  it("shows the page to a logged-in agent", async () => {
    renderGuard({});
    expect(await screen.findByText("secret")).toBeInTheDocument();
  });

  it("sends a guest to the backend login page", async () => {
    renderGuard({ authenticated: false, role: null });
    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("sends a partner without a format to onboarding, unless allowed", async () => {
    renderGuard({ onboarding_required: true });
    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/onboarding"));
  });

  it("lets the onboarding page itself through", async () => {
    renderGuard({ onboarding_required: true }, { allowOnboarding: true });
    expect(await screen.findByText("secret")).toBeInTheDocument();
  });

  it("shows 403 to the wrong role", async () => {
    renderGuard({}, { role: "admin" });
    expect(await screen.findByText("Нет доступа")).toBeInTheDocument();
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });
});
