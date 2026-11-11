import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { mockApi, sentBody } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";
import { PartnerEditorPage } from "./PartnerEditorPage";

const PARTNER = {
  id: 7,
  display_name: "Анна Партнёрова",
  email: "anna@example.test",
  phone: "+79990001122",
  employment_format: "individual",
  payout_details: "Карта 2200",
  inn: null,
  admin_note: "После 18",
  is_admin: false,
};

function renderEditor(path: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/partners/new" element={<PartnerEditorPage />} />
      <Route path="/admin/partners/:agentId/edit" element={<PartnerEditorPage />} />
      <Route path="/admin/partners" element={<p>Список партнёров</p>} />
    </Routes>,
    path,
  );
}

describe("PartnerEditorPage", () => {
  it("creates a partner and returns to the searchable list", async () => {
    const api = mockApi({ "/site/admin/partners": { body: PARTNER } });
    renderEditor("/admin/partners/new");
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("ФИО"), "Анна Партнёрова");
    await user.type(screen.getByLabelText("Почта"), "anna@example.test");
    await user.type(screen.getByLabelText("Реквизиты для выплат"), "Карта 2200");
    await user.click(screen.getByRole("button", { name: "Создать партнёра" }));
    expect(await screen.findByText("Список партнёров")).toBeInTheDocument();
    expect(sentBody(api, "/site/admin/partners")).toMatchObject({
      display_name: "Анна Партнёрова",
      email: "anna@example.test",
      employment_format: "individual",
      payout_details: "Карта 2200",
    });
  });

  it("loads existing details, edits payment details and preserves login email", async () => {
    const api = mockApi({ "/partners/7": { body: PARTNER } });
    renderEditor("/admin/partners/7/edit");
    const user = userEvent.setup();
    const details = await screen.findByLabelText("Реквизиты для выплат");
    expect(screen.getByLabelText("Почта")).toHaveAttribute("readonly");
    await user.clear(details);
    await user.type(details, "Новые реквизиты");
    await user.click(screen.getByRole("button", { name: "Сохранить изменения" }));
    await waitFor(() =>
      expect(sentBody(api, "/partners/7")).toMatchObject({
        payout_details: "Новые реквизиты",
        display_name: PARTNER.display_name,
      }),
    );
    expect(sentBody(api, "/partners/7")).not.toHaveProperty("email");
  });

  it("shows server validation errors without losing entered data", async () => {
    mockApi({
      "/partners/7": (body) =>
        body
          ? {
              status: 400,
              body: { error: { code: "partner_invalid", message: "Телефон уже используется" } },
            }
          : { body: PARTNER },
    });
    renderEditor("/admin/partners/7/edit");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Сохранить изменения" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Телефон уже используется");
    expect(screen.getByLabelText("ФИО")).toHaveValue(PARTNER.display_name);
  });

  it("does not offer editing an administrator", async () => {
    mockApi({ "/partners/7": { body: { ...PARTNER, is_admin: true } } });
    renderEditor("/admin/partners/7/edit");
    expect(await screen.findByText("Аккаунт администратора")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Сохранить изменения" })).not.toBeInTheDocument();
  });
});
