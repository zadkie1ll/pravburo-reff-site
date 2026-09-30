import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "@/shared/api/client";

import type { Rates } from "./types";

const RATES = "/api/v1/site/admin/network/rates";
const KEY = ["admin", "network", "rates"] as const;

export function useRates() {
  return useQuery({
    queryKey: KEY,
    queryFn: ({ signal }) => apiGet<Rates>(RATES, signal),
  });
}

export function useSaveRates() {
  const client = useQueryClient();
  return useMutation({
    // Amounts by level: { 1: "600.50", 2: "225", 3: "50" }.
    mutationFn: (amounts: Record<number, string>) =>
      apiPost<Rates>(RATES, {
        amount_1: amounts[1] ?? "",
        amount_2: amounts[2] ?? "",
        amount_3: amounts[3] ?? "",
      }),
    onSuccess: (rates) => client.setQueryData(KEY, rates),
  });
}
