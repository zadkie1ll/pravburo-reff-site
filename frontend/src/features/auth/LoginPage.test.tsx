import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, sentBody } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { LoginPage } from "./LoginPage";

const assign = vi.fn();

async function fillAndSubmit() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Почта"), "a@example.com");
  await user.type(screen.getByLabelText("Пароль"), "secret1");
  const button = screen.getByRole("button", { name: "Войти" });
  await waitFor(() => expect(button).toBeEnabled());
  await user.click(button);
}

afterEach(() => {
  vi.unstubAllGlobals();
  assign.mockReset();
});

describe("LoginPage", () => {
  it("posts the credentials with the CSRF token and follows `next`", async () => {
    const api = mockApi({ "/auth/login": { body: { next: "/cabinet" } } });
    vi.stubGlobal("location", { assign });
    renderWithProviders(<LoginPage />);

    await fillAndSubmit();

    await waitFor(() => expect(assign).toHaveBeenCalledWith("/cabinet"));
    const call = api.mock.calls.find(([url]) => url.endsWith("/auth/login"));
    expect(call?.[1]?.headers).toMatchObject({ "X-CSRF-Token": "tok" });
    expect(sentBody(api, "/auth/login")).toEqual({ email: "a@example.com", password: "secret1" });
  });

  it("shows the backend error and does not navigate", async () => {
    mockApi({
      "/auth/login": {
        status: 400,
        body: { error: { code: "invalid_credentials", message: "Неверная почта или пароль" } },
      },
    });
    vi.stubGlobal("location", { assign });
    renderWithProviders(<LoginPage />);

    await fillAndSubmit();

    expect(await screen.findByRole("alert")).toHaveTextContent("Неверная почта или пароль");
    expect(assign).not.toHaveBeenCalled();
  });

  it("offers Yandex when the backend has it configured", async () => {
    mockApi({
      "/auth/config": {
        body: { telegram_bot_username: "", telegram_auth_url: "", yandex_enabled: true },
      },
    });
    renderWithProviders(<LoginPage />);

    expect(await screen.findByRole("link", { name: "Войти через Яндекс" })).toHaveAttribute(
      "href",
      "/auth/yandex/start",
    );
  });

  it("shows an error passed by a failed social callback", () => {
    mockApi();
    renderWithProviders(<LoginPage />, "/login?error=Не удалось проверить Telegram");

    expect(screen.getByRole("alert")).toHaveTextContent("Не удалось проверить Telegram");
  });
});
