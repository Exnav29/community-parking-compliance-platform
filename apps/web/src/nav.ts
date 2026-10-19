// SPDX-License-Identifier: Apache-2.0
import type { Me } from "./api";

export type PageKey = "overview" | "cases" | "map" | "registry" | "staff" | "policies" | "access";

/** Navigation comes from the server's manifest for this person. Hiding a page is a convenience only: every API re-checks. */
export function pagesFor(me: Me): { key: PageKey; label: string }[] {
  const nav = new Set(me.navigation);
  const r = me.active_role;
  const manager = ["org_admin", "estate_manager", "security_manager"].includes(r);
  const out: { key: PageKey; label: string }[] = [];
  if (nav.has("aggregate_dashboards") && r !== "resident") out.push({ key: "overview", label: "Overview" });
  if (manager && (nav.has("triage_reports") || nav.has("incident_reports"))) out.push({ key: "cases", label: "Cases and reports" });
  if (manager && nav.has("incident_reports")) out.push({ key: "map", label: "Map" });
  if (manager && nav.has("resident_registry")) out.push({ key: "registry", label: "Residents, units, vehicles" });
  if (manager && nav.has("manage_users")) out.push({ key: "staff", label: "Staff and devices" });
  if (manager && nav.has("change_policy") || r === "org_admin") out.push({ key: "policies", label: "Policies" });
  if (nav.has("access_review")) out.push({ key: "access", label: "Access review" });
  return out;
}

