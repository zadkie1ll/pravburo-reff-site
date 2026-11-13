import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/shared/api/client";

export interface ExistingClient {
  id: number;
  agent_id: number;
  agent_name: string;
  agent_email: string | null;
  full_name: string;
  phone: string | null;
  bitrix_deal_id: string;
  bitrix_deal_url?: string;
  stage_label: string;
  current_amount: string | null;
  current_status: string | null;
  admin_note: string | null;
  created_at_label: string;
}

export interface ClientsList {
  rows: ExistingClient[];
  page: number;
  total_pages: number;
  total_count: number;
}

export interface ClientInput {
  agent_id: number;
  deal_id: string;
  full_name: string;
  phone: string;
  admin_note: string;
  current_amount: string | null;
}

export interface DealSnapshot {
  deal_id: string;
  deal_url?: string;
  full_name: string;
  phone: string | null;
  stage_code: string;
  stage_label: string;
  category_id: number;
  first_payment: string | null;
  paid_in_full: boolean;
}

export interface BitrixCandidate {
  kind: "deal" | "lead";
  id: number;
  title: string;
  full_name: string;
  phone: string | null;
  category_id: number | null;
  category_label: string;
  stage_code: string;
  stage_label: string;
  url: string;
}

export interface BitrixSearchResults {
  rows: BitrixCandidate[];
  has_more: boolean;
  page: number;
}

/** Validate locally; the API verifies the portal host before reading a deal. */
export function parseDealReference(value: string): string | null {
  const reference = value.trim();
  if (/^[1-9]\d*$/.test(reference)) return reference;
  try {
    const url = new URL(reference);
    if (url.protocol !== "https:" && url.protocol !== "http:") return null;
    if (url.username || url.password) return null;
    return /^\/crm\/deal\/details\/([1-9]\d*)\/?$/.exec(url.pathname)?.[1] ?? null;
  } catch {
    return null;
  }
}

export interface ClientFilters {
  q: string;
  agentId: number | null;
  page: number;
}

export function positiveId(value: string | null): number | null {
  const id = Number(value);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

export function clientsSearch({ q, agentId, page }: ClientFilters): string {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (agentId !== null) params.set("agent_id", String(agentId));
  if (page > 1) params.set("page", String(page));
  return params.size ? `?${params}` : "";
}

const BASE = "/api/v1/site/admin/clients";
const KEY = ["admin", "clients"] as const;

export function useClients(filters: ClientFilters) {
  const search = clientsSearch(filters);
  return useQuery({
    queryKey: [...KEY, search],
    queryFn: ({ signal }) => apiGet<ClientsList>(`${BASE}${search}`, signal),
    placeholderData: keepPreviousData,
  });
}

export function useFindDeal() {
  return useMutation({
    mutationFn: (reference: string) => {
      const value = reference.trim();
      return apiGet<DealSnapshot>(
        /^[1-9]\d*$/.test(value)
          ? `${BASE}/deals/${encodeURIComponent(value)}`
          : `${BASE}/deals/preview?${new URLSearchParams({ deal: value })}`,
      );
    },
  });
}

export function useSearchBitrixClients() {
  return useMutation({
    mutationFn: ({ q, page }: { q: string; page: number }) =>
      apiGet<BitrixSearchResults>(
        `${BASE}/search?${new URLSearchParams({ q, page: String(page) })}`,
      ),
  });
}

export function useAddClient() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ClientInput) => apiPost<ExistingClient>(BASE, body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: KEY });
      void client.invalidateQueries({ queryKey: ["admin", "partners"] });
    },
  });
}
