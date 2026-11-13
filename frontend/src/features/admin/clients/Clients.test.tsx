import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockApi, sentBody } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";
import { useInfoFromNavigation } from "@/features/auth/useInfoFromNavigation";
import { AdminClientsPage } from "./AdminClientsPage";
import { ClientEditorPage } from "./ClientEditorPage";
import { parseDealReference, type ExistingClient, type BitrixCandidate } from "./api";

const BASE = "/site/admin/clients";
const PARTNER = {
  id: 7,
  display_name: "Анна Партнёрова",
  email: "anna@example.test",
  is_admin: false,
};
const CLIENT: ExistingClient = {
  id: 1,
  agent_id: 7,
  agent_name: PARTNER.display_name,
  agent_email: PARTNER.email,
  full_name: "Иван Клиентов",
  phone: "+79990001122",
  bitrix_deal_id: "432",
  bitrix_deal_url: "https://portal.example/crm/deal/details/432/",
  stage_label: "Договор подписан",
  current_amount: "12500.50",
  current_status: "pending",
  admin_note: "Текущий остаток",
  created_at_label: "13.11.2026",
};
const DEAL = {
  deal_id: "432",
  deal_url: CLIENT.bitrix_deal_url,
  full_name: CLIENT.full_name,
  phone: CLIENT.phone,
  stage_code: "WON",
  stage_label: CLIENT.stage_label,
  category_id: 1,
  first_payment: "75000.00",
  paid_in_full: true,
};

function Destination() {
  const location = useLocation();
  const info = useInfoFromNavigation();
  return (
    <p>
      Список клиентов {location.search} {info}
    </p>
  );
}

