import { useMutation, useQuery } from "@tanstack/react-query";

import type { NextResponse } from "@/features/auth/types";
import { apiGet, apiPost } from "@/shared/api/client";

import type { OnboardingOptions, OnboardingRequest } from "./types";

const ONBOARDING = "/api/v1/site/onboarding";

export function useOnboardingOptions() {
  return useQuery({
    queryKey: ["onboarding"],
    queryFn: ({ signal }) => apiGet<OnboardingOptions>(ONBOARDING, signal),
  });
}

export function useChooseFormat() {
  return useMutation({
    mutationFn: (body: OnboardingRequest) => apiPost<NextResponse>(ONBOARDING, body),
    // The cabinet is still a backend page: full load so it sees the saved format.
    onSuccess: ({ next }) => window.location.assign(next),
  });
}
