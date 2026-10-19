// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";
import { pagesFor } from "./nav";
import type { Me } from "./api";

const me = (role: string, navigation: string[]): Me => ({ organization: "o", display_name: "O", active_role: role, roles_held: [role], estates: ["E1"], navigation, anonymous_label: "Confidential", enforcement_gates: {} });
const keys = (m: Me) => pagesFor(m).map((p) => p.key);

describe("console navigation follows the server manifest (hiding is a convenience, not security)", () => {
  it("officers and residents get no console pages", () => {
    expect(keys(me("security_officer", ["gate_operations", "triage_reports", "incident_reports", "aggregate_dashboards"]))).toEqual(["overview"]);
    expect(keys(me("resident", ["submit_report", "aggregate_dashboards"]))).toEqual([]);
  });
  it("auditors see overview and access review, never registry or staff pages", () => {
    const k = keys(me("auditor", ["aggregate_dashboards", "access_review", "audit_history"]));
    expect(k).toEqual(["overview", "access"]);
  });
  it("security managers get cases, map, registry and access review but not policy editing", () => {
    const k = keys(me("security_manager", ["aggregate_dashboards", "triage_reports", "incident_reports", "resident_registry", "manage_users", "access_review"]));
    expect(k).toEqual(expect.arrayContaining(["overview", "cases", "map", "registry", "staff", "access"]));
    expect(k).not.toContain("policies");
  });
  it("organization admins get every page", () => {
    const k = keys(me("org_admin", ["aggregate_dashboards", "triage_reports", "incident_reports", "resident_registry", "manage_users", "change_policy", "access_review"]));
    expect(k).toEqual(["overview", "cases", "map", "registry", "staff", "policies", "access"]);
  });
});
