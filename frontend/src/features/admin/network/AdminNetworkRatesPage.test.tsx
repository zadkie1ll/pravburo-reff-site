import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, sentBody } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { AdminNetworkRatesPage } from "./AdminNetworkRatesPage";

const RATES = {
  rates: [
    { level: 1, label: "1 уровень (прямой пригласивший)", amount: "500.00" },
    { level: 2, label: "2 уровень (пригласивший пригласившего)", amount: "200.00" },
    { level: 3, label: "3 уровень (только для цепочки из партнёров)", amount: "100.00" },
  ],
};

const PATH = "/network/rates";

afterEach(() => vi.unstubAllGlobals());

describe("AdminNetworkRatesPage", () => {
  it("shows the current amount of every level", async () => {
    mockApi({ [PATH]: { body: RATES } });
    renderWithProviders(<AdminNetworkRatesPage />);

    expect(await screen.findByLabelText(/^1 уровень/)).toHaveValue(500);
    expect(screen.getByLabelText(/^2 уровень/)).toHaveValue(200);
    expect(screen.getByLabelText(/^3 уровень/)).toHaveValue(100);
    expect(screen.getByLabelText(/^1 уровень/)).toHaveAttribute("min", "0");
  });

  it("sends the amounts as typed text and confirms", async () => {
    const api = mockApi({
      [PATH]: (body) => ({
        body: body ? { rates: RATES.rates.map((r) => ({ ...r, amount: "600.50" })) } : RATES,
      }),
    });
    renderWithProviders(<AdminNetworkRatesPage />);
    const user = userEvent.setup();

    const first = await screen.findByLabelText(/^1 уровень/);
    await user.clear(first);
    await user.type(first, "600.5");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    expect(await screen.findByText("Суммы сохранены")).toBeInTheDocument();
    expect(sentBody(api, PATH)).toEqual({
      amount_1: "600.5",
      amount_2: "200.00",
      amount_3: "100.00",
    });
  });

  it("shows the server's reason and keeps what was typed when refused", async () => {
    mockApi({
      [PATH]: (body) =>
        body
          ? {
              status: 400,
              body: {
                error: { code: "validation_error", message: "Сумма не может быть отрицательной" },
              },
            }
          : { body: RATES },
    });
    renderWithProviders(<AdminNetworkRatesPage />);
    const user = userEvent.setup();

    const first = await screen.findByLabelText(/^1 уровень/);
    await user.clear(first);
    await user.type(first, "5");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("отрицательной");
    await waitFor(() => expect(first).toHaveValue(5));
    expect(screen.queryByText("Суммы сохранены")).not.toBeInTheDocument();
  });

  it("shows an error when the rates cannot be loaded", async () => {
    mockApi({ [PATH]: { status: 500, body: {} } });
    renderWithProviders(<AdminNetworkRatesPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
