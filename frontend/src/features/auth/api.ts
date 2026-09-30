import { useMutation, useQuery } from "@tanstack/react-query";

import { apiGet, apiPost } from "@/shared/api/client";

import type {
  AuthConfig,
  InfoResponse,
  LoginRequest,
  NextResponse,
  PasswordResetConfirmRequest,
  RegisterRequest,
} from "./types";

const AUTH = "/api/v1/site/auth";

export function useAuthConfig() {
  return useQuery({
    queryKey: ["auth-config"],
    queryFn: ({ signal }) => apiGet<AuthConfig>(`${AUTH}/config`, signal),
    staleTime: Infinity,
  });
}

// The next page is still rendered by the backend (or needs the fresh session): full load.
export const goNext = ({ next }: NextResponse) => window.location.assign(next);

export function useLogin() {
  return useMutation({
    mutationFn: (body: LoginRequest) => apiPost<NextResponse>(`${AUTH}/login`, body),
    onSuccess: goNext,
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: (body: RegisterRequest) => apiPost<InfoResponse>(`${AUTH}/register`, body),
  });
}

export function useConfirmRegistration() {
  return useMutation({
    mutationFn: (code: string) => apiPost<NextResponse>(`${AUTH}/register/confirm`, { code }),
    onSuccess: goNext,
  });
}

export function useRequestPasswordReset() {
  return useMutation({
    mutationFn: (email: string) => apiPost<InfoResponse>(`${AUTH}/password-reset`, { email }),
  });
}

export function useConfirmPasswordReset() {
  return useMutation({
    mutationFn: (body: PasswordResetConfirmRequest) =>
      apiPost<NextResponse>(`${AUTH}/password-reset/confirm`, body),
    onSuccess: goNext,
  });
}

export function useLogout() {
  return useMutation({
    mutationFn: () => apiPost<NextResponse>(`${AUTH}/logout`),
    onSuccess: goNext,
  });
}
