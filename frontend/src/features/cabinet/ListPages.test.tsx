import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { ApplicationsPage } from "./ApplicationsPage";
import { VisitsPage } from "./VisitsPage";

afterEach(() => vi.unstubAllGlobals());

describe("VisitsPage", () => {
  it("lists visits per day with a total and a way back", async () => {
    mockApi({
      "/cabinet/visits": {
        body: {
          days: [
            { day_label: "30.09.2026", count: 4 },
            { day_label: "29.09.2026", count: 1 },
          ],
          total: 5,
        },
      },
    });
    renderWithProviders(<VisitsPage />);

    expect(await screen.findByText("30.09.2026")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "5" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← Вернуться в кабинет" })).toHaveAttribute(
      "href",
      "/cabinet",
    );
  });

  it("says so when there are no visits, without a total row", async () => {
    mockApi({ "/cabinet/visits": { body: { days: [], total: 0 } } });
    renderWithProviders(<VisitsPage />);

    expect(await screen.findByText("Переходов по ссылке пока нет")).toBeInTheDocument();
    expect(screen.queryByText("Всего")).not.toBeInTheDocument();
  });
});

describe("ApplicationsPage", () => {
  it("lists the applications with the masked phone and status", async () => {
    mockApi({
      "/cabinet/applications": {
        body: {
          rows: [
            {
              client_name: "Иван Клиентов",
              masked_phone: "+7 999 ***-**-11",
              created_at_label: "01.09.2026",
              status: "Заявка получена",
            },
          ],
        },
      },
    });
    renderWithProviders(<ApplicationsPage />);

    expect(await screen.findByText("Иван Клиентов", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("+7 999 ***-**-11")).toBeInTheDocument();
    expect(screen.getByText("Заявка получена")).toBeInTheDocument();
  });

  it("says so when there are no applications", async () => {
    mockApi({ "/cabinet/applications": { body: { rows: [] } } });
    renderWithProviders(<ApplicationsPage />);

    expect(await screen.findByText("Заявок пока нет")).toBeInTheDocument();
  });

  it("shows an error when loading fails", async () => {
    mockApi({ "/cabinet/applications": { status: 500, body: {} } });
    renderWithProviders(<ApplicationsPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
