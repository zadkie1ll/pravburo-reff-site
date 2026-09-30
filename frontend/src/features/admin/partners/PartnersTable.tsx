import { AccessActions, NoteForm } from "./PartnerActions";
import type { Partner } from "./types";

interface PartnersTableProps {
  rows: Partner[];
  disabled: boolean;
  onNote: (id: number, note: string) => void;
  onBlock: (id: number, reason: string) => void;
  onUnblock: (id: number) => void;
}

export function PartnersTable({ rows, disabled, onNote, onBlock, onUnblock }: PartnersTableProps) {
  return (
    <section className="card table-card">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Партнёр</th>
              <th>Статус</th>
              <th>Клиентов</th>
              <th>Выплачено</th>
              <th>Реквизиты</th>
              <th>Заметка</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={7}>Партнёры не найдены</td>
              </tr>
            )}
            {rows.map((partner) => (
              <tr key={partner.id}>
                <td>
                  <strong>{partner.display_name || "Без имени"}</strong>
                  <br />
                  {partner.email || "—"}
                  <br />
                  {partner.phone || "—"}
                </td>
                <td>
                  {partner.is_active ? (
                    "Активен"
                  ) : (
                    <>
                      <span className="badge">Заблокирован</span>
                      {partner.blocked_reason && (
                        <>
                          <br />
                          <small>{partner.blocked_reason}</small>
                        </>
                      )}
                    </>
                  )}
                </td>
                <td>{partner.client_count}</td>
                <td>{partner.total_paid}</td>
                <td>{partner.payout_details || "—"}</td>
                <td>
                  {/* key: start over with the saved note when the list reloads. */}
                  <NoteForm
                    key={`${partner.id}:${partner.admin_note ?? ""}`}
                    partner={partner}
                    disabled={disabled}
                    onSave={onNote}
                  />
                </td>
                <td>
                  <AccessActions
                    key={`${partner.id}:${partner.is_active}`}
                    partner={partner}
                    disabled={disabled}
                    onBlock={onBlock}
                    onUnblock={onUnblock}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
