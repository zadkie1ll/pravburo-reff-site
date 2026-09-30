import { useSearchParams } from "react-router-dom";

import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { querySearch, useCalendar, useMarkPaid, useSaveOverdueDays } from "./api";
import { MonthNavigation } from "./MonthNavigation";
import { OverdueDaysForm } from "./OverdueDaysForm";
import { OverdueTable } from "./OverdueTable";
import { PayoutCalendar } from "./PayoutCalendar";
import type { CalendarQuery } from "./types";

const intOrNull = (value: string | null) => {
  const number = Number(value);
  return value !== null && Number.isInteger(number) && number > 0 ? number : null;
};

const CONFIRM_PAID =
  "Отметить выплату как выплаченную? Партнёру уйдут уведомления, отменить это нельзя.";

export function AdminPayoutsPage() {
  usePageTitle("Выплаты");
  // Month and status live in the URL: shareable, Back works. No year/month = the current month.
  const [params, setParams] = useSearchParams();
  const query: CalendarQuery = {
    year: intOrNull(params.get("year")),
    month: intOrNull(params.get("month")),
    status: params.get("status") ?? "",
  };
  const { data, isPending, isError } = useCalendar(query);
  const saveDays = useSaveOverdueDays();
  const markPaid = useMarkPaid();

  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;

  const busy = saveDays.isPending || markPaid.isPending;
  const failure = saveDays.error ?? markPaid.error;

  function pay(rewardId: number) {
    // Marking a payout paid e-mails/pushes the partner and cannot be undone: ask first.
    if (window.confirm(CONFIRM_PAID)) markPaid.mutate(rewardId);
  }

  return (
    <>
      <section className="card">
        <p className="eyebrow">Администратор</p>
        <h1>Выплаты</h1>
        <p>
          Дата на календаре — фактическая дата выплаты, если она уже сделана, иначе плановый срок
          (одобрение + {data.overdue_days} дн.). Выплата без даты одобрения не показана на календаре
          — она ещё не одобрена в сервисе вознаграждений.
        </p>
        <OverdueDaysForm
          key={data.overdue_days}
          days={data.overdue_days}
          disabled={busy}
          onSave={(days) => saveDays.mutate(days)}
        />
      </section>

      {failure && (
        <p className="alert" role="alert">
          {errorMessage(failure, "Не удалось выполнить действие.")}
        </p>
      )}

      {data.overdue_rows.length > 0 && (
        <OverdueTable rows={data.overdue_rows} disabled={busy} onMarkPaid={pay} />
      )}

      <MonthNavigation
        key={data.status}
        calendar={data}
        statuses={data.statuses}
        onStatus={(status) => setParams(new URLSearchParams(querySearch({ ...query, status })))}
      />
      <PayoutCalendar weeks={data.weeks} disabled={busy} onMarkPaid={pay} />

      <p className="mt-20">
        <AppLink to="/admin">← Админ-панель</AppLink>
      </p>
    </>
  );
}
