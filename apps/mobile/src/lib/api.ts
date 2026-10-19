// SPDX-License-Identifier: Apache-2.0
/**
 * Organization-bound Frappe API client. The base URL comes from verified organization discovery and the
 * token/cookie is held per organization in the OS keystore; nothing here trusts a client-supplied tenant id.
 * Anonymous reporting uses a separate request path with credentials omitted entirely.
 */
export interface OrgContext {
  orgId: string;
  baseUrl: string; // https://<org-site>
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export class FrappeClient {
  private org: OrgContext;
  private fetchImpl: typeof fetch;
  constructor(org: OrgContext, fetchImpl: typeof fetch = fetch.bind(globalThis)) {
    this.org = org;
    this.fetchImpl = fetchImpl;
    const lanOk = import.meta.env.VITE_ALLOW_LAN_HTTP === "1"; // set ONLY for development/test builds
    const privateHttp = /^http:\/\/(localhost|127\.0\.0\.1|10\.0\.2\.2|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?(\/|$)/;
    if (!/^https:\/\//.test(org.baseUrl) && !(privateHttp.test(org.baseUrl) && (lanOk || /localhost|127\.0\.0\.1|10\.0\.2\.2/.test(org.baseUrl)))) {
      throw new Error("Organization URL must use HTTPS (plain HTTP is only allowed for local/LAN test builds)");
    }
  }

  private async req(path: string, init: RequestInit & { anonymous?: boolean } = {}) {
    const { anonymous, ...rest } = init;
    const res = await this.fetchImpl(this.org.baseUrl + path, {
      ...rest,
      // 'omit' keeps cookies/session out of the anonymous intake request (PRD 34.2.1).
      credentials: anonymous ? "omit" : "include",
      headers: { Accept: "application/json", ...(rest.headers ?? {}) },
      referrerPolicy: "no-referrer",
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(res.status, body?.exception ?? body?.message ?? res.statusText);
    return body.message ?? body;
  }

  login(usr: string, pwd: string) {
    return this.req("/api/method/login", { method: "POST", body: new URLSearchParams({ usr, pwd }) });
  }
  logout() {
    return this.req("/api/method/logout", { method: "POST" });
  }
  whoami(roleContext?: string) {
    const q = roleContext ? `?role_context=${encodeURIComponent(roleContext)}` : "";
    return this.req(`/api/method/frappe_cpcp.api.session.whoami${q}`);
  }
  get(method: string, params: Record<string, unknown> = {}) {
    const q = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]));
    return this.req(`/api/method/frappe_cpcp.api.${method}?${q}`);
  }
  post(method: string, args: Record<string, unknown>) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(args)) if (v !== undefined && v !== null) form.set(k, String(v));
    return this.req(`/api/method/frappe_cpcp.api.${method}`, { method: "POST", body: form });
  }
  anonymousStatus(receiptId: string, secret: string) {
    const form = new URLSearchParams({ receipt_id: receiptId, secret });
    return this.req("/api/method/frappe_cpcp.api.allegations.anonymous_status", { method: "POST", body: form, anonymous: true });
  }
  /** Identity-unlinked: no cookies, no referrer, and callers must not attach any auth header. */
  submitAnonymous(args: Record<string, unknown>) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(args)) if (v !== undefined && v !== null) form.set(k, String(v));
    return this.req("/api/method/frappe_cpcp.api.allegations.submit_anonymous", { method: "POST", body: form, anonymous: true });
  }
}
