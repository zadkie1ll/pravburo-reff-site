import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { AdminNetworkTreePage } from "./AdminNetworkTreePage";
import type { NetworkTreeResponse } from "./types";

const PATH = "/network/tree";
const EMPTY: NetworkTreeResponse = { matches: [], root: null, tree: null };

const leaf = (id: number, name: string) => ({
  id,
  name,
  email: null,
  phone: null,
  is_active: true,
  children: [],
});

afterEach(() => vi.unstubAllGlobals());

describe("AdminNetworkTreePage", () => {
  it("starts with just the search box", async () => {
    mockApi({ [PATH]: { body: EMPTY } });
    renderWithProviders(<AdminNetworkTreePage />, "/admin/network/tree");

    expect(await screen.findByLabelText("Найти партнёра по имени или почте")).toBeInTheDocument();
    expect(screen.queryByText(/^Дерево:/)).not.toBeInTheDocument();
    expect(screen.queryByText("Ничего не найдено")).not.toBeInTheDocument();
  });

  it("puts the search into the URL and lists the matches as links to their trees", async () => {
    const api = mockApi({
      [PATH]: (_body) => ({
        body: {
          ...EMPTY,
          matches: [{ id: 5, label: "Ольга Партнёрова", email: "olga@example.com" }],
        },
      }),
    });
    renderWithProviders(<AdminNetworkTreePage />, "/admin/network/tree");
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Найти партнёра по имени или почте"), "Ольга");
    await user.click(screen.getByRole("button", { name: "Искать" }));

    const link = await screen.findByRole("link", { name: "Ольга Партнёрова" });
    expect(link).toHaveAttribute("href", "/admin/network/tree?root=5");
    expect(screen.getByText(/olga@example.com/)).toBeInTheDocument();
    expect(api.mock.calls.map(([u]) => u)).toContain(
      "/api/v1/site/admin/network/tree?q=%D0%9E%D0%BB%D1%8C%D0%B3%D0%B0",
    );
  });

  it("says so when nothing matches", async () => {
    mockApi({ [PATH]: { body: EMPTY } });
    renderWithProviders(<AdminNetworkTreePage />, "/admin/network/tree?q=никто");

    expect(await screen.findByText("Ничего не найдено")).toBeInTheDocument();
  });

  it("shows the chosen partner's tree with a way back to the search", async () => {
    mockApi({
      [PATH]: {
        body: {
          matches: [],
          root: { id: 5, label: "Ольга Партнёрова" },
          tree: { ...leaf(5, "Ольга Партнёрова"), children: [leaf(6, "Вася Ребёнков")] },
        },
      },
    });
    renderWithProviders(<AdminNetworkTreePage />, "/admin/network/tree?q=Ольга&root=5");

    expect(await screen.findByText("Дерево: Ольга Партнёрова")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Дерево сети партнёров" })).toBeInTheDocument();
    // The name is both the label and (with no e-mail or phone) the tooltip of the node.
    expect(screen.getAllByText("Вася Ребёнков").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "← Назад к поиску" })).toHaveAttribute(
      "href",
      expect.stringContaining("q="),
    );
  });

  it("ignores a broken root in the URL", async () => {
    const api = mockApi({ [PATH]: { body: EMPTY } });
    renderWithProviders(<AdminNetworkTreePage />, "/admin/network/tree?root=abc");

    await screen.findByLabelText("Найти партнёра по имени или почте");
    expect(api.mock.calls.some(([u]) => u.includes("root="))).toBe(false);
  });

  it("shows an error when the network cannot be loaded", async () => {
    mockApi({ [PATH]: { status: 500, body: {} } });
    renderWithProviders(<AdminNetworkTreePage />, "/admin/network/tree");

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
