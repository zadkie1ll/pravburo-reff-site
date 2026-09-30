import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, sentBody } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { ConfirmRegistrationPage } from "./ConfirmRegistrationPage";
import { RegisterPage } from "./RegisterPage";

const assign = vi.fn();

function renderFlow(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/register/confirm" element={<ConfirmRegistrationPage />} />
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

describe("registration", () => {
  it("sends the form and moves to the code step with the notice", async () => {
    const api = mockApi({
      "/auth/register": { body: { info: "Если почта свободна, код отправлен на неё" } },
    });
    renderFlow("/register");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Почта"), "new@example.com");
    await user.type(screen.getByLabelText("Пароль"), "secret1");
    await user.type(screen.getByLabelText("Повторите пароль"), "secret1");
    await user.click(await enabled("Получить код"));

    expect(await screen.findByText("Подтвердите почту")).toBeInTheDocument();
    expect(screen.getByText("Если почта свободна, код отправлен на неё")).toBeInTheDocument();
    expect(sentBody(api, "/auth/register")).toEqual({
      email: "new@example.com",
      password: "secret1",
      password_repeat: "secret1",
    });
  });

  it("stays on the form and shows the backend validation message", async () => {
    mockApi({
      "/auth/register": {
        status: 400,
        body: { error: { code: "validation_error", message: "Пароли не совпадают" } },
      },
    });
    renderFlow("/register");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Почта"), "new@example.com");
    await user.type(screen.getByLabelText("Пароль"), "secret1");
    await user.type(screen.getByLabelText("Повторите пароль"), "secret2");
    await user.click(await enabled("Получить код"));

    expect(await screen.findByRole("alert")).toHaveTextContent("Пароли не совпадают");
    expect(screen.queryByText("Подтвердите почту")).not.toBeInTheDocument();
  });

  it("confirms the code and follows `next`", async () => {
    const api = mockApi({ "/register/confirm": { body: { next: "/cabinet" } } });
    vi.stubGlobal("location", { assign });
    renderFlow("/register/confirm");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Код"), "123456");
    await user.click(await enabled("Подтвердить"));

    await waitFor(() => expect(assign).toHaveBeenCalledWith("/cabinet"));
    expect(sentBody(api, "/register/confirm")).toEqual({ code: "123456" });
  });

  it("shows a wrong-code error", async () => {
    mockApi({
      "/register/confirm": {
        status: 400,
        body: { error: { code: "invalid_code", message: "Неверный или просроченный код" } },
      },
    });
    renderFlow("/register/confirm");
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Код"), "000000");
    await user.click(await enabled("Подтвердить"));

    expect(await screen.findByRole("alert")).toHaveTextContent("Неверный или просроченный код");
  });
});
