export type EmploymentFormat = "self_employed" | "individual_entrepreneur" | "individual";

export interface FormatOption {
  value: EmploymentFormat;
  title: string;
  text: string;
}

export interface OnboardingOptions {
  options: FormatOption[];
  telegram_manager_url: string;
}

export interface OnboardingRequest {
  employment_format: EmploymentFormat;
  display_name: string;
  payout_details: string;
  inn: string;
}
