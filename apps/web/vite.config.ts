import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Production build is served by Frappe itself from /assets/frappe_cpcp/web/ so the session cookie is same-origin.
// `npm run dev` proxies the API to the local dev server and picks the organization with the Host header.
const DEV_ORG_HOST = process.env.CPCP_DEV_HOST ?? "org-a.localhost";

export default defineConfig({
  base: "/assets/frappe_cpcp/web/",
  plugins: [react()],
  build: { outDir: "../frappe_cpcp/frappe_cpcp/public/web", emptyOutDir: true },
  server: {
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false, headers: { Host: DEV_ORG_HOST } } },
  },
});
