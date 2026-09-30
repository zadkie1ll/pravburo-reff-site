export type Role = "admin" | "agent";

export interface SessionInfo {
  authenticated: boolean;
  email: string | null;
  role: Role | null;
  onboarding_required: boolean;
  csrf_token: string;
}
