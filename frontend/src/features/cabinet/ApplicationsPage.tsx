import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { useApplications } from "./api";
import { BackToCabinet } from "./BackToCabinet";
import { ClientCell } from "./ClientCell";

export function ApplicationsPage() {
  usePageTitle("Оставлено заявок");
  const { data, isPending, isError } = useApplications();

  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;

  return (
    <>
      <section className="hero">
        <p className="eyebrow">Кабинет агента</p>
        <h1>Оставлено заявок</h1>
      </section>
      <section className="card table-card">
        <div className="table-wrap">
          <table className="table-stack">
            <thead>
              <tr>
                <th>Клиент</th>
                <th>Дата обращения</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.length === 0 && (
                <tr>
                  <td colSpan={3}>Заявок пока нет</td>
                </tr>
              )}
              {data.rows.map((row, index) => (
                <tr key={`${row.client_name}-${row.created_at_label}-${index}`}>
                  <ClientCell name={row.client_name} maskedPhone={row.masked_phone} />
                  <td data-label="Дата обращения">{row.created_at_label}</td>
                  <td data-label="Статус">{row.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <BackToCabinet />
    </>
  );
}
