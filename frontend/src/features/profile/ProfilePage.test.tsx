import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, sentBody } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { ProfilePage } from "./ProfilePage";
import type { Profile } from "./types";

const PROFILE: Profile = {
  display_name: "Ольга Тестова",
  email: "olga@example.com",
  phone: "+79990001122",
  employment_format: "self_employed",
  payout_details: "Карта 1234",
  inn: "123456789012",
  registered_at_label: "01.09.2026",
  is_active: true,
  is_admin: false,
  pending_email: "",
  yandex_enabled: true,
  yandex_linked: false,
  employment_formats: [
    { value: "self_employed", label: "Самозанятый" },
    { value: "individual_entrepreneur", label: "ИП" },
    { value: "individual", label: "Физлицо" },
  ],
};

const error = (code: string, message: string) => ({
  status: 400,
  body: { error: { code, message } },
});

afterEach(() => vi.unstubAllGlobals());

describe("ProfilePage", () => {
  it("shows the summary of the partner's data", async () => {
    mockApi({ "/site/profile": { body: PROFILE } });
    renderWithProviders(<ProfilePage />);

    const summary = (await screen.findByRole("heading", { name: "Основное" })).closest("section");
    expect(summary).toHaveTextContent("+79990001122");
    expect(summary).toHaveTextContent("Самозанятый");
    expect(summary).toHaveTextContent("Карта 1234");
    expect(summary).toHaveTextContent("Активен");
    expect(screen.getByLabelText("ФИО")).toHaveValue("Ольга Тестова");
    expect(screen.getByLabelText("Формат сотрудничества")).toHaveValue("self_employed");
  });

  it("saves the changed data and confirms it", async () => {
    const api = mockApi({
      "/site/profile": (body) => ({
        body: body ? { ...PROFILE, ...(body as object), display_name: "Новое Имя" } : PROFILE,
      }),
    });
    renderWithProviders(<ProfilePage />);
    const user = userEvent.setup();

    const name = await screen.findByLabelText("ФИО");
    await user.clear(name);
    await user.type(name, "Новое Имя");
    await user.selectOptions(screen.getByLabelText("Формат сотрудничества"), "individual");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    expect(await screen.findByText("Профиль обновлён")).toBeInTheDocument();
    expect(sentBody(api, "/site/profile")).toEqual({
      display_name: "Новое Имя",
      phone: "+79990001122",
      employment_format: "individual",
      payout_details: "Карта 1234",
      inn: "123456789012",
    });
  });

  it("shows the backend's reason when the data is refused", async () => {
    mockApi({
      "/site/profile": (body) =>
        body
          ? error("profile_invalid", "Укажите корректный ИНН (10 или 12 цифр)")
          : { body: PROFILE },
    });
    renderWithProviders(<ProfilePage />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Сохранить" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Укажите корректный ИНН");
  });

  it("changes the e-mail in two steps", async () => {
    let pending = "";
    const api = mockApi({
      "/site/profile": () => ({ body: { ...PROFILE, pending_email: pending } }),
      "/profile/email": () => {
        pending = "new@example.com";
        return { body: { info: "Код отправлен на новую почту" } };
      },
      "/profile/email/confirm": () => {
        pending = "";
        return { body: { info: "Почта изменена" } };
      },
    });
    renderWithProviders(<ProfilePage />);
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Новая почта"), "new@example.com");
    await user.type(screen.getByLabelText("Текущий пароль"), "secret");
    await user.click(screen.getByRole("button", { name: "Сменить почту" }));

    expect(await screen.findByText("Код отправлен на новую почту")).toBeInTheDocument();
    expect(await screen.findByText("new@example.com", { selector: "strong" })).toBeInTheDocument();
    expect(sentBody(api, "/profile/email")).toEqual({
      new_email: "new@example.com",
      current_password: "secret",
    });

    await user.type(screen.getByLabelText("Код из письма"), "123456");
    await user.click(screen.getByRole("button", { name: "Подтвердить почту" }));

    expect(await screen.findByText("Почта изменена")).toBeInTheDocument();
    expect(sentBody(api, "/profile/email/confirm")).toEqual({ code: "123456" });
    expect(await screen.findByLabelText("Новая почта")).toBeInTheDocument();
  });

  it("shows why the e-mail change was refused", async () => {
    mockApi({
      "/site/profile": { body: PROFILE },
      "/profile/email": error("invalid_password", "Неверный пароль"),
    });
    renderWithProviders(<ProfilePage />);
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Новая почта"), "new@example.com");
    await user.type(screen.getByLabelText("Текущий пароль"), "wrong");
    await user.click(screen.getByRole("button", { name: "Сменить почту" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Неверный пароль");
  });

  it("offers to link Yandex, or says it is linked, or hides it when unavailable", async () => {
    mockApi({ "/site/profile": { body: PROFILE } });
    const first = renderWithProviders(<ProfilePage />);
    expect(await screen.findByRole("link", { name: "Привязать Яндекс →" })).toHaveAttribute(
      "href",
      "/auth/yandex/start",
    );
    first.unmount();

    mockApi({ "/site/profile": { body: { ...PROFILE, yandex_linked: true } } });
    const second = renderWithProviders(<ProfilePage />);
    expect(await screen.findByText("Яндекс привязан")).toBeInTheDocument();
    second.unmount();

    mockApi({ "/site/profile": { body: { ...PROFILE, yandex_enabled: false } } });
    renderWithProviders(<ProfilePage />);
    await screen.findByLabelText("ФИО");
    expect(screen.queryByText(/Яндекс/)).not.toBeInTheDocument();
  });

  it("shows the message a Yandex callback left in the address", async () => {
    mockApi({ "/site/profile": { body: PROFILE } });
    renderWithProviders(<ProfilePage />, "/profile?info=Яндекс привязан");

    expect(
      await screen.findByText("Яндекс привязан", { selector: ".notice-success" }),
    ).toBeVisible();
  });

  it("links an admin to the admin panel", async () => {
    mockApi({ "/site/profile": { body: { ...PROFILE, is_admin: true } } });
    renderWithProviders(<ProfilePage />);

    expect(await screen.findByRole("link", { name: "Админ-панель" })).toHaveAttribute(
      "href",
      "/admin",
    );
  });

  it("shows an error when the profile cannot be loaded", async () => {
    mockApi({ "/site/profile": { status: 500, body: {} } });
    renderWithProviders(<ProfilePage />);

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });
});
