import type { CapacitorConfig } from "@capacitor/cli";

// Provisional reverse-domain ID: replace once the owner controls the final domain (PRD 54).
const config: CapacitorConfig = {
  appId: "invalid.cpcp.mobile",
  appName: "CPCP",
  webDir: "dist",
  server: { androidScheme: "https" },
};
export default config;
