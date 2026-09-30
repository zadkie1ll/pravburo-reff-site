import { AppLink } from "@/shared/ui/AppLink";

import type { LinkStats } from "./types";

export function LinkStatsCard({ stats }: { stats: LinkStats }) {
  return (
    <section className="card card-wide">
      <h2>Переходы по ссылке</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Показатель</th>
              <th>Значение</th>
            </tr>
          </thead>
          <tbody>
            <tr className="row-link">
              <td>
                <AppLink to="/cabinet/visits">Переходов по ссылке →</AppLink>
              </td>
              <td>{stats.visits}</td>
            </tr>
            <tr className="row-link">
              <td>
                <AppLink to="/cabinet/applications">Оставлено заявок →</AppLink>
              </td>
              <td>{stats.applications}</td>
            </tr>
            <tr className="row-link">
              <td>
                <AppLink to="/payouts">Заключено договоров →</AppLink>
              </td>
              <td>{stats.contracts}</td>
            </tr>
            <tr>
              <td>Конверсия в заявки</td>
              <td>{stats.conversion_rate_label}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
