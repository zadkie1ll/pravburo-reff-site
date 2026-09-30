import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, sentBody } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { TwoFactorSetupPage } from "./TwoFactorSetupPage";
import { TwoFactorVerifyPage } from "./TwoFactorVerifyPage";

const STATE = "/2fa/state";
const assign = vi.fn();
const replace = vi.fn();

const SETUP = { body: { step: "setup", qr_url: "/admin/2fa/qr.png" } };
const VERIFY = { body: { step: "verify", qr_url: null } };
const wrong = (code: string, message: string, status = 400) => ({
  status,
  body: { error: { code, message } },
});

function renderPages(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/2fa/setup" element={<TwoFactorSetupPage />} />
      <Route path="/admin/2fa/verify" element={<TwoFactorVerifyPage />} />
    </Routes>,
    route,
  );
}

const enterCode = async (
  user: ReturnType<typeof userEvent.setup>,
  code: string,
  button: string,
) => {
  await user.type(screen.getByLabelText("Код из приложения"), code);
  const submit = screen.getByRole("button", { name: button });
  await waitFor(() => expect(submit).toBeEnabled());
  await user.click(submit);
};

afterEach(() => {
  vi.unstubAllGlobals();
  assign.mockReset();
  replace.mockReset();
});

describe("2FA setup page", () => {
  it("shows the QR code with instructions", async () => {
    mockApi({ [STATE]: SETUP });
    renderPages("/admin/2fa/setup");

    expect(
      await screen.findByRole("heading", { name: "Настройте двухфакторную аутентификацию" }),
    ).toBeInTheDocument();
    expect(screen.getByAltText("QR-код для настройки 2FA")).toHaveAttribute(
      "src",
      "/admin/2fa/qr.png",
    );
    expect(screen.getByText(/Google Authenticator/)).toBeInTheDocument();
  });

  it("sends the code and follows `next` into the admin panel", async () => {
    const api = mockApi({ [STATE]: SETUP, "/2fa/setup": { body: { next: "/admin" } } });
    vi.stubGlobal("location", { assign, replace });
    renderPages("/admin/2fa/setup");
    const user = userEvent.setup();

    await screen.findByAltText("QR-код для настройки 2FA");
    await enterCode(user, "123456", "Подтвердить и включить");

    await waitFor(() => expect(assign).toHaveBeenCalledWith("/admin"));
    expect(sentBody(api, "/2fa/setup")).toEqual({ code: "123456" });
  });

  it("says the code was wrong and empties the field", async () => {
    mockApi({ [STATE]: SETUP, "/2fa/setup": wrong("invalid_code", "Неверный код") });
    vi.stubGlobal("location", { assign, replace });
    renderPages("/admin/2fa/setup");
    const user = userEvent.setup();

    await screen.findByAltText("QR-код для настройки 2FA");
    await enterCode(user, "000000", "Подтвердить и включить");

    expect(await screen.findByRole("alert")).toHaveTextContent("Неверный код");
    expect(screen.getByLabelText("Код из приложения")).toHaveValue("");
    expect(assign).not.toHaveBeenCalled();
  });

  it("moves an admin who already has 2FA to the code page", async () => {
    mockApi({ [STATE]: VERIFY });
    renderPages("/admin/2fa/setup");

    expect(
      await screen.findByRole("heading", { name: "Введите код из приложения" }),
    ).toBeInTheDocument();
  });
});

describe("2FA verify page", () => {
  it("asks for the current code, with the field focused", async () => {
    mockApi({ [STATE]: VERIFY });
    renderPages("/admin/2fa/verify");

    expect(
      await screen.findByRole("heading", { name: "Введите код из приложения" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Код из приложения")).toHaveFocus();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("only takes six digits", async () => {
    mockApi({ [STATE]: VERIFY });
    renderPages("/admin/2fa/verify");

    const input = await screen.findByLabelText("Код из приложения");
    expect(input).toHaveAttribute("maxlength", "6");
    expect(input).toHaveAttribute("pattern", "[0-9]{6}");
    expect(input).toHaveAttribute("inputmode", "numeric");
    expect(input).toHaveAttribute("autocomplete", "one-time-code");
  });

  it("logs in with the right code", async () => {
    const api = mockApi({ [STATE]: VERIFY, "/2fa/verify": { body: { next: "/admin" } } });
    vi.stubGlobal("location", { assign, replace });
    renderPages("/admin/2fa/verify");
    const user = userEvent.setup();

    await screen.findByLabelText("Код из приложения");
    await enterCode(user, "654321", "Войти");

    await waitFor(() => expect(assign).toHaveBeenCalledWith("/admin"));
    expect(sentBody(api, "/2fa/verify")).toEqual({ code: "654321" });
  });

  it("shows the lockout message after too many tries", async () => {
    mockApi({
      [STATE]: VERIFY,
      "/2fa/verify": wrong("rate_limited", "Слишком много попыток. Попробуйте позже.", 429),
    });
    vi.stubGlobal("location", { assign, replace });
    renderPages("/admin/2fa/verify");
    const user = userEvent.setup();

    await screen.findByLabelText("Код из приложения");
    await enterCode(user, "111111", "Войти");

    expect(await screen.findByRole("alert")).toHaveTextContent("Слишком много попыток");
  });

  it("moves an admin who has not set 2FA up to the setup page", async () => {
    mockApi({ [STATE]: SETUP });
    renderPages("/admin/2fa/verify");

    expect(
      await screen.findByRole("heading", { name: "Настройте двухфакторную аутентификацию" }),
    ).toBeInTheDocument();
  });

  it("sends anyone without a password step to the login page", async () => {
    mockApi({ [STATE]: wrong("unauthorized", "Требуется вход", 401) });
    vi.stubGlobal("location", { assign, replace });
    renderPages("/admin/2fa/verify");

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByLabelText("Код из приложения")).not.toBeInTheDocument();
  });

  it("shows an error when the state cannot be loaded", async () => {
    mockApi({ [STATE]: { status: 500, body: {} } });
    renderPages("/admin/2fa/verify");

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
