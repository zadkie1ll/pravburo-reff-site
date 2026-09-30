export type ProcessingStatus = "new" | "in_progress" | "closed";

export interface Option {
  value: string;
  label: string;
}

export interface Manager {
  id: number;
  label: string;
}

export interface Application {
  id: number;
  client_name: string;
  phone: string;
  agent_name: string;
  agent_email: string | null;
  city: string | null;
  debt_amount: string | null;
  delivery_label: string;
  delivery_error: string | null;
  processing_status: ProcessingStatus;
  assigned_manager_id: number | null;
  created_at_label: string;
}

export interface ApplicationsList {
  rows: Application[];
  page: number;
  total_pages: number;
  total_count: number;
  delivery_statuses: Option[];
  processing_statuses: Option[];
  managers: Manager[];
}
