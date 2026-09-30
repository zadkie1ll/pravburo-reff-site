export interface ReferralFormInfo {
  turnstile_site_key: string;
}

export interface ReferralSubmission {
  full_name: string;
  phone: string;
  preferred_call_time_msk: string;
  city: string;
  debt_amount: string;
  situation: string;
  website: string;
  turnstile_token: string;
}
