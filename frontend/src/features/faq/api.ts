import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/shared/api/client";

import type { FaqResponse } from "./types";

export function useFaq() {
  return useQuery({
    queryKey: ["faq"],
    queryFn: ({ signal }) => apiGet<FaqResponse>("/api/v1/site/faq", signal),
  });
}
