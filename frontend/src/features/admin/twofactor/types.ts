export interface TwoFactorState {
  step: "setup" | "verify";
  /** The QR image to scan while setting up; none once 2FA is on. */
  qr_url: string | null;
}
