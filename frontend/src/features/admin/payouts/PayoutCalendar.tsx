import type { CalendarDay } from "./types";

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

interface PayoutCalendarProps {
  weeks: CalendarDay[][];
  disabled: boolean;
  onMarkPaid: (rewardId: number) => void;
}

export function PayoutCalendar({ weeks, disabled, onMarkPaid }: PayoutCalendarProps) {
  return (
    <section className="card table-card">
      <div className="calendar-grid">
        {WEEKDAYS.map((weekday) => (
          <div className="calendar-weekday" key={weekday}>
            {weekday}
          </div>
        ))}
        {weeks.flat().map((day, index) => (
          <div
            key={index}
            className={[
              "calendar-day",
              !day.in_month && "calendar-day-outside",
              day.is_today && "calendar-day-today",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <span className="calendar-day-number">{day.day}</span>
            {day.entries.map((entry) => (
              <div key={entry.reward_id} className={`calendar-entry status-${entry.status_slug}`}>
                <span>
                  {entry.client_name} · {entry.amount_label}
                </span>
                {entry.can_mark_paid && (
                  <button
                    className="text-button"
                    type="button"
                    disabled={disabled}
                    aria-label={`Отметить как выплачено: ${entry.client_name}, ${entry.amount_label}`}
                    onClick={() => onMarkPaid(entry.reward_id)}
                  >
                    Отметить как выплачено
                  </button>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}
