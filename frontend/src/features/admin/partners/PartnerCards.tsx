import { AppLink } from "@/shared/ui/AppLink";
import { AdminIcon } from "../AdminIcon";
import { AccessActions, NoteForm } from "./PartnerActions";
import type { Partner } from "./types";

interface PartnerCardsProps {
  rows: Partner[];
  disabled: boolean;
  onNote: (id: number, note: string) => void;
  onBlock: (id: number, reason: string) => void;
  onUnblock: (id: number) => void;
}

const money = (value: string) => {
  const number = Number(value);
  return Number.isFinite(number)
    ? new Intl.NumberFormat("ru-RU", {
        style: "currency",
        currency: "RUB",
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      }).format(number)
    : "—";
};

export function PartnerCards({ rows, disabled, onNote, onBlock, onUnblock }: PartnerCardsProps) {
  if (rows.length === 0)
    return (
      <section className="card">
        <p>Партнёры не найдены</p>
      </section>
    );

  return (
    <div className="partner-card-grid">
      {rows.map((partner) => {
        const name = partner.display_name || "Без имени";
        const initials =
          partner.display_name
            .trim()
            .split(/\s+/)
            .slice(0, 2)
            .map((part) => part[0])
            .join("")
            .toUpperCase() || "П";
        return (
          <article
            key={partner.id}
            className="partner-profile-card"
            aria-label={`Партнёр: ${name}`}
          >
            <header className="partner-card-header">
              <span className="partner-avatar" aria-hidden="true">
                {initials}
              </span>
              <div className="partner-card-identity">
                <h2>{name}</h2>
                <small>
                  #{partner.id}
                  {partner.is_admin ? " · Администратор" : ""}
                </small>
              </div>
              <span
                className={`partner-access-badge ${partner.is_active ? "is-active" : "is-blocked"}`}
              >
                {partner.is_active ? "Активен" : "Заблокирован"}
              </span>
            </header>
            <div className="partner-contact-list">
              <span>{partner.email || "Почта не указана"}</span>
              <span>{partner.phone || "Телефон не указан"}</span>
            </div>
            {!partner.is_active && partner.blocked_reason && (
              <p className="partner-blocked-reason">{partner.blocked_reason}</p>
            )}
            <dl className="partner-card-metrics">
              <div>
                <dt>Клиентов</dt>
                <dd>{partner.client_count}</dd>
              </div>
              <div>
                <dt>Выплачено</dt>
                <dd>{money(partner.total_paid)}</dd>
              </div>
            </dl>
            <div className="partner-bank-details">
              <span>Реквизиты для выплат</span>
              <p>{partner.payout_details || "Не указаны"}</p>
            </div>
            {partner.admin_note && <p className="partner-note-preview">{partner.admin_note}</p>}
            <div className="partner-card-tools">
              {!partner.is_admin && (
                <AppLink
                  className="partner-edit-button"
                  to={`/admin/partners/${partner.id}/edit`}
                  aria-label={`Редактировать партнёра: ${name}`}
                >
                  <AdminIcon name="edit" /> Редактировать
                </AppLink>
              )}
              <details className="partner-disclosure">
                <summary>
                  <AdminIcon name="applications" />
                  Заметка
                </summary>
                <NoteForm
                  key={`${partner.id}:${partner.admin_note ?? ""}`}
                  partner={partner}
                  disabled={disabled}
                  onSave={onNote}
                />
              </details>
              {!partner.is_admin && (
                <details className="partner-disclosure partner-access-disclosure">
                  <summary>
                    <AdminIcon name="partners" />
                    Управление доступом
                  </summary>
                  <AccessActions
                    key={`${partner.id}:${partner.is_active}`}
                    partner={partner}
                    disabled={disabled}
                    onBlock={onBlock}
                    onUnblock={onUnblock}
                  />
                </details>
              )}
            </div>
          </article>
        );
      })}
    </div>
  );
}
