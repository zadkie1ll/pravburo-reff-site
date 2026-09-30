import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/renderWithProviders";

import { HomePage } from "./HomePage";

afterEach(() => vi.unstubAllGlobals());

describe("HomePage", () => {
  it("introduces the program and offers to sign in or register", () => {
    renderWithProviders(<HomePage />);

    expect(
      screen.getByRole("heading", { name: "Агентская программа Правбюро" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: "Регистрация агента" })).toHaveAttribute(
      "href",
      "/register",
    );
  });

  it("uses the plain site name as the page title", () => {
    renderWithProviders(<HomePage />);

    expect(document.title).toBe("Правбюро");
  });
});
