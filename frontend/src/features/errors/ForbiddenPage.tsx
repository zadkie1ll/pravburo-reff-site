import { usePageTitle } from "@/shared/hooks/usePageTitle";

export function ForbiddenPage() {
  usePageTitle("Нет доступа");
  return (
    <section className="not-found">
      <span>403</span>
      <h1>Нет доступа</h1>
      <p>У вашей учётной записи нет прав для просмотра этой страницы.</p>
      <a className="button" href="/">
        На главную
      </a>
    </section>
  );
}
