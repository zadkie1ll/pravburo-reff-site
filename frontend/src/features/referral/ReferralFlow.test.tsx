import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, sentBody } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { ReferralFormPage } from "./ReferralFormPage";
import { ReferralSuccessPage } from "./ReferralSuccessPage";

const CODE = "00000000-0000-4000-8000-000000000099";
const API = `/site/referral/${CODE}`;

function renderFlow() {
  return renderWithProviders(
    <Routes>
      <Route path="/r/:referralCode" element={<ReferralFormPage />} />
      <Route path="/r/:referralCode/success" element={<ReferralSuccessPage />} />
    </Routes>,
    `/r/${CODE}`,
  );
}

/** A Turnstile stand-in that exposes the callbacks the widget registered. */
function stubTurnstile() {
  const captured: { callback?: (token: string) => void; expired?: () => void } = {};
  const api = {
    render: vi.fn((_el: HTMLElement, options: Record<string, unknown>) => {
      captured.callback = options.callback as (token: string) => void;
      captured.expired = options["expired-callback"] as () => void;
      return "widget-1";
    }),
    reset: vi.fn(),
    remove: vi.fn(),
  };
  vi.stubGlobal("turnstile", api);
  return { api, captured };
}

async function fillRequired(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText("ФИО"), "Иван Иванов");
  await user.type(screen.getByLabelText("Телефон"), "+79991234567");
}

afterEach(() => vi.unstubAllGlobals());

