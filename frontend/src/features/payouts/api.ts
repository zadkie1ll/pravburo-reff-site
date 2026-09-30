import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiGet } from "@/shared/api/client";

import type { PayoutFilters, Payouts } from "./types";

/** Query string with only the filters that are set (an empty filter means "all"). */
export function filtersToQuery(filters: PayoutFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  return params.toString();
}

export function usePayouts(filters: PayoutFilters) {
  const query = filtersToQuery(filters);
  return useQuery({
    queryKey: ["payouts", query],
    queryFn: ({ signal }) =>
      apiGet<Payouts>(`/api/v1/site/payouts${query ? `?${query}` : ""}`, signal),
    // Keep the table (and the filter form) on screen while a new filter loads.
    placeholderData: keepPreviousData,
  });
}
