import { useMutation, useQuery } from "@tanstack/react-query";

import { goNext } from "@/features/auth/api";
import type { NextResponse } from "@/features/auth/types";
import { apiGet, apiPost } from "@/shared/api/client";

import type { TwoFactorState } from "./types";

const BASE = "/api/v1/site/admin/2fa";

export function useTwoFactorState() {
  return useQuery({
    queryKey: ["admin", "2fa", "state"],
    queryFn: ({ signal }) => apiGet<TwoFactorState>(`${BASE}/state`, signal),
    retry: false,
    // Nothing here is worth reusing: the step changes as soon as a code is accepted.
    staleTime: 0,
    gcTime: 0,
  });
}

export function useSubmitCode(step: TwoFactorState["step"]) {
  return useMutation({
    mutationFn: (code: string) => apiPost<NextResponse>(`${BASE}/${step}`, { code }),
    // The session just changed (pending -> logged in): load the panel from scratch.
    onSuccess: goNext,
  });
}