describe("referral form", () => {
  it("loads the form once (a load counts as a visit) and shows the intro", async () => {
    const api = mockApi({ [API]: { body: { turnstile_site_key: "" } } });
    renderFlow();

    expect(
      await screen.findByRole("heading", { name: "Расскажите о вашей ситуации" }),
    ).toBeInTheDocument();
    const loads = api.mock.calls.filter(([url]) => url.endsWith(CODE));
    expect(loads).toHaveLength(1);
  });

  it("hides the situation fields until asked, then reveals them", async () => {
    mockApi({ [API]: { body: { turnstile_site_key: "" } } });
    renderFlow();
    const user = userEvent.setup();

    await screen.findByLabelText("ФИО");
    expect(screen.queryByLabelText("Город")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Описать свою ситуацию" }));

    expect(screen.getByLabelText("Город")).toBeInTheDocument();
    expect(screen.getByLabelText("Сумма долга")).toBeInTheDocument();
    expect(screen.getByLabelText("Описание ситуации")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Описать свою ситуацию" })).not.toBeInTheDocument();
  });

  it("sends the application and shows the thank-you page", async () => {
    const api = mockApi({
      [API]: (body) => ({ body: body ? { ok: true } : { turnstile_site_key: "" } }),
    });
    renderFlow();
    const user = userEvent.setup();

    await fillRequired(user);
    await user.click(screen.getByRole("button", { name: "Описать свою ситуацию" }));
    await user.type(screen.getByLabelText("Город"), "Казань");
    await user.click(screen.getByRole("button", { name: "Отправить заявку" }));

    expect(await screen.findByRole("heading", { name: "Заявка принята" })).toBeInTheDocument();
    expect(sentBody(api, CODE)).toEqual({
      full_name: "Иван Иванов",
      phone: "+79991234567",
      preferred_call_time_msk: "",
      city: "Казань",
      debt_amount: "",
      situation: "",
      website: "",
      turnstile_token: "",
    });
  });

  it("carries whatever a bot typed into the honeypot", async () => {
    const api = mockApi({
      [API]: (body) => ({ body: body ? { ok: true } : { turnstile_site_key: "" } }),
    });
    const { container } = renderFlow();
    const user = userEvent.setup();

    await fillRequired(user);
    await user.type(container.querySelector<HTMLInputElement>("input[name=website]")!, "spam");
    await user.click(screen.getByRole("button", { name: "Отправить заявку" }));

    await screen.findByRole("heading", { name: "Заявка принята" });
    expect(sentBody(api, CODE)).toMatchObject({ website: "spam" });
  });

  it("shows the server's message and stays on the form when refused", async () => {
    mockApi({
      [API]: (body) =>
        body
          ? {
              status: 400,
              body: {
                error: { code: "application_invalid", message: "Укажите корректный телефон" },
              },
            }
          : { body: { turnstile_site_key: "" } },
    });
    renderFlow();
    const user = userEvent.setup();

    await fillRequired(user);
    await user.click(screen.getByRole("button", { name: "Отправить заявку" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Укажите корректный телефон");
    expect(screen.queryByRole("heading", { name: "Заявка принята" })).not.toBeInTheDocument();
  });

  it("shows the not-found page for an unknown link", async () => {
    mockApi({
      [API]: { status: 404, body: { error: { code: "not_found", message: "Ссылка не найдена" } } },
    });
    renderFlow();

    expect(await screen.findByRole("heading", { name: "Страница не найдена" })).toBeInTheDocument();
  });

  it("shows a generic error when the form cannot be loaded", async () => {
    mockApi({ [API]: { status: 500, body: {} } });
    renderFlow();

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

describe("Turnstile", () => {
  it("blocks sending until the challenge is solved, then sends its token", async () => {
    const { captured } = stubTurnstile();
    const api = mockApi({
      [API]: (body) => ({ body: body ? { ok: true } : { turnstile_site_key: "site-key" } }),
    });
    renderFlow();
    const user = userEvent.setup();

    await fillRequired(user);
    const send = screen.getByRole("button", { name: "Отправить заявку" });
    await waitFor(() => expect(captured.callback).toBeDefined());
    expect(send).toBeDisabled();

    act(() => captured.callback?.("solved-token"));
    await waitFor(() => expect(send).toBeEnabled());
    await user.click(send);

    await screen.findByRole("heading", { name: "Заявка принята" });
    expect(sentBody(api, CODE)).toMatchObject({ turnstile_token: "solved-token" });
  });

  it("asks for a fresh challenge after a refused attempt (a token works once)", async () => {
    const { api: turnstile, captured } = stubTurnstile();
    mockApi({
      [API]: (body) =>
        body
          ? {
              status: 429,
              body: {
                error: {
                  code: "submission_rejected",
                  message: "Не удалось отправить форму. Попробуйте позже.",
                },
              },
            }
          : { body: { turnstile_site_key: "site-key" } },
    });
    renderFlow();
    const user = userEvent.setup();

    await fillRequired(user);
    await waitFor(() => expect(captured.callback).toBeDefined());
    act(() => captured.callback?.("used-token"));
    const send = screen.getByRole("button", { name: "Отправить заявку" });
    await waitFor(() => expect(send).toBeEnabled());
    await user.click(send);

    expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось отправить форму");
    expect(turnstile.reset).toHaveBeenCalledWith("widget-1");
    expect(send).toBeDisabled();
  });

  it("blocks sending again when the token expires", async () => {
    const { captured } = stubTurnstile();
    mockApi({ [API]: { body: { turnstile_site_key: "site-key" } } });
    renderFlow();

    await waitFor(() => expect(captured.callback).toBeDefined());
    act(() => captured.callback?.("token"));
    const send = screen.getByRole("button", { name: "Отправить заявку" });
    await waitFor(() => expect(send).toBeEnabled());
    act(() => captured.expired?.());

    await waitFor(() => expect(send).toBeDisabled());
  });
});

describe("thank-you page", () => {
  it("thanks the client", async () => {
    mockApi();
    renderWithProviders(<ReferralSuccessPage />);

    expect(screen.getByRole("heading", { name: "Заявка принята" })).toBeInTheDocument();
    expect(screen.getByText("Специалист Правбюро свяжется с вами.")).toBeInTheDocument();
  });
});
