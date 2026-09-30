import type { EmploymentFormat } from "@/features/onboarding/types";

export interface FormatOption {
  value: EmploymentFormat;
  label: string;
}

export interface Profile {
  display_name: string;
  email: string | null;
  phone: string | null;
  employment_format: EmploymentFormat | null;
  payout_details: string | null;
  inn: string | null;
  registered_at_label: string;
  is_active: boolean;
  is_admin: boolean;
  /** New address waiting for its confirmation code, or "". */
  pending_email: string;
  yandex_enabled: boolean;
  yandex_linked: boolean;
  employment_formats: FormatOption[];
}

export interface ProfileUpdate {
  display_name: string;
  phone: string;
  employment_format: EmploymentFormat;
  payout_details: string;
  inn: string;
}

export interface EmailChangeRequest {
  new_email: string;
  current_password: string;
}
