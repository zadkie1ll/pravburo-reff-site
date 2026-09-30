import { useQuery } from "@tanstack/react-query";

import { apiDelete, apiGet, apiPost, apiPut } from "@/shared/api/client";
import { useInvalidatingMutation } from "@/shared/api/useInvalidatingMutation";

import type { FaqList, MoveDirection } from "./types";

const BASE = "/api/v1/site/admin/faq";
const KEY = ["admin", "faq"] as const;

export function useAdminFaq() {
  return useQuery({
    queryKey: KEY,
    queryFn: ({ signal }) => apiGet<FaqList>(BASE, signal),
  });
}

interface Content {
  question: string;
  answer: string;
}

export function useCreateFaq() {
  return useInvalidatingMutation(KEY, (content: Content) => apiPost(BASE, content));
}

export function useUpdateFaq() {
  return useInvalidatingMutation(KEY, ({ id, ...content }: Content & { id: number }) =>
    apiPut(`${BASE}/${id}`, content),
  );
}

export function useDeleteFaq() {
  return useInvalidatingMutation(KEY, (id: number) => apiDelete(`${BASE}/${id}`));
}

export function useMoveFaq() {
  return useInvalidatingMutation(
    KEY,
    ({ id, direction }: { id: number; direction: MoveDirection }) =>
      apiPost(`${BASE}/${id}/move`, { direction }),
  );
}
