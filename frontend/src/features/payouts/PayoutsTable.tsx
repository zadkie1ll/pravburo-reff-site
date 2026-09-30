import type { PayoutRow } from "./types";

export function PayoutsTable({ rows }: { rows: PayoutRow[] }) {
  return (
    <section className="card table-card">
      <div className="table-wrap">
        <table className="table-stack">
          <thead>
            <tr>
              <th>Дата выплаты</th>
              <th>Клиент</th>
              <th>Тип выплаты</th>
              <th>Сумма</th>
              <th>Статус</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={5}>Выплат по выбранным фильтрам нет</td>
              </tr>
            )}
            {rows.map((row, index) => (
              <tr key={`${row.client_name}-${row.type_label}-${index}`}>
                <td data-label="Дата выплаты">{row.payout_date_label}</td>
                <td data-label="Клиент">{row.client_name}</td>
                <td data-label="Тип выплаты">{row.type_label}</td>
                <td data-label="Сумма">{row.amount_label}</td>
                <td data-label="Статус">
                  <span className={`status-pill status-${row.status_slug}`}>
                    {row.status_label}
                  </span>
                  {row.rejection_reason && (
                    <>
                      <br />
                      <small className="reason-note">{row.rejection_reason}</small>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
