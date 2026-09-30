import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { SelectField } from "@/shared/ui/SelectField";

import { querySearch } from "./api";
import type { Option, PayoutsCalendar } from "./types";

interface MonthNavigationProps {
  calendar: PayoutsCalendar;
  statuses: Option[];
  onStatus: (status: string) => void;
}

/** Status filter plus previous/next month links; both keep the rest of the URL. */
export function MonthNavigation({ calendar, statuses, onStatus }: MonthNavigationProps) {
  const [status, setStatus] = useState(calendar.status);
  const search = (target: { year: number; month: number }) =>
    querySearch({ ...target, status: calendar.status });

  function submit(event: FormEvent) {
    event.preventDefault();
    onStatus(status);
  }

  return (
    <section className="card">
      <form className="filter-row" onSubmit={submit}>
        <SelectField
          label="Статус"
          name="status"
          options={statuses}
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        />
        <button className="button" type="submit">
          Показать
        </button>
      </form>
      <div className="footer-actions mt-20">
        <Link className="button secondary" to={{ search: search(calendar.previous) }}>
          ← Предыдущий месяц
        </Link>
        <strong>{calendar.month_label}</strong>
        <Link className="button secondary" to={{ search: search(calendar.next) }}>
          Следующий месяц →
        </Link>
      </div>
    </section>
  );
}
