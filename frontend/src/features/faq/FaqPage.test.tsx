import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/renderWithProviders";

import { FaqPage } from "./FaqPage";

const faqBody = {
  items: [{ question: "Когда я получу деньги?", answer: "После оплаты клиентом." }],
  telegram_manager_url: "https://t.me/manager",
  telegram_materials_url: "https://t.me/materials",
};

function mockApi(authenticated: boolean) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const body = url.endsWith("/me")
        ? { authenticated, role: authenticated ? "agent" : null, csrf_token: "t" }
        : faqBody;
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("FaqPage", () => {
  it("renders questions and external links for a guest", async () => {
    mockApi(false);
    renderWithProviders(<FaqPage />);

    expect(await screen.findByText("Когда я получу деньги?")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть материалы" })).toHaveAttribute(
      "href",
      "https://t.me/materials",
    );
    expect(screen.getByRole("link", { name: "Написать менеджеру" })).toHaveAttribute(
      "href",
      "https://t.me/manager",
    );
    expect(screen.queryByText("← Вернуться в кабинет")).not.toBeInTheDocument();
  });

  it("shows the way back to the cabinet for a logged-in agent", async () => {
    mockApi(true);
    renderWithProviders(<FaqPage />);

    expect(await screen.findByText("← Вернуться в кабинет")).toBeInTheDocument();
  });
});
