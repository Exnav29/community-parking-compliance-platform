// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";
import { FrappeClient } from "./api";
import { accuracyTier, normalizePlate } from "./plate";
import { OfflineQueue, type KeyValueStore } from "./queue";

function memStore(): KeyValueStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    get: async (k) => data.get(k) ?? null,
    set: async (k, v) => void data.set(k, v),
    remove: async (k) => void data.delete(k),
  };
}

describe("plate + accuracy", () => {
  it("normalizes like the server", () => {
    expect(normalizePlate("gr 1234-25")).toBe("GR123425");
    expect(() => normalizePlate("!")).toThrow();
  });
  it("tiers accuracy without claiming vehicle position", () => {
    expect(accuracyTier(10)).toBe("high");
    expect(accuracyTier(60)).toBe("approximate");
    expect(accuracyTier(200)).toBe("low");
    expect(accuracyTier(null)).toBe("unknown");
  });
});

describe("offline queue (AC-16, AC-30, AC-88)", () => {
  it("keeps drafts provisional and per-organization", async () => {
    const s = memStore();
    const a = new OfflineQueue(s, "org-a");
    const b = new OfflineQueue(s, "org-b");
    await a.enqueue("visitor_check_in", { plate: "AB12" });
    expect((await a.list())[0].state).toBe("Pending Sync");
    expect(await b.list()).toEqual([]);
  });
  it("refuses enforcement, payment and release offline", async () => {
    const q = new OfflineQueue(memStore(), "org-a");
    for (const k of ["clamp_vehicle", "tow_dispatch", "payment_collect", "release_vehicle", "fine_issue", "unknown_kind"]) {
      await expect(q.enqueue(k, {})).rejects.toThrow();
    }
  });
  it("uploads exactly once and marks conflicts for review", async () => {
    const q = new OfflineQueue(memStore(), "org-a");
    await q.enqueue("visitor_check_in", { plate: "AB12" });
    await q.enqueue("visitor_check_out", { session: "S1" });
    const seen: string[] = [];
    const send = async (d: { clientUuid: string; kind: string }) => {
      seen.push(d.clientUuid);
      return { conflict: d.kind === "visitor_check_out" };
    };
    expect(await q.flush(send)).toEqual({ synced: 1, review: 1, failed: 0 });
    expect(await q.flush(send)).toEqual({ synced: 0, review: 0, failed: 0 }); // second pass sends nothing
    expect(seen.length).toBe(2);
  });
  it("retries failures without duplicating", async () => {
    const q = new OfflineQueue(memStore(), "org-a");
    await q.enqueue("incident_draft", { note: "x" });
    let calls = 0;
    const flaky = async () => {
      if (++calls === 1) throw new Error("offline");
      return {};
    };
    expect((await q.flush(flaky)).failed).toBe(1);
    expect((await q.flush(flaky)).synced).toBe(1);
    expect((await q.list()).length).toBe(1);
  });
  it("wipe removes the old organization's data on logout/switch", async () => {
    const s = memStore();
    const q = new OfflineQueue(s, "org-a");
    await q.enqueue("visitor_check_in", { plate: "AB12" });
    await q.wipe();
    expect(s.data.size).toBe(0);
  });
});

describe("api client", () => {
  it("rejects non-HTTPS organization URLs outside local dev", () => {
    expect(() => new FrappeClient({ orgId: "x", baseUrl: "http://evil.example" })).toThrow();
    expect(() => new FrappeClient({ orgId: "x", baseUrl: "https://org.example" })).not.toThrow();
  });
  it("anonymous submission omits credentials and referrer", async () => {
    let init: RequestInit | undefined;
    const fake = (async (_u: string, i?: RequestInit) => {
      init = i;
      return new Response(JSON.stringify({ message: { ok: 1 } }), { status: 200 });
    }) as unknown as typeof fetch;
    const c = new FrappeClient({ orgId: "x", baseUrl: "https://org.example" }, fake);
    await c.submitAnonymous({ narrative: "n" });
    expect(init?.credentials).toBe("omit");
    expect(init?.referrerPolicy).toBe("no-referrer");
    await c.post("registry.lookup_plate", {});
    expect(init?.credentials).toBe("include");
  });
});
