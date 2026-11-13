import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Routes, Route } from "react-router-dom";
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
  it("opens a separate existing-clients section with list and import actions", async () => {
    mockApi({
      "/site/admin": {
        body: {
          sections: [...PANEL.sections, { title: "Действующие клиенты", url: "/admin/clients" }],
        },
      },
    });
    renderWithProviders(
      <Routes>
        <Route path="/admin" element={<AdminPanelPage />} />
      </Routes>,
      "/admin",
    );
    const user = userEvent.setup();
    await user.click(await screen.findByRole("link", { name: "Действующие клиенты" }));
    expect(screen.getByRole("link", { name: "Все действующие клиенты" })).toHaveAttribute(
      "href",
      "/admin/clients",
    );
    expect(screen.getByRole("link", { name: "Добавить клиента" })).toHaveAttribute(
      "href",
      "/admin/clients/new",
    );
    expect(screen.queryByRole("link", { name: "Все заявки" })).not.toBeInTheDocument();
  });

  it("groups tools in application tiles and opens the selected section", async () => {
    mockApi({ "/site/admin": { body: PANEL } });
    renderWithProviders(
      <Routes>
        <Route path="/admin" element={<AdminPanelPage />} />
      </Routes>,
      "/admin",
    );
    const user = userEvent.setup();

    expect(await screen.findByRole("link", { name: "Партнёры" })).toHaveAttribute(
      "href",
      "/admin?section=partners",
    );
    expect(screen.queryByText(/Действий:/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Выплаты" }));
    expect(await screen.findByRole("link", { name: "Начисления" })).toHaveAttribute(
      "href",
      "/admin/rewards",
    );
    await user.click(screen.getByRole("link", { name: "Все разделы" }));
    await user.click(screen.getByRole("link", { name: "Партнёры" }));
    expect(await screen.findByRole("link", { name: "Создать партнёра" })).toHaveAttribute(
      "href",
      "/admin/partners/new",
    );
    expect(screen.getByRole("link", { name: "Редактировать партнёра" })).toHaveAttribute(
      "href",
      "/admin/partners",
    );
    expect(screen.getByRole("button", { name: "Выйти" })).toBeInTheDocument();
  });

  it("shows an error when the panel cannot be loaded", async () => {
    mockApi({ "/site/admin": { status: 500, body: {} } });
    renderWithProviders(<AdminPanelPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
