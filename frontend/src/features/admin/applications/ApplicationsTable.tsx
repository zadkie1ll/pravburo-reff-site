import { SelectField } from "@/shared/ui/SelectField";

import type { Application, Manager, Option, ProcessingStatus } from "./types";

interface ApplicationsTableProps {
  rows: Application[];
  processingStatuses: Option[];
  managers: Manager[];
  disabled: boolean;
  onStatus: (id: number, status: ProcessingStatus) => void;
  onManager: (id: number, managerId: number | null) => void;
}

export function ApplicationsTable({
  rows,
  processingStatuses,
  managers,
  disabled,
  onStatus,
  onManager,
}: ApplicationsTableProps) {
  const managerOptions = managers.map((manager) => ({
    value: String(manager.id),
    label: manager.label,
  }));

  return (
    <section className="card table-card">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Клиент</th>
              <th>Партнёр</th>
              <th>Город</th>
              <th>Сумма долга</th>
              <th>Доставка</th>
              <th>Обработка</th>
              <th>Менеджер</th>
              <th>Дата заявки</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={8}>Заявки не найдены</td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <strong>{row.client_name}</strong>
                  <br />
                  {row.phone}
                </td>
                <td>
                  {row.agent_name}
                  <br />
                  {row.agent_email || "—"}
                </td>
                <td>{row.city || "—"}</td>
                <td>{row.debt_amount || "—"}</td>
                <td>
                  {row.delivery_label}
                  {row.delivery_error && (
                    <>
                      <br />
                      <small>{row.delivery_error}</small>
                    </>
                  )}
                </td>
                <td>
                  <form onSubmit={(event) => event.preventDefault()}>
                    <SelectField
                      label=""
                      aria-label={`Обработка: ${row.client_name}`}
                      emptyLabel={null}
                      disabled={disabled}
                      options={processingStatuses}
                      value={row.processing_status}
                      onChange={(event) => onStatus(row.id, event.target.value as ProcessingStatus)}
                    />
                  </form>
                </td>
                <td>
                  <form onSubmit={(event) => event.preventDefault()}>
                    <SelectField
                      label=""
                      aria-label={`Менеджер: ${row.client_name}`}
                      emptyLabel="Не назначен"
                      disabled={disabled}
                      options={managerOptions}
                      value={
                        row.assigned_manager_id === null ? "" : String(row.assigned_manager_id)
                      }
                      onChange={(event) =>
                        onManager(row.id, event.target.value ? Number(event.target.value) : null)
                      }
                    />
                  </form>
                </td>
                <td>{row.created_at_label}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
