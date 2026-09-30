import { AppLink } from "@/shared/ui/AppLink";

import type { Finance } from "./types";

export function FinanceCard({ finance }: { finance: Finance }) {
  return (
    <section className="card">
      <h2>Финансы</h2>
      <p className="metric">{finance.total_paid_label}</p>
      <p>выплачено всего</p>
      <dl className="details">
        <div>
          <dt>Получено в этом месяце</dt>
          <dd>{finance.this_month_label}</dd>
        </div>
        <div>
          <dt>Ожидает выплаты</dt>
          <dd>{finance.pending_total_label}</dd>
        </div>
        {finance.pending_groups.map((group) => (
          <div key={group.label}>
            <dt>{group.label}</dt>
            <dd>{group.amount_label}</dd>
          </div>
        ))}
      </dl>
      <AppLink to="/payouts">Подробнее о выплатах →</AppLink>
    </section>
  );
}
