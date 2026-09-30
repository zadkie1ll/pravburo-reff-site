import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, sentBody } from "@/test/mockApi";
import { renderWithProviders } from "@/test/renderWithProviders";

import { OnboardingPage } from "./OnboardingPage";

const assign = vi.fn();
const replace = vi.fn();

const NEW_PARTNER = {
  authenticated: true,
  email: "new@example.com",
  role: "agent",
  onboarding_required: true,
  csrf_token: "tok",
};

const OPTIONS = {
  options: [
    { value: "self_employed", title: "Самозанятый", text: "Налог 4%." },
    { value: "individual", title: "Физическое лицо", text: "Удерживается 43%." },
  ],
  telegram_manager_url: "https://t.me/manager",
};

afterEach(() => {
  vi.unstubAllGlobals();
  assign.mockReset();
  replace.mockReset();
});

describe("OnboardingPage", () => {
  it("saves the chosen format and follows `next`", async () => {
    const api = mockApi({
      "/me": { body: NEW_PARTNER },
      "/site/onboarding": { body: OPTIONS },
    });
    vi.stubGlobal("location", { assign, replace });
    renderWithProviders(<OnboardingPage />);
    const user = userEvent.setup();

    const button = await screen.findByRole("button", { name: "Продолжить" });
    expect(button).toBeDisabled();
    await user.click(screen.getByLabelText(/Самозанятый/));
    await user.click(button);

    await waitFor(() => expect(assign).toHaveBeenCalled());
    expect(sentBody(api, "/site/onboarding")).toEqual({ employment_format: "self_employed" });
  });

  it("links to the manager for people no option fits", async () => {
    mockApi({ "/me": { body: NEW_PARTNER }, "/site/onboarding": { body: OPTIONS } });
    renderWithProviders(<OnboardingPage />);

    expect(await screen.findByRole("link", { name: "Написать менеджеру" })).toHaveAttribute(
      "href",
      "https://t.me/manager",
    );
  });

  it("sends a partner who already chose a format to the cabinet", async () => {
    mockApi({
      "/me": { body: { ...NEW_PARTNER, onboarding_required: false } },
      "/site/onboarding": { body: OPTIONS },
    });
    vi.stubGlobal("location", { assign, replace });
    renderWithProviders(<OnboardingPage />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/cabinet"));
  });
});
