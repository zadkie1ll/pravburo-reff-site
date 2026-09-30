import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { InfoResponse } from "@/features/auth/types";
import { apiGet, apiPost } from "@/shared/api/client";

import type { EmailChangeRequest, Profile, ProfileUpdate } from "./types";

const PROFILE = "/api/v1/site/profile";
const profileKey = ["profile"] as const;

export function useProfile() {
  return useQuery({
    queryKey: profileKey,
    queryFn: ({ signal }) => apiGet<Profile>(PROFILE, signal),
  });
}

export function useUpdateProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfileUpdate) => apiPost<Profile>(PROFILE, body),
    onSuccess: (profile) => client.setQueryData(profileKey, profile),
  });
}

export function useBeginEmailChange() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: EmailChangeRequest) => apiPost<InfoResponse>(`${PROFILE}/email`, body),
    // The profile now reports the pending address, which switches the form to the code step.
    onSuccess: () => client.invalidateQueries({ queryKey: profileKey }),
  });
}

export function useConfirmEmailChange() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => apiPost<InfoResponse>(`${PROFILE}/email/confirm`, { code }),
    onSuccess: () => {
      // The e-mail changed: the profile and the session (header, password reset) are stale.
      void client.invalidateQueries({ queryKey: profileKey });
      void client.invalidateQueries({ queryKey: ["session"] });
    },
  });
}
