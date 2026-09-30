import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { useVisits } from "./api";
import { BackToCabinet } from "./BackToCabinet";

export function VisitsPage() {
  usePageTitle("Переходы по ссылке");
  const { data: visits, isPending, isError } = useVisits();

  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;

  return (
    <>
      <section className="hero">
        <p className="eyebrow">Кабинет агента</p>
        <h1>Переходы по ссылке</h1>
      </section>
      <section className="card table-card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Дата</th>
                <th>Переходов</th>
              </tr>
            </thead>
            <tbody>
              {visits.days.length === 0 && (
                <tr>
                  <td colSpan={2}>Переходов по ссылке пока нет</td>
                </tr>
              )}
              {visits.days.map((day) => (
                <tr key={day.day_label}>
                  <td>{day.day_label}</td>
                  <td>{day.count}</td>
                </tr>
              ))}
            </tbody>
            {visits.days.length > 0 && (
              <tfoot>
                <tr>
                  <th>Всего</th>
                  <th>{visits.total}</th>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </section>
      <BackToCabinet />
    </>
  );
}
