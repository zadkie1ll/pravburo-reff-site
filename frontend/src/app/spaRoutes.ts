/**
 * Every page of the site is a React route. Keep in sync with SPA_PATHS and SPA_PATH_TEMPLATES in
 * src/web/routes/spa.py (a backend test compares them). Links to any other path (the API, the
 * backend's own endpoints such as the QR code or the PDF export) are full page loads.
 */
export const SPA_PATHS: readonly string[] = [
  "/",
  "/faq",
  "/login",
  "/register",
  "/register/confirm",
  "/password/reset",
  "/password/reset/confirm",
  "/onboarding",
  "/cabinet",
  "/cabinet/visits",
  "/cabinet/applications",
  "/payouts",
  "/profile",
  "/admin",
  "/admin/applications",
  "/admin/clients",
  "/admin/clients/new",
  "/admin/partners",
  "/admin/partners/new",
  "/admin/network/rates",
  "/admin/network/tree",
  "/admin/faq",
  "/admin/payouts",
  "/admin/2fa/setup",
  "/admin/2fa/verify",
];

/** Routes with parameters (React Router syntax). */
export const SPA_PATH_PATTERNS: readonly string[] = [
  "/r/:referralCode",
  "/r/:referralCode/success",
  "/admin/partners/:agentId/edit",
];

export function isSpaPath(path: string): boolean {
  const pathname = path.split(/[?#]/, 1)[0] ?? "";
  return SPA_PATHS.includes(pathname) || /^\/admin\/partners\/\d+\/edit$/.test(pathname);
}
