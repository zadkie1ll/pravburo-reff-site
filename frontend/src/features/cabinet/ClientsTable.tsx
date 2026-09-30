import { ClientCell } from "./ClientCell";
import type { ClientRow } from "./types";

export function ClientsTable({ clients }: { clients: ClientRow[] }) {
  return (
    <section className="card table-card">
      <h2>Клиенты</h2>
      <div className="table-wrap">
        <table className="table-stack">
          <thead>
            <tr>
              <th>Клиент</th>
              <th>Дата обращения</th>
              <th>Этап</th>
              <th>Начисление</th>
              <th>Сумма</th>
            </tr>
          </thead>
          <tbody>
            {clients.length === 0 && (
              <tr>
                <td colSpan={5}>Клиентов пока нет</td>
              </tr>
            )}
            {clients.map((row, index) => (
              <tr key={`${row.client_name}-${row.created_at_label}-${index}`}>
                <ClientCell name={row.client_name} maskedPhone={row.masked_phone} />
                <td data-label="Дата обращения">{row.created_at_label}</td>
                <td data-label="Этап">{row.stage}</td>
                <td data-label="Начисление">{row.reward_summary}</td>
                <td data-label="Сумма">{row.reward_totals}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
