import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, sentBody } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { PasswordResetConfirmPage } from "./PasswordResetConfirmPage";
import { PasswordResetPage } from "./PasswordResetPage";

const assign = vi.fn();

const AGENT_SESSION = {
  authenticated: true,
  email: "agent@example.com",
  role: "agent",
  onboarding_required: false,
  csrf_token: "tok",
};

function renderFlow(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/password/reset" element={<PasswordResetPage />} />
      <Route path="/password/reset/confirm" element={<PasswordResetConfirmPage />} />
    </Routes>,
    route,
  );
}

async function enabled(name: string) {
  const button = screen.getByRole("button", { name });
  await waitFor(() => expect(button).toBeEnabled());
  return button;
}

afterEach(() => {
  vi.unstubAllGlobals();
  assign.mockReset();
});

describe("password reset", () => {
  it("recovers the password for a guest", async () => {
    const api = mockApi({
      "/auth/password-reset": { body: { info: "Если аккаунт существует, код отправлен на почту" } },
    });
    renderFlow("/password/reset");
    const user = userEvent.setup();

    expect(screen.getByRole("heading", { name: "Восстановить пароль" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Почта"), "agent@example.com");
    await user.click(await enabled("Получить код"));

    expect(await screen.findByRole("heading", { name: "Новый пароль" })).toBeInTheDocument();
    expect(screen.getByText("Если аккаунт существует, код отправлен на почту")).toBeInTheDocument();
    expect(sentBody(api, "/auth/password-reset")).toEqual({ email: "agent@example.com" });
  });

  it("changes the password for a logged-in partner, with the e-mail prefilled", async () => {
    mockApi({ "/me": { body: AGENT_SESSION } });
    renderFlow("/password/reset");

    expect(await screen.findByRole("heading", { name: "Изменить пароль" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Почта")).toHaveValue("agent@example.com"));
  });

  it("saves the new password and follows `next`", async () => {
    const api = mockApi({ "/password-reset/confirm": { body: { next: "/cabinet" } } });
    vi.stubGlobal("location", { assign });
    renderFlow("/password/reset/confirm");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Код"), "654321");
    await user.type(screen.getByLabelText("Новый пароль"), "newpass1");
    await user.type(screen.getByLabelText("Повторите пароль"), "newpass1");
    await user.click(await enabled("Сохранить"));

    await waitFor(() => expect(assign).toHaveBeenCalledWith("/cabinet"));
    expect(sentBody(api, "/password-reset/confirm")).toEqual({
      code: "654321",
      password: "newpass1",
      password_repeat: "newpass1",
    });
  });

  it("shows the backend error for a wrong code", async () => {
    mockApi({
      "/password-reset/confirm": {
        status: 400,
        body: { error: { code: "invalid_code", message: "Неверный или просроченный код" } },
      },
    });
    renderFlow("/password/reset/confirm");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Код"), "000000");
    await user.type(screen.getByLabelText("Новый пароль"), "newpass1");
    await user.type(screen.getByLabelText("Повторите пароль"), "newpass1");
    await user.click(await enabled("Сохранить"));

    expect(await screen.findByRole("alert")).toHaveTextContent("Неверный или просроченный код");
  });
});
