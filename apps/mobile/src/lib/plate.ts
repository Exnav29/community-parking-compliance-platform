// SPDX-License-Identifier: Apache-2.0
/** Mirrors the server's plate normalization (frappe_cpcp.core.plates). The server stays authoritative. */
export function normalizePlate(raw: string): string {
  const v = raw.toUpperCase().replace(/[\s\-_.·]+/g, "");
  if (!/^[A-Z0-9]{2,12}$/.test(v)) throw new Error("Plate must be 2-12 letters/digits");
  return v;
}

export type AccuracyTier = "high" | "approximate" | "low" | "unknown";

/** Illustrative, configurable UX thresholds; NOT a guarantee of vehicle position (PRD 7). */
export function accuracyTier(accuracyM: number | null | undefined, high = 25, approx = 75): AccuracyTier {
  if (accuracyM == null || accuracyM < 0) return "unknown";
  if (accuracyM <= high) return "high";
  if (accuracyM <= approx) return "approximate";
  return "low";
}

export const TIER_LABEL: Record<AccuracyTier, string> = {
  high: "High accuracy",
  approximate: "Approximate",
  low: "Low accuracy - confirm location",
  unknown: "Accuracy unknown",
};
