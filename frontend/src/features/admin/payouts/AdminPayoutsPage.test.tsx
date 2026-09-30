import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, sentBody } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { AdminPayoutsPage } from "./AdminPayoutsPage";
import type { CalendarDay, PayoutsCalendar } from "./types";

const day = (n: number, extra: Partial<CalendarDay> = {}): CalendarDay => ({
  day: n,
  in_month: true,
  is_today: false,
  entries: [],
  ...extra,
});

const CALENDAR: PayoutsCalendar = {
  year: 2026,
  month: 9,
  month_label: "Сентябрь 2026",
  status: "",
  statuses: [
    { value: "scheduled", label: "Запланировано" },
    { value: "overdue", label: "Просрочено" },
    { value: "paid", label: "Выплачено" },
  ],
  overdue_days: 14,
  previous: { year: 2026, month: 8 },
  next: { year: 2026, month: 10 },
  weeks: [
    [
      day(31, { in_month: false }),
      day(1),
      day(2, {
        is_today: true,
        entries: [
          {
            reward_id: 11,
            client_name: "Иван Клиентов",
            amount_label: "3 000 ₽",
            status_slug: "scheduled",
            can_mark_paid: true,
          },
        ],
      }),
      day(3, {
        entries: [
          {
            reward_id: 12,
            client_name: "Пётр Оплатов",
            amount_label: "10 000 ₽",
            status_slug: "paid",
            can_mark_paid: false,
          },
        ],
      }),
      day(4),
      day(5),
      day(6),
    ],
  ],
  overdue_rows: [
    {
      reward_id: 21,
      agent_name: "Ольга Партнёрова",
      client_name: "Мария Опоздалова",
      type_label: "Аванс",
      amount_label: "3 000 ₽",
      target_date_label: "10.09.2026",
    },
  ],
};

const PATH = "/admin/payouts";
const ok = { body: { ok: true } };
const calendar = (extra: Partial<PayoutsCalendar> = {}) => ({ body: { ...CALENDAR, ...extra } });

afterEach(() => vi.unstubAllGlobals());

