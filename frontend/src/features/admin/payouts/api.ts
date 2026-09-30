import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiGet, apiPost } from "@/shared/api/client";
import { useInvalidatingMutation } from "@/shared/api/useInvalidatingMutation";

import type { CalendarQuery, PayoutsCalendar } from "./types";

const BASE = "/api/v1/site/admin/payouts";
const KEY = ["admin", "payouts"] as const;

/** Search string ("?year=..&month=..&status=..") with only what is set. */
export function querySearch({ year, month, status }: CalendarQuery): string {
  const params = new URLSearchParams();
  if (year !== null) params.set("year", String(year));
  if (month !== null) params.set("month", String(month));
  if (status) params.set("status", status);
  const text = params.toString();
  return text ? `?${text}` : "";
}

export function useCalendar(query: CalendarQuery) {
  const search = querySearch(query);
  return useQuery({
    queryKey: [...KEY, search],
    queryFn: ({ signal }) => apiGet<PayoutsCalendar>(`${BASE}${search}`, signal),
    placeholderData: keepPreviousData,
  });
}

export function useSaveOverdueDays() {
  return useInvalidatingMutation(KEY, (days: number) =>
    apiPost(`${BASE}/settings`, { overdue_days: days }),
  );
}

export function useMarkPaid() {
  return useInvalidatingMutation(KEY, (rewardId: number) =>
    apiPost(`${BASE}/${rewardId}/mark-paid`),
  );
}
