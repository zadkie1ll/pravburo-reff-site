export interface Option {
  value: string;
  label: string;
}

export interface PayoutRow {
  payout_date_label: string;
  client_name: string;
  type_label: string;
  amount_label: string;
  status_label: string;
  status_slug: string;
  rejection_reason: string;
}

export interface Payouts {
  rows: PayoutRow[];
  reward_types: Option[];
  statuses: Option[];
}

export interface PayoutFilters {
  month: string;
  reward_type: string;
  status: string;
}
