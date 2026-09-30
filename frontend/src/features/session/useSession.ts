import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/shared/api/client";
import { setCsrfToken } from "@/shared/api/csrf";

import type { SessionInfo } from "./types";

export const sessionQueryKey = ["session"] as const;

async function fetchSession(signal: AbortSignal): Promise<SessionInfo> {
  const session = await apiGet<SessionInfo>("/api/v1/site/me", signal);
  setCsrfToken(session.csrf_token);
  return session;
}

export function useSession() {
  return useQuery({
    queryKey: sessionQueryKey,
    queryFn: ({ signal }) => fetchSession(signal),
    staleTime: 60_000,
  });
}
