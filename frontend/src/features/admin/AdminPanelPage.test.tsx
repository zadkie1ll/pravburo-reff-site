import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { AdminPanelPage } from "./AdminPanelPage";

const PANEL = {
  sections: [
    { title: "Партнёры", description: "Список, поиск.", url: "/admin/partners" },
    { title: "Начисления", description: "Одобрение начислений.", url: "/admin/rewards" },
  ],
};

afterEach(() => vi.unstubAllGlobals());

describe("AdminPanelPage", () => {
  it("lists every section with its description and link", async () => {
    mockApi({ "/site/admin": { body: PANEL } });
    renderWithProviders(<AdminPanelPage />);

    expect(await screen.findByRole("link", { name: "Партнёры" })).toHaveAttribute(
      "href",
      "/admin/partners",
    );
    expect(screen.getByRole("link", { name: "Начисления" })).toHaveAttribute(
      "href",
      "/admin/rewards",
    );
    expect(screen.getByText(/Одобрение начислений\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Выйти" })).toBeInTheDocument();
  });

  it("shows an error when the panel cannot be loaded", async () => {
    mockApi({ "/site/admin": { status: 500, body: {} } });
    renderWithProviders(<AdminPanelPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