function renderEditor(path = "/admin/clients/new?agent_id=7") {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/clients/new" element={<ClientEditorPage />} />
      <Route path="/admin/clients" element={<Destination />} />
    </Routes>,
    path,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("existing client import", () => {
  it("loads the preselected partner and read-only snapshot, allows corrections, and sends a null amount", async () => {
    const api = mockApi({
      [BASE]: { body: CLIENT },
      "/partners/7": { body: PARTNER },
      "/deals/432": { body: DEAL },
    });
    renderEditor();
    const user = userEvent.setup();
    expect(await screen.findByText(/Выбран: Анна Партнёрова/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("ID сделки в Битрикс24 или ссылка"), "432");
    await user.click(screen.getByRole("button", { name: "Найти сделку" }));
    expect(await screen.findByLabelText("Данные сделки из Битрикс24")).toHaveTextContent(
      "Договор подписан",
    );
    expect(screen.getByLabelText("ФИО клиента")).toHaveValue(CLIENT.full_name);
    expect(screen.getByLabelText("Телефон клиента")).toHaveValue(CLIENT.phone);
    expect(screen.getByLabelText(/^К выплате партнёру/)).toHaveValue(null);
    await user.clear(screen.getByLabelText("ФИО клиента"));
    await user.type(screen.getByLabelText("ФИО клиента"), "Иван Исправленный");
    await user.type(screen.getByLabelText("Заметка"), "Проверено");
    await user.click(screen.getByRole("button", { name: "Добавить клиента" }));
    expect(await screen.findByText(/Список клиентов/)).toHaveTextContent(
      "?agent_id=7 Действующий клиент добавлен",
    );
    expect(sentBody(api, BASE)).toEqual({
      agent_id: 7,
      deal_id: "432",
      full_name: "Иван Исправленный",
      phone: CLIENT.phone,
      current_amount: null,
      admin_note: "Проверено",
    });
    expect(api.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
    expect(api.mock.calls.find(([url]) => url.endsWith("/deals/432"))?.[1]?.method).toBe("GET");
  });

  it("requires explicit partner selection, paginates partner search and never guesses the amount", async () => {
    const api = mockApi({
      [BASE]: { body: CLIENT },
      "/deals/432": { body: DEAL },
      "/site/admin/partners": {
        body: { rows: [PARTNER], page: 1, total_pages: 2, total_count: 2 },
      },
    });
    renderEditor("/admin/clients/new");
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Найти партнёра по имени, почте или телефону"), "Анна");
    await user.type(screen.getByLabelText("ID сделки в Битрикс24 или ссылка"), "432");
    await user.type(screen.getByLabelText("ФИО клиента"), "Иван");
    await user.click(screen.getByRole("button", { name: "Добавить клиента" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Выберите партнёра");
    expect(sentBody(api, BASE)).toBeUndefined();
    await user.click(screen.getByRole("button", { name: "Найти партнёра" }));
    await user.click(await screen.findByRole("button", { name: "Следующие партнёры" }));
    await waitFor(() => expect(api.mock.calls.some(([url]) => url.includes("page=2"))).toBe(true));
    await user.click(
      await screen.findByRole("button", { name: "Выбрать партнёра: Анна Партнёрова" }),
    );
    await user.type(screen.getByLabelText(/^К выплате партнёру/), "12500.50");
    await user.click(screen.getByRole("button", { name: "Найти сделку" }));
    await screen.findByLabelText("Данные сделки из Битрикс24");
    expect(screen.getByLabelText(/^К выплате партнёру/)).toHaveValue(12500.5);
    await user.click(screen.getByRole("button", { name: "Добавить клиента" }));
    await screen.findByText(/Список клиентов/);
    expect(sentBody(api, BASE)).toMatchObject({ agent_id: 7, current_amount: "12500.5" });
  });

  it("supports manual fallback and preserves inputs on server rejection", async () => {
    const api = mockApi({
      "/partners/7": { body: PARTNER },
      "/deals/432": { status: 503, body: {} },
      [BASE]: {
        status: 400,
        body: { error: { code: "duplicate", message: "Сделка уже привязана" } },
      },
    });
    renderEditor();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("ID сделки в Битрикс24 или ссылка"), "432");
    await user.click(screen.getByRole("button", { name: "Найти сделку" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Можно заполнить ФИО и телефон вручную",
    );
    await user.type(screen.getByLabelText("ФИО клиента"), "Клиент вручную");
    await user.type(screen.getByLabelText("Заметка"), "Сверить");
    await user.click(screen.getByRole("button", { name: "Добавить клиента" }));
    expect(await screen.findByText("Сделка уже привязана")).toBeInTheDocument();
    expect(screen.getByLabelText("ФИО клиента")).toHaveValue("Клиент вручную");
    expect(screen.getByLabelText("Заметка")).toHaveValue("Сверить");
    expect(sentBody(api, BASE)).toMatchObject({ phone: "", current_amount: null });
  });

  it("rejects non-positive current amounts and clears the snapshot when the deal ID changes", async () => {
    const api = mockApi({
      [BASE]: { body: CLIENT },
      "/partners/7": { body: PARTNER },
      "/deals/432": { body: DEAL },
    });
    renderEditor();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("ID сделки в Битрикс24 или ссылка"), "432");
    await user.click(screen.getByRole("button", { name: "Найти сделку" }));
    await screen.findByLabelText("Данные сделки из Битрикс24");
    await user.type(screen.getByLabelText(/^К выплате партнёру/), "0");
    await user.click(screen.getByRole("button", { name: "Добавить клиента" }));
    expect(sentBody(api, BASE)).toBeUndefined();
    expect(screen.getByLabelText(/^К выплате партнёру/)).toBeInvalid();
    await user.type(screen.getByLabelText("ID сделки в Битрикс24 или ссылка"), "9");
    expect(screen.queryByLabelText("Данные сделки из Битрикс24")).not.toBeInTheDocument();
  });
});

describe("existing client list", () => {
  it("shows cards and pagination above and below, preserving search and partner filters", async () => {
    mockApi({
      [BASE]: { body: { rows: [CLIENT], page: 2, total_pages: 3, total_count: 45 } },
      "/partners/7": { body: PARTNER },
    });
    renderWithProviders(<AdminClientsPage />, "/admin/clients?q=Иван&agent_id=7&page=2");
    const card = await screen.findByRole("article", { name: "Клиент: Иван Клиентов" });
    expect(within(card).getByRole("link", { name: "Открыть в Битриксе" })).toHaveAttribute(
      "href",
      CLIENT.bitrix_deal_url,
    );
    expect(card).toHaveTextContent("Договор подписан");
    expect(card).toHaveTextContent("Ожидает");
    expect(card).toHaveTextContent(/12\s*500,50\s*₽/);
    expect(card).toHaveTextContent("Текущий остаток");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    const pagers = screen.getAllByRole("navigation", { name: "Страницы" });
    expect(pagers).toHaveLength(2);
    for (const pager of pagers) {
      expect(within(pager).getByRole("link", { name: "Вперёд →" })).toHaveAttribute(
        "href",
        "/admin/clients?q=%D0%98%D0%B2%D0%B0%D0%BD&agent_id=7&page=3",
      );
    }
    expect(
      pagers[0]!.compareDocumentPosition(card) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      card.compareDocumentPosition(pagers[1]!) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "Добавить клиента" })).toHaveAttribute(
      "href",
      "/admin/clients/new?agent_id=7",
    );
    expect(screen.getAllByRole("navigation", { name: "Возврат к разделу" })).toHaveLength(1);
  });

  it("applies and clears filters, resetting the page", async () => {
    const api = mockApi({
      [BASE]: { body: { rows: [], page: 1, total_pages: 1, total_count: 0 } },
      "/partners/7": { body: PARTNER },
    });
    renderWithProviders(<AdminClientsPage />, "/admin/clients?agent_id=7&page=3");
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Найти клиента по имени, телефону или сделке"), "432");
    await user.click(screen.getByRole("button", { name: "Искать" }));
    await waitFor(() =>
      expect(api.mock.calls.map(([url]) => url)).toContain(
        "/api/v1/site/admin/clients?q=432&agent_id=7",
      ),
    );
    await user.click(screen.getByRole("button", { name: "Сбросить фильтры" }));
    await waitFor(() =>
      expect(api.mock.calls.map(([url]) => url)).toContain("/api/v1/site/admin/clients"),
    );
    expect(screen.getByLabelText("Найти клиента по имени, телефону или сделке")).toHaveValue("");
    expect(await screen.findByText("Действующие клиенты не найдены")).toBeInTheDocument();
  });

  it("shows missing amount and error states", async () => {
    mockApi({
      [BASE]: {
        body: {
          rows: [{ ...CLIENT, current_amount: null, current_status: null }],
          page: 1,
          total_pages: 1,
          total_count: 1,
        },
      },
    });
    const first = renderWithProviders(<AdminClientsPage />, "/admin/clients");
    expect(await screen.findByText("Не указано")).toBeInTheDocument();
    first.unmount();
    mockApi({ [BASE]: { status: 500, body: {} } });
    renderWithProviders(<AdminClientsPage />, "/admin/clients");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

const CANDIDATES: BitrixCandidate[] = [
  {
    kind: "deal",
    id: 432,
    title: "Первый договор",
    full_name: CLIENT.full_name,
    phone: CLIENT.phone,
    category_id: 1,
    category_label: "Основная",
    stage_code: "WON",
    stage_label: "Подписан",
    url: DEAL.deal_url!,
  },
  {
    kind: "deal",
    id: 987,
    title: "Второй договор",
    full_name: CLIENT.full_name,
    phone: CLIENT.phone,
    category_id: 2,
    category_label: "Повторные обращения",
    stage_code: "C2:NEW",
    stage_label: "Новая",
    url: "https://portal.example/crm/deal/details/987/",
  },
  {
    kind: "lead",
    id: 123,
    title: "Обращение",
    full_name: CLIENT.full_name,
    phone: null,
    category_id: null,
    category_label: "",
    stage_code: "NEW",
    stage_label: "Новый",
    url: "https://portal.example/crm/lead/details/123/",
  },
];
const SEARCH_LABEL = "ФИО для поиска в Битриксе";
const REFERENCE_LABEL = "ID сделки в Битрикс24 или ссылка";

async function runSearch() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(SEARCH_LABEL), "Иван Клиентов");
  await user.click(screen.getByRole("button", { name: "Найти клиента в Битриксе" }));
  return user;
}

function deferredResponse() {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>((done) => {
    resolve = done;
  });
  return { promise, resolve: (body: unknown) => resolve(new Response(JSON.stringify(body))) };
}

describe("Bitrix search and preview", () => {
  it("shows deals in different funnels and leads with links before explicit selection", async () => {
    const api = mockApi({
      "/partners/7": { body: PARTNER },
      [`${BASE}/search`]: { body: { rows: CANDIDATES, page: 1, has_more: true } },
      "/deals/987": { body: { ...DEAL, deal_id: "987", deal_url: CANDIDATES[1]!.url } },
    });
    renderEditor();
    const user = await runSearch();
    const results = await screen.findByRole("region", { name: "Результаты поиска в Битриксе" });
    expect(results).toHaveTextContent("Основная");
    expect(results).toHaveTextContent("Повторные обращения");
    const cards = within(results).getAllByRole("article");
    for (const [i, card] of cards.entries()) {
      const link = within(card).getByRole("link", { name: "Открыть в Битриксе" });
      expect(link).toHaveAttribute("href", CANDIDATES[i]!.url);
      expect(link).toHaveAttribute("target", "_blank");
      expect(link.getAttribute("rel")).toContain("noopener");
    }
    expect(within(cards[2]!).queryByRole("button")).not.toBeInTheDocument();
    expect(cards[2]).toHaveTextContent("Лид #123");
    expect(cards[2]).toHaveTextContent("Для привязки нужна сделка");
    expect(screen.getByLabelText(REFERENCE_LABEL)).toHaveValue("");
    expect(api.mock.calls.some(([url]) => url.includes("/deals/"))).toBe(false);
    await user.click(within(cards[1]!).getByRole("button", { name: "Выбрать сделку" }));
    const preview = await screen.findByLabelText("Данные сделки из Битрикс24");
    expect(preview).toHaveTextContent("Сделка #987");
    expect(within(preview).getByRole("link")).toHaveAttribute("href", CANDIDATES[1]!.url);
    expect(screen.getByLabelText("ФИО клиента")).toHaveValue(CLIENT.full_name);
    expect(sentBody(api, BASE)).toBeUndefined();
    await user.click(screen.getByRole("button", { name: "Следующие результаты" }));
    await waitFor(() => expect(api.mock.calls.some(([url]) => url.includes("page=2"))).toBe(true));
    await user.clear(screen.getByLabelText(SEARCH_LABEL));
    expect(
      screen.queryByRole("region", { name: "Результаты поиска в Битриксе" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Данные сделки из Битрикс24")).toHaveTextContent("#987");
  });

  it("does not automatically choose a single result", async () => {
    const api = mockApi({
      "/partners/7": { body: PARTNER },
      [`${BASE}/search`]: { body: { rows: [CANDIDATES[0]], page: 1, has_more: false } },
    });
    renderEditor();
    await runSearch();
    await screen.findByRole("button", { name: "Выбрать сделку" });
    expect(screen.getByLabelText(REFERENCE_LABEL)).toHaveValue("");
    expect(screen.getByLabelText("ФИО клиента")).toHaveValue("");
    expect(api.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
  });

  it("previews a full URL through the local query API and posts only its numeric snapshot ID", async () => {
    const api = mockApi({
      "/partners/7": { body: PARTNER },
      "/deals/preview": { body: DEAL },
      [BASE]: { body: CLIENT },
    });
    renderEditor();
    const user = userEvent.setup();
    const reference = `${DEAL.deal_url}?from=search&tab=main`;
    await user.type(screen.getByLabelText(REFERENCE_LABEL), reference);
    await user.click(screen.getByRole("button", { name: "Найти сделку" }));
    await screen.findByLabelText("Данные сделки из Битрикс24");
    expect(api.mock.calls.map(([url]) => url)).toContain(
      `/api/v1${BASE}/deals/preview?${new URLSearchParams({ deal: reference })}`,
    );
    expect(api.mock.calls.every(([url]) => url.startsWith("/api/v1/"))).toBe(true);
    await user.clear(screen.getByLabelText("Телефон клиента"));
    await user.type(screen.getByLabelText("Телефон клиента"), "+79998887766");
    await user.type(screen.getByLabelText(/^К выплате партнёру/), "100");
    await user.click(screen.getByRole("button", { name: "Добавить клиента" }));
    await screen.findByText(/Список клиентов/);
    expect(sentBody(api, BASE)).toMatchObject({
      deal_id: "432",
      phone: "+79998887766",
      current_amount: "100",
    });
  });

  it("validates query length and clears errors on query changes", async () => {
    const api = mockApi({
      "/partners/7": { body: PARTNER },
      [`${BASE}/search`]: {
        status: 503,
        body: { error: { code: "unavailable", message: "Поиск недоступен" } },
      },
    });
    renderEditor();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(SEARCH_LABEL), "Ив");
    await user.click(screen.getByRole("button", { name: "Найти клиента в Битриксе" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("от 3 до 200");
    expect(api.mock.calls.some(([url]) => url.includes("/search?"))).toBe(false);
    await user.type(screen.getByLabelText(SEARCH_LABEL), "ан");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Найти клиента в Битриксе" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Поиск недоступен");
    await user.clear(screen.getByLabelText(SEARCH_LABEL));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByLabelText(SEARCH_LABEL)).toHaveAttribute("maxlength", "200");
  });

  it("ignores a pending search after the query changes", async () => {
    const api = mockApi({ "/partners/7": { body: PARTNER } });
    const original = api.getMockImplementation()!;
    const pending = deferredResponse();
    api.mockImplementation((url, init) =>
      url.includes("/search?") ? pending.promise : original(url, init),
    );
    renderEditor();
    const user = await runSearch();
    await user.clear(screen.getByLabelText(SEARCH_LABEL));
    await act(async () => pending.resolve({ rows: CANDIDATES, page: 1, has_more: false }));
    expect(
      screen.queryByRole("region", { name: "Результаты поиска в Битриксе" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("ФИО клиента")).toHaveValue("");
  });

  it("keeps the newest chosen deal when an older preview returns late", async () => {
    const api = mockApi({
      "/partners/7": { body: PARTNER },
      [`${BASE}/search`]: { body: { rows: CANDIDATES, page: 1, has_more: false } },
      "/deals/987": { body: { ...DEAL, deal_id: "987", full_name: "Выбранный клиент" } },
    });
    const original = api.getMockImplementation()!;
    const pending = deferredResponse();
    api.mockImplementation((url, init) =>
      url.endsWith("/deals/432") ? pending.promise : original(url, init),
    );
    renderEditor();
    const user = await runSearch();
    const buttons = await screen.findAllByRole("button", { name: "Выбрать сделку" });
    await user.click(buttons[0]!);
    await user.click(buttons[1]!);
    await screen.findByLabelText("Данные сделки из Битрикс24");
    await user.clear(screen.getByLabelText(SEARCH_LABEL));
    await act(async () => pending.resolve(DEAL));
    expect(screen.getByLabelText(REFERENCE_LABEL)).toHaveValue("987");
    expect(screen.getByLabelText("ФИО клиента")).toHaveValue("Выбранный клиент");
    expect(screen.getByLabelText("Данные сделки из Битрикс24")).toHaveTextContent("#987");
  });

  it.each([
    "https://portal.example/crm/lead/details/432/",
    "https://portal.example/other/432",
    "javascript:alert(1)",
    "0",
    "-1",
  ])("rejects invalid deal reference %s without requesting it", async (reference) => {
    const api = mockApi({ "/partners/7": { body: PARTNER } });
    renderEditor();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(REFERENCE_LABEL), reference);
    await user.click(screen.getByRole("button", { name: "Найти сделку" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Укажите ID сделки");
    expect(api.mock.calls.some(([url]) => url.includes("/deals/"))).toBe(false);
  });

  it("parses numeric IDs and fixed deal paths only", () => {
    expect(parseDealReference(" 432 ")).toBe("432");
    expect(parseDealReference(DEAL.deal_url!)).toBe("432");
    expect(parseDealReference("https://portal.example/crm/deal/details/432/extra")).toBeNull();
    expect(parseDealReference("https://portal.example/crm/deal/details/0432/")).toBeNull();
  });
});
