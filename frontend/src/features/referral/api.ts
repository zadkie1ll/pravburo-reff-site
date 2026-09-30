import { useMutation, useQuery } from "@tanstack/react-query";

import { apiGet, apiPost } from "@/shared/api/client";

import type { ReferralFormInfo, ReferralSubmission } from "./types";

const referralUrl = (code: string) => `/api/v1/site/referral/${code}`;

/**
 * Loading the form is what counts a visit of the partner's link on the server, so it must
 * happen once per page view: never refetch on mount or focus.
 */
export function useReferralForm(code: string) {
  return useQuery({
    queryKey: ["referral", code],
    queryFn: ({ signal }) => apiGet<ReferralFormInfo>(referralUrl(code), signal),
    staleTime: Infinity,
    refetchOnMount: false,
    retry: false,
  });
}

export function useSubmitReferral(code: string) {
  return useMutation({
    mutationFn: (body: ReferralSubmission) => apiPost<{ ok: boolean }>(referralUrl(code), body),
  });
}
