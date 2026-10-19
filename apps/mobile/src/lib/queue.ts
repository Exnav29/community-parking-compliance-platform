// SPDX-License-Identifier: Apache-2.0
/**
 * Offline provisional queue (PRD 14, 25.2, 44). Properties enforced here:
 *  - one namespace per organization; switching/logout wipes the previous namespace;
 *  - every item has a client UUID so retries are idempotent server-side;
 *  - records are PROVISIONAL: only non-financial check-in/check-out and incident drafts are accepted;
 *    enforcement, payment and release actions are rejected at enqueue time;
 *  - original observed time is kept separate from the time the server accepted it.
 */
export interface KeyValueStore {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
}

export type DraftKind = "visitor_check_in" | "visitor_check_out" | "incident_draft";
export type DraftState = "Pending Sync" | "Synced" | "Needs Review";

export interface Draft {
  clientUuid: string;
  kind: DraftKind;
  payload: Record<string, unknown>;
  observedAt: string; // ISO, device clock, provenance only
  state: DraftState;
  expiresAt: string;
  attempts: number;
  lastError?: string;
}

const ALLOWED: ReadonlySet<string> = new Set<DraftKind>(["visitor_check_in", "visitor_check_out", "incident_draft"]);
const FORBIDDEN_PREFIXES = ["clamp", "tow", "fine", "payment", "release", "penalty"];
// PRD v1.8: the device never stores people-directory data. Drafts hold only what the officer typed for ONE action.
const FORBIDDEN_PAYLOAD_KEYS = ["name", "full_name", "phone", "phone_e164", "email", "contacts", "residents", "members", "household", "history", "directory", "visits", "candidates"];
export const DRAFT_TTL_MS = 72 * 3600 * 1000; // unsent drafts are wiped after 72 hours

export class OfflineQueue {
  private store: KeyValueStore;
  private orgId: string;
  constructor(store: KeyValueStore, orgId: string) {
    this.store = store;
    this.orgId = orgId;
    if (!orgId) throw new Error("organization context required");
  }
  private key() {
    return `cpcp.queue.${this.orgId}`;
  }
  async list(): Promise<Draft[]> {
    const raw = await this.store.get(this.key());
    const all = raw ? (JSON.parse(raw) as Draft[]) : [];
    const live = all.filter((d) => !d.expiresAt || new Date(d.expiresAt).getTime() > Date.now());
    if (live.length !== all.length) await this.save(live); // expired drafts are removed, not kept "just in case"
    return live;
  }
  private async save(items: Draft[]) {
    await this.store.set(this.key(), JSON.stringify(items));
  }
  async enqueue(kind: string, payload: Record<string, unknown>, now = new Date()): Promise<Draft> {
    if (FORBIDDEN_PREFIXES.some((p) => kind.toLowerCase().startsWith(p)) || !ALLOWED.has(kind)) {
      throw new Error(`'${kind}' cannot be performed offline`);
    }
    const bad = Object.keys(payload).filter((k) => FORBIDDEN_PAYLOAD_KEYS.includes(k.toLowerCase()));
    if (bad.length) throw new Error(`personal or directory data cannot be stored on the device (${bad.join(", ")})`);
    const draft: Draft = {
      clientUuid: crypto.randomUUID(), kind: kind as DraftKind, payload,
      observedAt: now.toISOString(), state: "Pending Sync", attempts: 0, expiresAt: new Date(now.getTime() + DRAFT_TTL_MS).toISOString(),
    };
    await this.save([...(await this.list()), draft]);
    return draft;
  }
  /** Send pending drafts once each. `send` must be idempotent on clientUuid. */
  async flush(send: (d: Draft) => Promise<{ conflict?: boolean }>): Promise<{ synced: number; review: number; failed: number }> {
    const items = await this.list();
    let synced = 0, review = 0, failed = 0;
    for (const d of items) {
      if (d.state !== "Pending Sync") continue;
      try {
        const r = await send(d);
        d.state = r.conflict ? "Needs Review" : "Synced";
        r.conflict ? review++ : synced++;
      } catch (e) {
        d.attempts += 1;
        d.lastError = e instanceof Error ? e.message : String(e);
        failed++;
      }
    }
    await this.save(items);
    return { synced, review, failed };
  }
  async purgeSynced() {
    await this.save((await this.list()).filter((d) => d.state !== "Synced"));
  }
  /** Logout / organization switch / revoked session: nothing may survive for the old organization. */
  async wipe() {
    await this.store.remove(this.key());
  }
}
