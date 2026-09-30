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
