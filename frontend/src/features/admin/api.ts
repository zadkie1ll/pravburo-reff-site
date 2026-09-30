import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/shared/api/client";

import type { AdminPanel } from "./types";

export function useAdminPanel() {
  return useQuery({
    queryKey: ["admin", "panel"],
    queryFn: ({ signal }) => apiGet<AdminPanel>("/api/v1/site/admin", signal),
  });
}
