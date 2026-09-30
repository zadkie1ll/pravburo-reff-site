export interface PendingGroup {
  label: string;
  amount_label: string;
}

export interface Finance {
  total_paid_label: string;
  this_month_label: string;
  pending_total_label: string;
  pending_groups: PendingGroup[];
}

export interface LinkStats {
  visits: number;
  applications: number;
  contracts: number;
  conversion_rate_label: string;
}

export interface LevelNode {
  level: string;
  label: string;
  range_label: string;
  is_reached: boolean;
  is_current: boolean;
}

export interface Level {
  level: string;
  label: string;
  contracts_count: number;
  contracts_word: string;
  is_manual: boolean;
  nodes: LevelNode[];
  /** Fill of the segment between node i and i+1, percent, quantized to 10. */
  segment_fills: number[];
  next_level_label: string | null;
  contracts_to_next: number | null;
  contracts_to_next_word: string | null;
}

export interface ClientRow {
  client_name: string;
  masked_phone: string;
  created_at_label: string;
  stage: string;
  reward_summary: string;
  reward_totals: string;
}

export interface Cabinet {
  name: string;
  referral_url: string;
  finance: Finance;
  link_stats: LinkStats;
  level: Level;
  clients: ClientRow[];
}

export interface VisitDay {
  day_label: string;
  count: number;
}

export interface Visits {
  days: VisitDay[];
  total: number;
}

export interface ApplicationRow {
  client_name: string;
  masked_phone: string;
  created_at_label: string;
  status: string;
}

export interface Applications {
  rows: ApplicationRow[];
}
