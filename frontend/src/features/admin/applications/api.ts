import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiGet, apiPost } from "@/shared/api/client";
import { useInvalidatingMutation } from "@/shared/api/useInvalidatingMutation";

import { filtersToSearch, type ListFilters } from "../list/listFilters";
import type { ApplicationsList, ProcessingStatus } from "./types";

const BASE = "/api/v1/site/admin/applications";
const KEY = ["admin", "applications"] as const;

export function useApplications(filters: ListFilters) {
  const search = filtersToSearch(filters);
  return useQuery({
    queryKey: [...KEY, search],
    queryFn: ({ signal }) => apiGet<ApplicationsList>(`${BASE}${search}`, signal),
    placeholderData: keepPreviousData,
  });
}

export function useSetProcessingStatus() {
  return useInvalidatingMutation(KEY, ({ id, value }: { id: number; value: ProcessingStatus }) =>
    apiPost(`${BASE}/${id}/status`, { processing_status: value }),
  );
}

export function useSetManager() {
  return useInvalidatingMutation(KEY, ({ id, value }: { id: number; value: number | null }) =>
    apiPost(`${BASE}/${id}/manager`, { manager_id: value }),
  );
}
