import type { OverdueRow } from "./types";

interface OverdueTableProps {
  rows: OverdueRow[];
  disabled: boolean;
  onMarkPaid: (rewardId: number) => void;
}

export function OverdueTable({ rows, disabled, onMarkPaid }: OverdueTableProps) {
  return (
    <section className="card table-card">
      <h2>Просроченные выплаты</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Партнёр</th>
              <th>Клиент</th>
              <th>Тип</th>
              <th>Сумма</th>
              <th>Плановая дата</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.reward_id}>
                <td>{row.agent_name}</td>
                <td>{row.client_name}</td>
                <td>{row.type_label}</td>
                <td>{row.amount_label}</td>
                <td>{row.target_date_label}</td>
                <td>
                  <button
                    className="button secondary"
                    type="button"
                    disabled={disabled}
                    aria-label={`Отметить как выплачено: ${row.client_name}, ${row.amount_label}`}
                    onClick={() => onMarkPaid(row.reward_id)}
                  >
                    Отметить как выплачено
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
