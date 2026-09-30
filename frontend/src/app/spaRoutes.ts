/**
 * Routes already served by React. Keep in sync with SPA_PATHS and SPA_PATH_TEMPLATES in
 * src/web/routes/spa.py (a backend test compares them). Links to any other path are full page
 * loads because those pages are still rendered by the backend.
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
  "/admin/partners",
  "/admin/network/rates",
  "/admin/network/tree",
  "/admin/faq",
  "/admin/payouts",
  "/admin/2fa/setup",
  "/admin/2fa/verify",
];

/** Routes with parameters (React Router syntax). Nothing inside the app links to them. */
export const SPA_PATH_PATTERNS: readonly string[] = [
  "/r/:referralCode",
  "/r/:referralCode/success",
];

export function isSpaPath(path: string): boolean {
  return SPA_PATHS.includes(path);
}
