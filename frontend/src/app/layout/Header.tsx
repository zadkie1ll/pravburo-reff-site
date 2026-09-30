import { useState } from "react";

import { useSession } from "@/features/session/useSession";
import { AppLink } from "@/shared/ui/AppLink";

import { Brand } from "./Brand";
import { homeHref, mainNav } from "./navigation";

export function Header() {
  const { data: session } = useSession();
  const [menuOpen, setMenuOpen] = useState(false);

  const role = session?.role ?? null;
  const authenticated = session?.authenticated ?? false;
  const items = session ? mainNav(role, authenticated, session.onboarding_required) : [];

  return (
    <header className="site-header">
      <Brand
        href={homeHref(role, authenticated)}
        title="Личный кабинет"
        subtitle="Агентская программа"
        ariaLabel="Правбюро — главная"
      />
      <button
        className="menu-toggle"
        type="button"
        aria-label="Открыть меню"
        aria-expanded={menuOpen}
        aria-controls="main-nav"
        onClick={() => setMenuOpen((open) => !open)}
      >
        {menuOpen ? "×" : "☰"}
      </button>
      <nav
        className={menuOpen ? "main-nav is-open" : "main-nav"}
        id="main-nav"
        aria-label="Основная навигация"
      >
        {items.map((item) => (
          <AppLink
            key={item.to}
            to={item.to}
            className={item.cta ? "nav-cta" : undefined}
            onClick={() => setMenuOpen(false)}
          >
            {item.label}
          </AppLink>
        ))}
      </nav>
    </header>
  );
}
