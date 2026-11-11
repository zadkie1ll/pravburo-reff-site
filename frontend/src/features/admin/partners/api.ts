import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPost } from "@/shared/api/client";
import { useInvalidatingMutation } from "@/shared/api/useInvalidatingMutation";

import { filtersToSearch, type ListFilters } from "../list/listFilters";
import type { PartnerDetails, PartnerProfileInput, PartnersList } from "./types";

const BASE = "/api/v1/site/admin/partners";
const KEY = ["admin", "partners"] as const;

export function usePartners(filters: ListFilters) {
  const search = filtersToSearch(filters);
  return useQuery({
    queryKey: [...KEY, search],
    queryFn: ({ signal }) => apiGet<PartnersList>(`${BASE}${search}`, signal),
    placeholderData: keepPreviousData,
  });
}

export function useSaveNote() {
  return useInvalidatingMutation(KEY, ({ id, note }: { id: number; note: string }) =>
    apiPost(`${BASE}/${id}/note`, { note }),
  );
}

export function useBlockPartner() {
  return useInvalidatingMutation(KEY, ({ id, reason }: { id: number; reason: string }) =>
    apiPost(`${BASE}/${id}/block`, { reason }),
  );
}

export function useUnblockPartner() {
  return useInvalidatingMutation(KEY, (id: number) => apiPost(`${BASE}/${id}/unblock`));
}

export function usePartner(id: number | null) {
  return useQuery({
    queryKey: [...KEY, "detail", id],
    enabled: id !== null,
    queryFn: ({ signal }) => apiGet<PartnerDetails>(`${BASE}/${id}`, signal),
  });
}

export function useSavePartner(id: number | null) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: PartnerProfileInput & { email?: string }) =>
      apiPost<PartnerDetails>(id === null ? BASE : `${BASE}/${id}`, body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: KEY });
      void client.invalidateQueries({ queryKey: ["admin", "network"] });
    },
  });
}
