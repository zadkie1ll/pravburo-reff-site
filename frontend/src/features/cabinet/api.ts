import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/shared/api/client";

import type { Applications, Cabinet, Visits } from "./types";

export function useCabinet() {
  return useQuery({
    queryKey: ["cabinet"],
    queryFn: ({ signal }) => apiGet<Cabinet>("/api/v1/site/cabinet", signal),
  });
}

export function useVisits() {
  return useQuery({
    queryKey: ["cabinet", "visits"],
    queryFn: ({ signal }) => apiGet<Visits>("/api/v1/site/cabinet/visits", signal),
  });
}

export function useApplications() {
  return useQuery({
    queryKey: ["cabinet", "applications"],
    queryFn: ({ signal }) => apiGet<Applications>("/api/v1/site/cabinet/applications", signal),
  });
}
