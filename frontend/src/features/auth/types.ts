export interface AuthConfig {
  telegram_bot_username: string;
  telegram_auth_url: string;
  yandex_enabled: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  password_repeat: string;
  display_name: string;
  employment_format: "self_employed" | "individual_entrepreneur" | "individual";
  payout_details: string;
  inn: string;
}

export interface PasswordResetConfirmRequest {
  code: string;
  password: string;
  password_repeat: string;
}

/** Where the browser goes after the session has been started. */
export interface NextResponse {
  next: string;
}

export interface InfoResponse {
  info: string;
}
