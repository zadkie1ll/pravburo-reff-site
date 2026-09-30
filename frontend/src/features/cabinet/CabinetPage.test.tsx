import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { CabinetPage } from "./CabinetPage";
import type { Cabinet } from "./types";

const CABINET: Cabinet = {
  name: "Партнёр Тестов",
  referral_url: "https://agents.example/r/abc",
  finance: {
    total_paid_label: "10 000 ₽",
    this_month_label: "3 000 ₽",
    pending_total_label: "5 000 ₽",
    pending_groups: [{ label: "Ждём выплаты", amount_label: "5 000 ₽" }],
  },
  link_stats: { visits: 40, applications: 8, contracts: 2, conversion_rate_label: "20%" },
  level: {
    level: "active",
    label: "Актив",
    contracts_count: 2,
    contracts_word: "договора",
    is_manual: false,
    nodes: [
      { level: "start", label: "Старт", range_label: "1", is_reached: true, is_current: false },
      { level: "active", label: "Актив", range_label: "2–3", is_reached: true, is_current: true },
      { level: "pro", label: "Про", range_label: "4–5", is_reached: false, is_current: false },
      {
        level: "expert",
        label: "Эксперт",
        range_label: "6+",
        is_reached: false,
        is_current: false,
      },
    ],
    segment_fills: [100, 20, 0],
    next_level_label: "Про",
    contracts_to_next: 2,
    contracts_to_next_word: "договора",
  },
  clients: [
    {
      client_name: "Клиент Клиентов",
      masked_phone: "+7 999 ***-**-11",
      created_at_label: "01.09.2026",
      stage: "Анализ",
      reward_summary: "Аванс: ждём",
      reward_totals: "0 ₽ · 3 000 ₽",
    },
  ],
};

afterEach(() => vi.unstubAllGlobals());

describe("CabinetPage", () => {
  it("shows the finance, link, level and client blocks", async () => {
    mockApi({ "/site/cabinet": { body: CABINET } });
    renderWithProviders(<CabinetPage />);

    expect(await screen.findByRole("heading", { name: "Партнёр Тестов" })).toBeInTheDocument();
    expect(screen.getByText("10 000 ₽")).toBeInTheDocument();
    expect(screen.getByText("Ждём выплаты")).toBeInTheDocument();
    expect(screen.getByLabelText("Реферальная ссылка")).toHaveValue("https://agents.example/r/abc");
    expect(screen.getByAltText("QR-код реферальной ссылки")).toHaveAttribute(
      "src",
      "/cabinet/referral-qr.png",
    );
    expect(screen.getByText("Клиент Клиентов", { exact: false })).toBeInTheDocument();
  });

  it("links the stats rows to the pages behind them", async () => {
    mockApi({ "/site/cabinet": { body: CABINET } });
    renderWithProviders(<CabinetPage />);

    const visits = await screen.findByRole("link", { name: "Переходов по ссылке →" });
    expect(visits).toHaveAttribute("href", "/cabinet/visits");
    expect(screen.getByRole("link", { name: "Оставлено заявок →" })).toHaveAttribute(
      "href",
      "/cabinet/applications",
    );
    expect(screen.getByRole("cell", { name: "20%" })).toBeInTheDocument();
  });

  it("explains how far the next level is, with the plural from the backend", async () => {
    mockApi({ "/site/cabinet": { body: CABINET } });
    renderWithProviders(<CabinetPage />);

    expect(await screen.findByText(/Ещё 2 договора — и уровень Про\./)).toBeInTheDocument();
    expect(screen.getByText("2 договора с начала месяца")).toBeInTheDocument();
    const badge = screen.getByText("Актив", { selector: ".level-badge" });
    expect(badge).toHaveClass("level-badge-active");
  });

  it("says so when an admin set the level by hand", async () => {
    const manual = { ...CABINET, level: { ...CABINET.level, is_manual: true } };
    mockApi({ "/site/cabinet": { body: manual } });
    renderWithProviders(<CabinetPage />);

    expect(await screen.findByText("уровень установлен вручную")).toBeInTheDocument();
    expect(
      screen.getByText(/Уровень за этот месяц скорректирован администратором\./),
    ).toBeInTheDocument();
  });

  it("celebrates the top level", async () => {
    const top = {
      ...CABINET,
      level: { ...CABINET.level, next_level_label: null, contracts_to_next: null },
    };
    mockApi({ "/site/cabinet": { body: top } });
    renderWithProviders(<CabinetPage />);

    expect(await screen.findByText(/выше уже некуда/)).toBeInTheDocument();
  });

  it("says there are no clients yet", async () => {
    mockApi({ "/site/cabinet": { body: { ...CABINET, clients: [] } } });
    renderWithProviders(<CabinetPage />);

    expect(await screen.findByText("Клиентов пока нет")).toBeInTheDocument();
    expect(screen.queryByText("Клиент Клиентов")).not.toBeInTheDocument();
  });

  it("shows an error when the data cannot be loaded", async () => {
    mockApi({ "/site/cabinet": { status: 500, body: {} } });
    renderWithProviders(<CabinetPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
