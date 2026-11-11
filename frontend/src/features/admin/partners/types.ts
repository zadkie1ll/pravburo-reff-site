export interface Partner {
  id: number;
  display_name: string;
  email: string | null;
  phone: string | null;
  is_active: boolean;
  is_admin: boolean;
  blocked_reason: string | null;
  client_count: number;
  total_paid: string;
  payout_details: string | null;
  admin_note: string | null;
}

export interface PartnersList {
  rows: Partner[];
  page: number;
  total_pages: number;
  total_count: number;
  statuses: { value: string; label: string }[];
}

export type EmploymentFormat = "self_employed" | "individual_entrepreneur" | "individual";

export interface PartnerDetails {
  id: number;
  display_name: string;
  email: string | null;
  phone: string | null;
  employment_format: EmploymentFormat | null;
  payout_details: string | null;
  inn: string | null;
  admin_note: string | null;
  is_admin: boolean;
}

export interface PartnerProfileInput {
  display_name: string;
  phone: string;
  employment_format: EmploymentFormat;
  payout_details: string;
  inn: string;
  admin_note: string;
}
