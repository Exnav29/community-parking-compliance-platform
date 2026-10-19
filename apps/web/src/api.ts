// SPDX-License-Identifier: Apache-2.0
/**
 * Same-origin Frappe client for the management console. It carries no tenant id: the organization is the site that served the page
 * and the session cookie is bound to it. Every call is authorised by the server; this client only hides what the server would refuse.
 */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function clean(msg: unknown): string {
  const s = String(msg ?? "").replace(/<[^>]*>/g, "").replace(/^[\w.]+Error:\s*/, "");
  return s.length > 200 ? s.slice(0, 200) + "..." : s;
}

async function parse(res: Response) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 || res.status === 403) throw new ApiError(res.status, "You are not permitted to do that, or your session has ended.");
    let detail = body?._server_messages ? JSON.parse(JSON.parse(body._server_messages)[0]).message : body?.exception ?? res.statusText;
    throw new ApiError(res.status, clean(detail));
  }
  return body.message ?? body.data ?? body;
}

export const api = {
  async login(usr: string, pwd: string) {
    return parse(await fetch("/api/method/login", { method: "POST", credentials: "same-origin", body: new URLSearchParams({ usr, pwd }) }));
  },
  async logout() {
    await fetch("/api/method/logout", { method: "POST", credentials: "same-origin" }).catch(() => undefined);
  },
  async get(method: string, params: Record<string, unknown> = {}) {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));
    return parse(await fetch(`/api/method/frappe_cpcp.api.${method}?${q}`, { credentials: "same-origin" }));
  },
  async post(method: string, args: Record<string, unknown> = {}) {
    const f = new URLSearchParams();
    for (const [k, v] of Object.entries(args)) if (v !== undefined && v !== null && v !== "") f.set(k, String(v));
    return parse(await fetch(`/api/method/frappe_cpcp.api.${method}`, { method: "POST", credentials: "same-origin", body: f }));
  },
  /** Generic Frappe resource list. Server DocPerm + hooks + the request guard decide; every open by management is journaled. */
  async list(doctype: string, fields: string[], filters: Record<string, unknown> = {}, limit = 100) {
    const q = new URLSearchParams({ fields: JSON.stringify(fields), filters: JSON.stringify(filters), limit_page_length: String(limit), order_by: "modified desc" });
    return parse(await fetch(`/api/resource/${encodeURIComponent(doctype)}?${q}`, { credentials: "same-origin" })) as Promise<Record<string, unknown>[]>;
  },
  async create(doctype: string, doc: Record<string, unknown>) {
    return parse(await fetch(`/api/resource/${encodeURIComponent(doctype)}`, { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(doc) }));
  },
  async update(doctype: string, name: string, patch: Record<string, unknown>) {
    return parse(await fetch(`/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`, { method: "PUT", credentials: "same-origin",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) }));
  },
};

export interface Me {
  organization: string; display_name: string; active_role: string; roles_held: string[]; estates: string[]; navigation: string[];
  anonymous_label: string; enforcement_gates: Record<string, boolean>;
}
export interface EstateCtx { estate: string; name: string; timezone: string; currency: string; boundary: { coordinates: number[][][] } | null;
  gates: { name: string; gate_name: string }[]; zones: { name: string; zone_name: string; zone_type: string }[] }
