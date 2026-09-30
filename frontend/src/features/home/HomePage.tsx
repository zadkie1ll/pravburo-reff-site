import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";

export function HomePage() {
  usePageTitle();
  return (
    <section className="hero compact">
      <p className="eyebrow">Правбюро для партнёров</p>
      <h1>Агентская программа Правбюро</h1>
      <p>
        Рекомендуйте Правбюро людям, которым нужна помощь с долгами, следите за их движением и
        получайте вознаграждение.
      </p>
      <p>
        <AppLink className="button" to="/login">
          Войти
        </AppLink>{" "}
        <AppLink className="button secondary" to="/register">
          Регистрация агента
        </AppLink>
      </p>
    </section>
  );
}
