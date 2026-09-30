import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, sentBody } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { AdminFaqPage } from "./AdminFaqPage";
import type { FaqEntry } from "./types";

const ITEMS: FaqEntry[] = [
  { id: 1, question: "Когда выплата?", answer: "После оплаты." },
  { id: 2, question: "Как зафиксировать клиента?", answer: "Через ссылку." },
  { id: 3, question: "Что такое уровень?", answer: "Число договоров." },
];

const PATH = "/admin/faq";
const list = (items: FaqEntry[] = ITEMS) => ({ body: { items } });
const ok = { body: { ok: true } };

/** The card of an existing question, found by what its question field currently holds. */
const cardOf = (question: string) => screen.getByDisplayValue(question).closest("section")!;
const createCard = () =>
  screen.getByRole("heading", { name: "Добавить вопрос" }).closest("section")!;

afterEach(() => vi.unstubAllGlobals());

describe("AdminFaqPage", () => {
  it("lists every question in its own editable card", async () => {
    mockApi({ [PATH]: list() });
    renderWithProviders(<AdminFaqPage />);

    expect(await screen.findByDisplayValue("Когда выплата?")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Через ссылку.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "«Как это работает»" })).toHaveAttribute(
      "target",
      "_blank",
    );
  });

  it("says so when there are no questions", async () => {
    mockApi({ [PATH]: list([]) });
    renderWithProviders(<AdminFaqPage />);

    expect(await screen.findByText("Вопросов пока нет.")).toBeInTheDocument();
  });

  it("cannot move the first question up or the last one down", async () => {
    mockApi({ [PATH]: list() });
    renderWithProviders(<AdminFaqPage />);
    await screen.findByDisplayValue("Когда выплата?");

    expect(within(cardOf("Когда выплата?")).getByRole("button", { name: "↑ Выше" })).toBeDisabled();
    expect(
      within(cardOf("Что такое уровень?")).getByRole("button", { name: "↓ Ниже" }),
    ).toBeDisabled();
    expect(
      within(cardOf("Как зафиксировать клиента?")).getByRole("button", { name: "↑ Выше" }),
    ).toBeEnabled();
  });

  it("adds a question and empties the form", async () => {
    const api = mockApi({ [PATH]: (body) => (body ? ok : list()) });
    renderWithProviders(<AdminFaqPage />);
    const user = userEvent.setup();

    await screen.findByDisplayValue("Когда выплата?");
    const form = within(createCard());
    await user.type(form.getByLabelText("Вопрос"), "Новый вопрос");
    await user.type(form.getByLabelText("Ответ"), "Новый ответ");
    await user.click(form.getByRole("button", { name: "Добавить" }));

    await waitFor(() =>
      expect(sentBody(api, PATH)).toEqual({ question: "Новый вопрос", answer: "Новый ответ" }),
    );
    await waitFor(() => expect(form.getByLabelText("Вопрос")).toHaveValue(""));
    expect(form.getByLabelText("Ответ")).toHaveValue("");
  });

  it("saves an edited question", async () => {
    const api = mockApi({ [PATH]: list(), "/admin/faq/2": ok });
    renderWithProviders(<AdminFaqPage />);
    const user = userEvent.setup();

    await screen.findByDisplayValue("Через ссылку.");
    const answer = screen.getByDisplayValue("Через ссылку.");
    await user.clear(answer);
    await user.type(answer, "По реферальной ссылке.");
    await user.click(
      within(cardOf("Как зафиксировать клиента?")).getByRole("button", { name: "Сохранить" }),
    );

    await waitFor(() =>
      expect(sentBody(api, "/admin/faq/2")).toEqual({
        question: "Как зафиксировать клиента?",
        answer: "По реферальной ссылке.",
      }),
    );
    const put = api.mock.calls.find(([u, init]) => u.endsWith("/faq/2") && init?.body);
    expect(put?.[1]?.method).toBe("PUT");
  });

  it("moves a question", async () => {
    const api = mockApi({ [PATH]: list(), "/2/move": ok });
    renderWithProviders(<AdminFaqPage />);
    const user = userEvent.setup();

    await screen.findByDisplayValue("Когда выплата?");
    await user.click(
      within(cardOf("Как зафиксировать клиента?")).getByRole("button", { name: "↑ Выше" }),
    );

    await waitFor(() => expect(sentBody(api, "/2/move")).toEqual({ direction: "up" }));
  });

  it("deletes a question only after the admin confirms", async () => {
    const api = mockApi({ [PATH]: list(), "/admin/faq/3": ok });
    const confirm = vi.spyOn(window, "confirm");
    renderWithProviders(<AdminFaqPage />);
    const user = userEvent.setup();
    await screen.findByDisplayValue("Что такое уровень?");
    const remove = () =>
      within(cardOf("Что такое уровень?")).getByRole("button", { name: "Удалить" });
    const deleted = () =>
      api.mock.calls.some(([u, init]) => u.endsWith("/faq/3") && init?.method === "DELETE");

    confirm.mockReturnValueOnce(false);
    await user.click(remove());
    expect(confirm).toHaveBeenCalledWith("Удалить вопрос?");
    expect(deleted()).toBe(false);

    confirm.mockReturnValueOnce(true);
    await user.click(remove());
    await waitFor(() => expect(deleted()).toBe(true));
    confirm.mockRestore();
  });

  it("shows why a change was refused", async () => {
    mockApi({
      [PATH]: (body) =>
        body
          ? {
              status: 400,
              body: { error: { code: "validation_error", message: "Заполните вопрос и ответ" } },
            }
          : list(),
    });
    renderWithProviders(<AdminFaqPage />);
    const user = userEvent.setup();

    await screen.findByDisplayValue("Когда выплата?");
    const form = within(createCard());
    await user.type(form.getByLabelText("Вопрос"), "x");
    await user.type(form.getByLabelText("Ответ"), "y");
    await user.click(form.getByRole("button", { name: "Добавить" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Заполните вопрос и ответ");
  });

  it("shows an error when the list cannot be loaded", async () => {
    mockApi({ [PATH]: { status: 500, body: {} } });
    renderWithProviders(<AdminFaqPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