describe("AdminPayoutsPage", () => {
  it("shows the month with each payout on its day", async () => {
    mockApi({ [PATH]: calendar() });
    renderWithProviders(<AdminPayoutsPage />, PATH);

    expect(await screen.findByText("Сентябрь 2026")).toBeInTheDocument();
    for (const weekday of ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]) {
      expect(screen.getByText(weekday)).toBeInTheDocument();
    }
    const scheduled = screen.getByText("Иван Клиентов · 3 000 ₽").closest(".calendar-entry")!;
    expect(scheduled).toHaveClass("status-scheduled");
    expect(scheduled.closest(".calendar-day")).toHaveClass("calendar-day-today");
    expect(screen.getByText("31").closest(".calendar-day")).toHaveClass("calendar-day-outside");
  });

  it("offers 'mark as paid' only for scheduled and overdue entries", async () => {
    mockApi({ [PATH]: calendar() });
    renderWithProviders(<AdminPayoutsPage />, PATH);
    await screen.findByText("Сентябрь 2026");

    const paid = screen.getByText("Пётр Оплатов · 10 000 ₽").closest(".calendar-entry")!;
    const scheduled = screen.getByText("Иван Клиентов · 3 000 ₽").closest(".calendar-entry")!;
    expect(within(paid as HTMLElement).queryByRole("button")).not.toBeInTheDocument();
    expect(within(scheduled as HTMLElement).getByRole("button")).toBeInTheDocument();
  });

  it("explains the planned date with the current overdue period", async () => {
    mockApi({ [PATH]: calendar() });
    renderWithProviders(<AdminPayoutsPage />, PATH);

    expect(await screen.findByText(/одобрение \+ 14 дн\./)).toBeInTheDocument();
    expect(screen.getByLabelText("Просрочка через, дней")).toHaveValue(14);
  });

  it("lists overdue payouts with their planned date", async () => {
    mockApi({ [PATH]: calendar() });
    renderWithProviders(<AdminPayoutsPage />, PATH);

    const table = (await screen.findByRole("heading", { name: "Просроченные выплаты" })).closest(
      "section",
    )!;
    expect(within(table).getByText("Ольга Партнёрова")).toBeInTheDocument();
    expect(within(table).getByText("10.09.2026")).toBeInTheDocument();
  });

  it("hides the overdue table when nothing is overdue", async () => {
    mockApi({ [PATH]: calendar({ overdue_rows: [] }) });
    renderWithProviders(<AdminPayoutsPage />, PATH);
    await screen.findByText("Сентябрь 2026");

    expect(screen.queryByRole("heading", { name: "Просроченные выплаты" })).not.toBeInTheDocument();
  });

  it("moves between months through the URL, keeping the status", async () => {
    mockApi({ [PATH]: calendar({ status: "paid" }) });
    renderWithProviders(<AdminPayoutsPage />, `${PATH}?year=2026&month=9&status=paid`);

    expect(await screen.findByRole("link", { name: "← Предыдущий месяц" })).toHaveAttribute(
      "href",
      "/admin/payouts?year=2026&month=8&status=paid",
    );
    expect(screen.getByRole("link", { name: "Следующий месяц →" })).toHaveAttribute(
      "href",
      "/admin/payouts?year=2026&month=10&status=paid",
    );
  });

  it("filters by status keeping the month that is on screen", async () => {
    const api = mockApi({ [PATH]: calendar() });
    renderWithProviders(<AdminPayoutsPage />, `${PATH}?year=2026&month=9`);
    const user = userEvent.setup();

    await user.selectOptions(await screen.findByLabelText("Статус"), "overdue");
    await user.click(screen.getByRole("button", { name: "Показать" }));

    await waitFor(() =>
      expect(api.mock.calls.map(([u]) => u)).toContain(
        "/api/v1/site/admin/payouts?year=2026&month=9&status=overdue",
      ),
    );
  });

  it("asks the server for the current month when the URL has none", async () => {
    const api = mockApi({ [PATH]: calendar() });
    renderWithProviders(<AdminPayoutsPage />, PATH);
    await screen.findByText("Сентябрь 2026");

    expect(api.mock.calls.find(([u]) => u.includes(PATH))?.[0]).toBe("/api/v1/site/admin/payouts");
  });

  it("marks a payout paid only after the admin confirms, then reloads", async () => {
    const api = mockApi({ [PATH]: calendar(), "/11/mark-paid": ok });
    const confirm = vi.spyOn(window, "confirm");
    renderWithProviders(<AdminPayoutsPage />, PATH);
    const user = userEvent.setup();
    const button = () =>
      screen.getByRole("button", { name: "Отметить как выплачено: Иван Клиентов, 3 000 ₽" });
    const marked = () => api.mock.calls.some(([u]) => u.endsWith("/11/mark-paid"));
    await screen.findByText("Сентябрь 2026");

    confirm.mockReturnValueOnce(false);
    await user.click(button());
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("отменить это нельзя"));
    expect(marked()).toBe(false);

    confirm.mockReturnValueOnce(true);
    await user.click(button());
    await waitFor(() => expect(marked()).toBe(true));
    confirm.mockRestore();
  });

  it("marks an overdue payout paid from the overdue table", async () => {
    const api = mockApi({ [PATH]: calendar(), "/21/mark-paid": ok });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderWithProviders(<AdminPayoutsPage />, PATH);
    const user = userEvent.setup();

    const table = (await screen.findByRole("heading", { name: "Просроченные выплаты" })).closest(
      "section",
    )!;
    await user.click(within(table).getByRole("button", { name: /Отметить как выплачено/ }));

    await waitFor(() =>
      expect(api.mock.calls.some(([u]) => u.endsWith("/21/mark-paid"))).toBe(true),
    );
    vi.restoreAllMocks();
  });

  it("saves a new overdue period", async () => {
    const api = mockApi({ [PATH]: (body) => (body ? ok : calendar()) });
    renderWithProviders(<AdminPayoutsPage />, PATH);
    const user = userEvent.setup();

    const days = await screen.findByLabelText("Просрочка через, дней");
    await user.clear(days);
    await user.type(days, "30");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    await waitFor(() => expect(sentBody(api, "/settings")).toEqual({ overdue_days: 30 }));
  });

  it("shows why an action was refused", async () => {
    mockApi({
      [PATH]: calendar(),
      "/11/mark-paid": {
        status: 409,
        body: {
          error: { code: "not_payable", message: "Эту выплату нельзя отметить выплаченной" },
        },
      },
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderWithProviders(<AdminPayoutsPage />, PATH);
    const user = userEvent.setup();

    await user.click(
      await screen.findByRole("button", { name: "Отметить как выплачено: Иван Клиентов, 3 000 ₽" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("нельзя отметить выплаченной");
    vi.restoreAllMocks();
  });

  it("shows an error when the calendar cannot be loaded", async () => {
    mockApi({ [PATH]: { status: 500, body: {} } });
    renderWithProviders(<AdminPayoutsPage />, PATH);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
