import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, sentBody } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { AdminPartnersPage } from "./AdminPartnersPage";
import type { Partner, PartnersList } from "./types";

const PARTNER: Partner = {
  id: 7,
  display_name: "Ольга Партнёрова",
  email: "olga@example.com",
  phone: "+79990001122",
  is_active: true,
  is_admin: false,
  blocked_reason: null,
  client_count: 3,
  total_paid: "9000.00",
  payout_details: "Карта 1234",
  admin_note: "звонить после 18",
};

const list = (rows: Partner[], extra: Partial<PartnersList> = {}): { body: PartnersList } => ({
  body: {
    rows,
    page: 1,
    total_pages: 1,
    total_count: rows.length,
    statuses: [
      { value: "active", label: "Активные" },
      { value: "blocked", label: "Заблокированные" },
    ],
    ...extra,
  },
});

const PATH = "/admin/partners";

afterEach(() => vi.unstubAllGlobals());

describe("AdminPartnersPage", () => {
  it("lists partners with their figures", async () => {
    mockApi({ [PATH]: list([PARTNER]) });
    renderWithProviders(<AdminPartnersPage />, PATH);

    expect(await screen.findByText("Ольга Партнёрова")).toBeInTheDocument();
    expect(screen.getByText("olga@example.com", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Активен")).toBeInTheDocument();
    expect(screen.getByText("9000.00")).toBeInTheDocument();
    expect(screen.getByText("Карта 1234")).toBeInTheDocument();
    expect(screen.getByText("Всего: 1")).toBeInTheDocument();
    expect(screen.getByLabelText(/^Заметка:/)).toHaveValue("звонить после 18");
  });

  it("falls back to placeholders for missing data", async () => {
    mockApi({
      [PATH]: list([
        { ...PARTNER, display_name: "", email: null, phone: null, payout_details: null },
      ]),
    });
    renderWithProviders(<AdminPartnersPage />, PATH);

    expect(await screen.findByText("Без имени")).toBeInTheDocument();
  });

  it("searches and filters through the URL", async () => {
    const api = mockApi({ [PATH]: list([PARTNER]) });
    renderWithProviders(<AdminPartnersPage />, PATH);
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Найти по имени, почте или телефону"), "olga");
    await user.selectOptions(screen.getByLabelText("Статус"), "active");
    await user.click(screen.getByRole("button", { name: "Искать" }));

    await waitFor(() =>
      expect(api.mock.calls.map(([u]) => u)).toContain(
        "/api/v1/site/admin/partners?q=olga&status=active",
      ),
    );
  });

  it("saves a note", async () => {
    const api = mockApi({ [PATH]: list([PARTNER]), "/7/note": { body: { ok: true } } });
    renderWithProviders(<AdminPartnersPage />, PATH);
    const user = userEvent.setup();

    const note = await screen.findByLabelText(/^Заметка:/);
    await user.clear(note);
    await user.type(note, "VIP");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    await waitFor(() => expect(sentBody(api, "/7/note")).toEqual({ note: "VIP" }));
  });

  it("blocks with a reason, and requires one", async () => {
    let blocked = false;
    const api = mockApi({
      [PATH]: () =>
        list([
          blocked ? { ...PARTNER, is_active: false, blocked_reason: "Мошенничество" } : PARTNER,
        ]),
      "/7/block": () => {
        blocked = true;
        return { body: { ok: true } };
      },
    });
    renderWithProviders(<AdminPartnersPage />, PATH);
    const user = userEvent.setup();

    const reason = await screen.findByLabelText(/^Причина блокировки:/);
    expect(reason).toBeRequired();
    await user.type(reason, "Мошенничество");
    await user.click(screen.getByRole("button", { name: "Заблокировать" }));

    expect(await screen.findByText("Заблокирован")).toBeInTheDocument();
    expect(screen.getByText("Мошенничество")).toBeInTheDocument();
    expect(sentBody(api, "/7/block")).toEqual({ reason: "Мошенничество" });
    expect(screen.queryByRole("button", { name: "Заблокировать" })).not.toBeInTheDocument();
  });

  it("unblocks a blocked partner", async () => {
    let blocked = true;
    const api = mockApi({
      [PATH]: () =>
        list([blocked ? { ...PARTNER, is_active: false, blocked_reason: "Спам" } : PARTNER]),
      "/7/unblock": () => {
        blocked = false;
        return { body: { ok: true } };
      },
    });
    renderWithProviders(<AdminPartnersPage />, PATH);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Разблокировать" }));

    expect(await screen.findByText("Активен")).toBeInTheDocument();
    expect(api.mock.calls.some(([u]) => u.endsWith("/7/unblock"))).toBe(true);
  });

  it("offers no blocking for an administrator", async () => {
    mockApi({ [PATH]: list([{ ...PARTNER, is_admin: true }]) });
    renderWithProviders(<AdminPartnersPage />, PATH);

    await screen.findByText("Ольга Партнёрова");
    expect(screen.queryByRole("button", { name: "Заблокировать" })).not.toBeInTheDocument();
  });

  it("shows why a change was refused", async () => {
    mockApi({
      [PATH]: list([PARTNER]),
      "/7/block": {
        status: 400,
        body: {
          error: { code: "cannot_block_admin", message: "Администратора заблокировать нельзя" },
        },
      },
    });
    renderWithProviders(<AdminPartnersPage />, PATH);
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText(/^Причина блокировки:/), "x");
    await user.click(screen.getByRole("button", { name: "Заблокировать" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Администратора заблокировать нельзя",
    );
  });

  it("paginates keeping the filters", async () => {
    mockApi({ [PATH]: list([PARTNER], { page: 2, total_pages: 3 }) });
    renderWithProviders(<AdminPartnersPage />, `${PATH}?q=olga&page=2`);

    expect(await screen.findByText("Страница 2 из 3")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Вперёд →" })).toHaveAttribute(
      "href",
      expect.stringMatching(/q=olga.*page=3/),
    );
  });

  it("says so when nothing is found, and when loading fails", async () => {
    mockApi({ [PATH]: list([]) });
    const first = renderWithProviders(<AdminPartnersPage />, PATH);
    expect(await screen.findByText("Партнёры не найдены")).toBeInTheDocument();
    first.unmount();

    mockApi({ [PATH]: { status: 500, body: {} } });
    renderWithProviders(<AdminPartnersPage />, PATH);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
