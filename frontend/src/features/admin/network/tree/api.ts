import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiGet } from "@/shared/api/client";

import type { NetworkTreeResponse } from "./types";

export interface TreeQuery {
  q: string;
  root: number | null;
}

export function useNetworkTree({ q, root }: TreeQuery) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (root !== null) params.set("root", String(root));
  const search = params.toString();
  return useQuery({
    queryKey: ["admin", "network", "tree", search],
    queryFn: ({ signal }) =>
      apiGet<NetworkTreeResponse>(
        `/api/v1/site/admin/network/tree${search ? `?${search}` : ""}`,
        signal,
      ),
    placeholderData: keepPreviousData,
  });
}
