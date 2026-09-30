import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Backend the dev server proxies API and not-yet-migrated pages to.
const backend = process.env.VITE_BACKEND_URL ?? "http://127.0.0.1:8040";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    outDir: "dist",
    // CSP allows only 'self' for images/fonts: no data: URIs, so never inline assets.
    assetsInlineLimit: 0,
  },
  server: {
    port: 5173,
    // Everything the backend serves itself: the API, static files, files that need the session
    // (QR, PDF), push, the Telegram/Yandex sign-in legs and the service worker.
    // Page routes are React's, so Vite answers those.
    proxy: {
      "^/(api|static|health|push|auth|sw\\.js|cabinet/referral-qr\\.png|payouts/export\\.pdf|admin/2fa/qr\\.png)":
        backend,
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: false,
  },
});
