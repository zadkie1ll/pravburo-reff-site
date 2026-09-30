import { usePageTitle } from "@/shared/hooks/usePageTitle";

export function NotFoundPage() {
  usePageTitle("Страница не найдена");
  return (
    <section className="not-found">
      <span>404</span>
      <h1>Страница не найдена</h1>
      <p>Проверьте адрес или вернитесь на главную.</p>
      <a className="button" href="/">
        На главную
      </a>
    </section>
  );
}
