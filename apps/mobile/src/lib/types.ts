// SPDX-License-Identifier: Apache-2.0
import type { FrappeClient } from "./api";
import type { OfflineQueue } from "./queue";

export interface Me {
  organization: string; display_name: string; active_role: string; roles_held: string[]; estates: string[];
  navigation: string[]; anonymous_label: string;
  enforcement_gates: Record<string, boolean>;
}
export interface EstateCtx {
  estate: string; name: string; timezone: string; currency: string;
  boundary: { coordinates: number[][][] } | null;
  gates: { name: string; gate_name: string }[];
  zones: { name: string; zone_name: string; zone_type: string }[];
}
export interface Ctx {
  client: FrappeClient;
  me: Me;
  estate: EstateCtx;
  queue: OfflineQueue | null;
  online: boolean;
  toast: (m: string) => void;
  go: (s: Screen, arg?: string) => void;
  gate: string;
  setGate: (g: string) => void;
  shift: { on_duty: boolean; gate?: string; ends_at?: string } | null;
  refreshShift: () => Promise<void>;
}
export type Screen = "home" | "shift" | "checkin" | "checkout" | "find" | "queue" | "verify" | "cases" | "case" | "report" | "concern" | "settings";

export const uuid = () => crypto.randomUUID();
export const isNetworkError = (e: unknown) => e instanceof TypeError; // fetch() rejects with TypeError when offline

/** Local, non-PII usability timings so pilots can measure "routine check-in <= 20 s" (PRD 40.3, AC-94). */
export function recordTiming(kind: string, ms: number) {
  try {
    const all = JSON.parse(localStorage.getItem("cpcp.timings") ?? "{}");
    const arr: number[] = [...(all[kind] ?? []), Math.round(ms)].slice(-20);
    localStorage.setItem("cpcp.timings", JSON.stringify({ ...all, [kind]: arr }));
  } catch { /* storage unavailable: skip */ }
}
export function timings(kind: string): { n: number; medianSec: number | null } {
  try {
    const arr: number[] = JSON.parse(localStorage.getItem("cpcp.timings") ?? "{}")[kind] ?? [];
    const s = [...arr].sort((a, b) => a - b);
    return { n: s.length, medianSec: s.length ? Math.round(s[Math.floor(s.length / 2)] / 100) / 10 : null };
  } catch { return { n: 0, medianSec: null }; }
}
