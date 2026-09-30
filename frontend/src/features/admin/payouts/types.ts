export interface Option {
  value: string;
  label: string;
}

export interface MonthRef {
  year: number;
  month: number;
}

export interface CalendarEntry {
  reward_id: number;
  client_name: string;
  amount_label: string;
  status_slug: string;
  can_mark_paid: boolean;
}

export interface CalendarDay {
  day: number;
  in_month: boolean;
  is_today: boolean;
  entries: CalendarEntry[];
}

export interface OverdueRow {
  reward_id: number;
  agent_name: string;
  client_name: string;
  type_label: string;
  amount_label: string;
  target_date_label: string;
}

export interface PayoutsCalendar {
  year: number;
  month: number;
  month_label: string;
  status: string;
  statuses: Option[];
  overdue_days: number;
  previous: MonthRef;
  next: MonthRef;
  weeks: CalendarDay[][];
  overdue_rows: OverdueRow[];
}

/** What the URL holds: empty year/month mean "the current month". */
export interface CalendarQuery {
  year: number | null;
  month: number | null;
  status: string;
}
