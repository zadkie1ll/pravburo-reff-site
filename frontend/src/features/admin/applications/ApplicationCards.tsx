import { SelectField } from "@/shared/ui/SelectField";

import type { Application, Manager, Option, ProcessingStatus } from "./types";

interface ApplicationCardsProps {
  rows: Application[];
  processingStatuses: Option[];
  managers: Manager[];
  disabled: boolean;
  onStatus: (id: number, status: ProcessingStatus) => void;
  onManager: (id: number, managerId: number | null) => void;
}

export function ApplicationCards({
  rows,
  processingStatuses,
  managers,
  disabled,
  onStatus,
  onManager,
}: ApplicationCardsProps) {
  const managerOptions = managers.map((manager) => ({
    value: String(manager.id),
    label: manager.label,
  }));

  if (rows.length === 0)
    return (
      <section className="card">
        <p>Заявки не найдены</p>
      </section>
    );
  return (
    <div className="partner-card-grid application-card-grid">
      {rows.map((row) => (
        <article
          key={row.id}
          className="partner-profile-card application-card"
          aria-label={`Заявка: ${row.client_name}`}
        >
          <header className="partner-card-header">
            <span className="partner-avatar" aria-hidden="true">
              {row.client_name
                .trim()
                .split(/\s+/)
                .slice(0, 2)
                .map((p) => p[0])
                .join("")
                .toUpperCase() || "З"}
            </span>
            <div className="partner-card-identity">
              <h2>{row.client_name}</h2>
              <small>
                Заявка #{row.id} · {row.created_at_label}
              </small>
            </div>
            <span className={`application-status is-${row.processing_status}`}>
              {processingStatuses.find((s) => s.value === row.processing_status)?.label ??
                row.processing_status}
            </span>
          </header>
          <p className="application-phone">{row.phone}</p>
          <dl className="partner-card-metrics">
            <div>
              <dt>Город</dt>
              <dd>{row.city || "Не указан"}</dd>
            </div>
            <div>
              <dt>Сумма долга</dt>
              <dd>{row.debt_amount || "Не указана"}</dd>
            </div>
          </dl>
          <div className="application-partner">
            <span>Пригласивший партнёр</span>
            <strong>{row.agent_name}</strong>
            <small>{row.agent_email || "Почта не указана"}</small>
          </div>
          <div className="application-delivery">
            <span>Доставка в Битрикс</span>
            <p>{row.delivery_label}</p>
            {row.delivery_error && (
              <p className="application-delivery-error">{row.delivery_error}</p>
            )}
          </div>
          <div className="application-controls">
            <SelectField
              label="Обработка"
              aria-label={`Обработка: ${row.client_name}`}
              emptyLabel={null}
              disabled={disabled}
              options={processingStatuses}
              value={row.processing_status}
              onChange={(e) => onStatus(row.id, e.target.value as ProcessingStatus)}
            />
            <SelectField
              label="Менеджер"
              aria-label={`Менеджер: ${row.client_name}`}
              emptyLabel="Не назначен"
              disabled={disabled}
              options={managerOptions}
              value={row.assigned_manager_id === null ? "" : String(row.assigned_manager_id)}
              onChange={(e) => onManager(row.id, e.target.value ? Number(e.target.value) : null)}
            />
          </div>
        </article>
      ))}
    </div>
  );
}
