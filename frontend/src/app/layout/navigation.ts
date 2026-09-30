import type { Role } from "@/features/session/types";

export interface NavItem {
  to: string;
  label: string;
  cta?: boolean;
}

export function homeHref(role: Role | null, authenticated: boolean): string {
  if (role === "admin") return "/admin";
  return authenticated ? "/cabinet" : "/";
}

export function mainNav(role: Role | null, authenticated: boolean, onboarding = false): NavItem[] {
  // A partner who has not chosen a cooperation format cannot use the cabinet yet.
  if (onboarding) return [{ to: "/faq", label: "Как это работает" }];
  if (role === "admin") {
    return [
      { to: "/admin", label: "Админ-панель" },
      { to: "/faq", label: "Как это работает" },
    ];
  }
  if (authenticated) {
    return [
      { to: "/cabinet", label: "Главная" },
      { to: "/payouts", label: "Выплаты" },
      { to: "/faq", label: "Как это работает" },
      { to: "/profile", label: "Профиль" },
    ];
  }
  return [
    { to: "/faq", label: "Как это работает" },
    { to: "/login", label: "Войти" },
    { to: "/register", label: "Стать агентом", cta: true },
  ];
}

export function footerNav(
  role: Role | null,
  authenticated: boolean,
  onboarding = false,
): NavItem[] {
  if (onboarding) return [];
  if (role === "admin") return [{ to: "/admin", label: "Админ-панель" }];
  if (authenticated) {
    return [
      { to: "/cabinet", label: "Главная" },
      { to: "/payouts", label: "Выплаты" },
    ];
  }
  return [];
}
