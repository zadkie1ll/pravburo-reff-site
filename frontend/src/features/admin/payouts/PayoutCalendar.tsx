import { useState } from "react";

import type { CalendarDay } from "./types";

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

interface PayoutCalendarProps {
  weeks: CalendarDay[][];
  year: number;
  month: number;
  disabled: boolean;
  onMarkPaid: (rewardId: number) => void;
}

export function PayoutCalendar({ weeks, year, month, disabled, onMarkPaid }: PayoutCalendarProps) {
  const days = weeks.flat();
  const [selected, setSelected] = useState(() => {
    const today = days.findIndex((day) => day.in_month && day.is_today);
    if (today !== -1) return today;
    const first = days.findIndex((day) => day.in_month && day.entries.length > 0);
    return first === -1 ? days.findIndex((day) => day.in_month) : first;
  });
  const [visibleCount, setVisibleCount] = useState(6);
  const active = days[selected];
  const dateLabel = (day: number) =>
    new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" }).format(
      new Date(year, month - 1, day),
    );

  return (
    <section className="card table-card payout-calendar">
      <div className="payout-calendar-heading">
        <div>
          <h2>Календарь выплат</h2>
          <p>Выберите день, чтобы посмотреть начисления и отметить выплату.</p>
        </div>
        <div className="payout-legend" aria-label="Обозначения статусов">
          <span>
            <i className="payout-dot status-scheduled" />К выплате
          </span>
          <span>
            <i className="payout-dot status-paid" />
            Выплачено
          </span>
          <span>
            <i className="payout-dot status-overdue" />
            Просрочено / отклонено
          </span>
        </div>
      </div>
      <div className="calendar-grid">
        {WEEKDAYS.map((weekday) => (
          <div className="calendar-weekday" key={weekday}>
            {weekday}
          </div>
        ))}
        {weeks.flat().map((day, index) => (
          <button
            type="button"
            key={index}
            disabled={!day.in_month}
            aria-label={
              day.in_month ? `${dateLabel(day.day)}: начислений ${day.entries.length}` : undefined
            }
            aria-pressed={day.in_month && index === selected}
            aria-controls="payout-day-details"
            aria-current={day.is_today ? "date" : undefined}
            onClick={() => {
              setSelected(index);
              setVisibleCount(6);
            }}
            className={[
              "calendar-day",
              !day.in_month && "calendar-day-outside",
              day.is_today && "calendar-day-today",
              index === selected && "calendar-day-selected",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <span className="calendar-day-number">{day.day}</span>
            {day.entries.length > 0 && (
              <>
                <span className="calendar-day-count">
                  <span>Начислений: </span>
                  {day.entries.length}
                </span>
                <strong className="calendar-day-total">{day.total_amount_label}</strong>
                <span className="calendar-day-dots" aria-hidden="true">
                  {[...new Set(day.entries.map((entry) => entry.status_slug))].map((status) => (
                    <i key={status} className={`payout-dot status-${status}`} />
                  ))}
                </span>
              </>
            )}
          </button>
        ))}
      </div>
      {active && (
        <div id="payout-day-details" className="payout-day-details">
          <div className="payout-day-heading">
            <h3>Начисления на {dateLabel(active.day)}</h3>
            <span>Всего: {active.total_amount_label}</span>
          </div>
          {active.entries.length === 0 && (
            <p className="payout-empty">На этот день начислений нет.</p>
          )}
          <div className="payout-day-list">
            {active.entries.slice(0, visibleCount).map((entry) => (
              <article key={entry.reward_id} className="payout-detail-row">
                <div className="payout-detail-person">
                  <strong>{entry.agent_name}</strong>
                  <span>
                    {entry.client_name === "—" ? "Без привязки к клиенту" : entry.client_name}
                  </span>
                  <small>{entry.type_label}</small>
                </div>
                <div className="payout-detail-amount">
                  <strong>{entry.amount_label}</strong>
                  <span className={`status-pill status-${entry.status_slug}`}>
                    {entry.status_label}
                  </span>
                </div>
                <div className="payout-detail-action">
                  {entry.can_mark_paid && (
                    <button
                      className="button secondary"
                      type="button"
                      disabled={disabled}
                      aria-label={`Отметить как выплачено: ${entry.client_name}, ${entry.amount_label}`}
                      onClick={() => onMarkPaid(entry.reward_id)}
                    >
                      Отметить как выплачено
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
          {active.entries.length > visibleCount && (
            <button
              className="text-button payout-show-more"
              type="button"
              onClick={() => setVisibleCount((count) => count + 6)}
            >
              Показать ещё ({active.entries.length - visibleCount})
            </button>
          )}
        </div>
      )}
    </section>
  );
}
