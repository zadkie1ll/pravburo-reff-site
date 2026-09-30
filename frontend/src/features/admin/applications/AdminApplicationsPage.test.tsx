import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, sentBody } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { AdminApplicationsPage } from "./AdminApplicationsPage";
import type { ApplicationsList } from "./types";

const LIST: ApplicationsList = {
  rows: [
    {
      id: 11,
      client_name: "Иван Клиентов",
      phone: "+79991112233",
      agent_name: "Ольга Партнёрова",
      agent_email: "olga@example.com",
      city: "Казань",
      debt_amount: null,
      delivery_label: "Ошибка отправки",
      delivery_error: "ConnectionError",
      processing_status: "new",
      assigned_manager_id: null,
      created_at_label: "30.09.2026 10:15",
    },
  ],
  page: 1,
  total_pages: 1,
  total_count: 1,
  delivery_statuses: [
    { value: "pending", label: "Ожидает отправки" },
    { value: "failed", label: "Ошибка отправки" },
  ],
  processing_statuses: [
    { value: "new", label: "Новая" },
    { value: "in_progress", label: "В работе" },
    { value: "closed", label: "Закрыта" },
  ],
  managers: [{ id: 5, label: "Админ Главный" }],
};

const LIST_PATH = "/admin/applications";

afterEach(() => vi.unstubAllGlobals());

describe("AdminApplicationsPage", () => {
  it("lists the applications with delivery details", async () => {
    mockApi({ [LIST_PATH]: { body: LIST } });
    renderWithProviders(<AdminApplicationsPage />, "/admin/applications");

    expect(await screen.findByText("Иван Клиентов")).toBeInTheDocument();
    expect(screen.getByText("Ольга Партнёрова", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("ConnectionError")).toBeInTheDocument();
    expect(screen.getByText("Всего: 1")).toBeInTheDocument();
    expect(screen.getByLabelText("Обработка: Иван Клиентов")).toHaveValue("new");
    expect(screen.getByLabelText("Менеджер: Иван Клиентов")).toHaveValue("");
  });

  it("searches from the first page and keeps the filters in the URL", async () => {
    const api = mockApi({ [LIST_PATH]: { body: LIST } });
    renderWithProviders(<AdminApplicationsPage />, "/admin/applications?page=3");
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Найти по имени или телефону"), " Иван ");
    await user.selectOptions(screen.getByLabelText("Статус доставки в Битрикс"), "failed");
    await user.click(screen.getByRole("button", { name: "Искать" }));

    await waitFor(() =>
      expect(api.mock.calls.map(([u]) => u)).toContain(
        "/api/v1/site/admin/applications?q=%D0%98%D0%B2%D0%B0%D0%BD&status=failed",
      ),
    );
  });

  it("starts from the filters and page in the URL", async () => {
    const api = mockApi({ [LIST_PATH]: { body: { ...LIST, page: 2, total_pages: 3 } } });
    renderWithProviders(
      <AdminApplicationsPage />,
      "/admin/applications?q=Иван&status=failed&page=2",
    );

    expect(await screen.findByLabelText("Найти по имени или телефону")).toHaveValue("Иван");
    expect(screen.getByLabelText("Статус доставки в Битрикс")).toHaveValue("failed");
    const url = api.mock.calls.find(([u]) => u.includes("/admin/applications"))?.[0];
    expect(url).toContain("status=failed");
    expect(url).toContain("page=2");
  });

  it("shows pagination that keeps the filters", async () => {
    mockApi({ [LIST_PATH]: { body: { ...LIST, page: 2, total_pages: 3 } } });
    renderWithProviders(<AdminApplicationsPage />, "/admin/applications?q=Иван&page=2");

    expect(await screen.findByText("Страница 2 из 3")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← Назад" })).toHaveAttribute(
      "href",
      expect.stringContaining("q="),
    );
    expect(screen.getByRole("link", { name: "Вперёд →" })).toHaveAttribute(
      "href",
      expect.stringContaining("page=3"),
    );
  });

  it("hides pagination for a single page", async () => {
    mockApi({ [LIST_PATH]: { body: LIST } });
    renderWithProviders(<AdminApplicationsPage />, "/admin/applications");

    await screen.findByText("Иван Клиентов");
    expect(screen.queryByRole("navigation", { name: "Страницы" })).not.toBeInTheDocument();
  });

  it("saves a new processing status and reloads the list", async () => {
    let status = "new";
    const api = mockApi({
      [LIST_PATH]: () => ({
        body: { ...LIST, rows: [{ ...LIST.rows[0], processing_status: status }] },
      }),
      "/11/status": (body) => {
        status = (body as { processing_status: string }).processing_status;
        return { body: { ok: true } };
      },
    });
    renderWithProviders(<AdminApplicationsPage />, "/admin/applications");
    const user = userEvent.setup();

    await user.selectOptions(
      await screen.findByLabelText("Обработка: Иван Клиентов"),
      "in_progress",
    );

    await waitFor(() =>
      expect(screen.getByLabelText("Обработка: Иван Клиентов")).toHaveValue("in_progress"),
    );
    expect(sentBody(api, "/11/status")).toEqual({ processing_status: "in_progress" });
  });

  it("assigns a manager and can clear the assignment", async () => {
    let manager: number | null = null;
    const api = mockApi({
      [LIST_PATH]: () => ({
        body: { ...LIST, rows: [{ ...LIST.rows[0], assigned_manager_id: manager }] },
      }),
      "/11/manager": (body) => {
        manager = (body as { manager_id: number | null }).manager_id;
        return { body: { ok: true } };
      },
    });
    renderWithProviders(<AdminApplicationsPage />, "/admin/applications");
    const user = userEvent.setup();

    const select = await screen.findByLabelText("Менеджер: Иван Клиентов");
    await user.selectOptions(select, "5");
    await waitFor(() => expect(sentBody(api, "/11/manager")).toEqual({ manager_id: 5 }));
    await waitFor(() => expect(select).toHaveValue("5"));

    await user.selectOptions(select, "");
    await waitFor(() => expect(sentBody(api, "/11/manager")).toEqual({ manager_id: null }));
  });

  it("shows why a change was refused", async () => {
    mockApi({
      [LIST_PATH]: { body: LIST },
      "/11/manager": {
        status: 400,
        body: {
          error: { code: "invalid_manager", message: "Менеджером может быть только администратор" },
        },
      },
    });
    renderWithProviders(<AdminApplicationsPage />, "/admin/applications");
    const user = userEvent.setup();

    await user.selectOptions(await screen.findByLabelText("Менеджер: Иван Клиентов"), "5");

    expect(await screen.findByRole("alert")).toHaveTextContent("только администратор");
  });

  it("says so when nothing is found", async () => {
    mockApi({ [LIST_PATH]: { body: { ...LIST, rows: [], total_count: 0 } } });
    renderWithProviders(<AdminApplicationsPage />, "/admin/applications");

    expect(await screen.findByText("Заявки не найдены")).toBeInTheDocument();
  });

  it("shows an error when the list cannot be loaded", async () => {
    mockApi({ [LIST_PATH]: { status: 500, body: {} } });
    renderWithProviders(<AdminApplicationsPage />, "/admin/applications");

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
