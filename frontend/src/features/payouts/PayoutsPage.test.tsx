import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { PayoutsPage } from "./PayoutsPage";

const PAYOUTS = {
  rows: [
    {
      payout_date_label: "30.09.2026",
      client_name: "Иван Клиентов",
      type_label: "Аванс",
      amount_label: "3 000 ₽",
      status_label: "Выплачено",
      status_slug: "paid",
      rejection_reason: "",
    },
    {
      payout_date_label: "—",
      client_name: "Пётр Отказов",
      type_label: "Основная выплата",
      amount_label: "10 000 ₽",
      status_label: "Отклонено",
      status_slug: "rejected",
      rejection_reason: "Клиент отказался от договора",
    },
  ],
  reward_types: [
    { value: "advance", label: "Аванс" },
    { value: "main", label: "Основная выплата" },
  ],
  statuses: [
    { value: "paid", label: "Выплачено" },
    { value: "rejected", label: "Отклонено" },
  ],
};

afterEach(() => vi.unstubAllGlobals());

describe("PayoutsPage", () => {
  it("shows the payouts with a status pill and the rejection reason", async () => {
    mockApi({ "/site/payouts": { body: PAYOUTS } });
    renderWithProviders(<PayoutsPage />, "/payouts");

    expect(await screen.findByText("Иван Клиентов")).toBeInTheDocument();
    expect(screen.getByText("Выплачено", { selector: ".status-pill" })).toHaveClass("status-paid");
    expect(screen.getByText("Клиент отказался от договора")).toBeInTheDocument();
  });

  it("starts from the filters in the URL and links the PDF with them", async () => {
    const api = mockApi({ "/site/payouts": { body: PAYOUTS } });
    renderWithProviders(<PayoutsPage />, "/payouts?month=2026-09&status=paid");

    const pdf = await screen.findByRole("link", { name: "Экспорт в PDF" });
    expect(pdf).toHaveAttribute("href", "/payouts/export.pdf?month=2026-09&status=paid");
    expect(screen.getByLabelText("Месяц")).toHaveValue("2026-09");
    expect(screen.getByLabelText("Статус")).toHaveValue("paid");
    const url = api.mock.calls.find(([u]) => u.includes("/site/payouts"))?.[0];
    expect(url).toBe("/api/v1/site/payouts?month=2026-09&status=paid");
  });

  it("reloads with the chosen filters when 'Показать' is pressed", async () => {
    const api = mockApi({ "/site/payouts": { body: PAYOUTS } });
    renderWithProviders(<PayoutsPage />, "/payouts");
    const user = userEvent.setup();

    await user.selectOptions(await screen.findByLabelText("Тип выплаты"), "main");
    await user.click(screen.getByRole("button", { name: "Показать" }));

    await waitFor(() =>
      expect(api.mock.calls.map(([u]) => u)).toContain("/api/v1/site/payouts?reward_type=main"),
    );
    // The PDF link follows the applied filter.
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Экспорт в PDF" })).toHaveAttribute(
        "href",
        "/payouts/export.pdf?reward_type=main",
      ),
    );
  });

  it("says so when nothing matches", async () => {
    mockApi({ "/site/payouts": { body: { ...PAYOUTS, rows: [] } } });
    renderWithProviders(<PayoutsPage />, "/payouts");

    expect(await screen.findByText("Выплат по выбранным фильтрам нет")).toBeInTheDocument();
  });

  it("shows an error when loading fails", async () => {
    mockApi({ "/site/payouts": { status: 500, body: {} } });
    renderWithProviders(<PayoutsPage />, "/payouts");

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
