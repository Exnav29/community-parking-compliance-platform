// SPDX-License-Identifier: Apache-2.0
import { useCallback, useEffect, useMemo, useState } from "react";
import { Big, Screen } from "./components/ui";
import { FrappeClient, type OrgContext } from "./lib/api";
import { secureStore } from "./lib/device";
import { OfflineQueue } from "./lib/queue";
import { timings, uuid, type Ctx, type EstateCtx, type Me, type Screen as ScreenName } from "./lib/types";
import { useOnline } from "./lib/useOnline";
import { CheckIn, CheckOut, FindVehicle } from "./screens/Gate";
import { Concern, MyReports } from "./screens/Resident";
import { Case, Cases, Queue, Verify } from "./screens/Security";
import "./styles.css";

const lastOrg = () => { try { return JSON.parse(localStorage.getItem("cpcp.lastOrg") ?? "{}") as Partial<OrgContext>; } catch { return {}; } };

export default function App() {
  const [org, setOrg] = useState<OrgContext | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [estate, setEstate] = useState<EstateCtx | null>(null);
  const [screen, setScreen] = useState<ScreenName>("home");
  const [arg, setArg] = useState<string>("");
  const [msg, setMsg] = useState("");
  const [gate, setGate] = useState("");
  const online = useOnline();
  const client = useMemo(() => (org ? new FrappeClient(org) : null), [org]);
  const queue = useMemo(() => { const s = secureStore(); return org && s ? new OfflineQueue(s, org.orgId) : null; }, [org]);
  const toast = useCallback((m: string) => { setMsg(m); window.setTimeout(() => setMsg((cur) => (cur === m ? "" : cur)), 8000); }, []);

  // Send provisional drafts when the connection returns. Each draft carries its own client UUID so a retry never duplicates.
  useEffect(() => {
    if (!online || !queue || !client || !estate) return;
    queue.flush(async (d) => {
      try {
        if (d.kind === "visitor_check_in") await client.post("visitors.check_in_visitor", { ...d.payload, client_uuid: d.clientUuid, observed_at: d.observedAt });
        else if (d.kind === "visitor_check_out") await client.post("visitors.check_out_visitor", { ...d.payload, client_uuid: d.clientUuid, observed_at: d.observedAt });
        return {};
      } catch (e) {
        const m = (e as Error).message || "";
        if (/Already (inside|checked out)/.test(m)) return { conflict: true };
        throw e;
      }
    }).then((r) => { if (r.synced || r.review) toast(`Synced ${r.synced} saved item(s)${r.review ? `, ${r.review} need review` : ""}.`); });
  }, [online, queue, client, estate, toast]);

  const signOut = useCallback(async () => {
    await queue?.wipe();
    try { await client?.logout(); } catch { /* local state is cleared regardless */ }
    setMe(null); setOrg(null); setEstate(null); setScreen("home");
  }, [client, queue]);

  if (!client || !me || !estate) return <Connect onReady={(o, m, e) => { setOrg(o); setMe(m); setEstate(e); setGate(localStorage.getItem("cpcp.gate") ?? e.gates[0]?.name ?? ""); }} />;

  const ctx: Ctx = {
    client, me, estate, queue, online, toast, gate,
    go: (s, a) => { setScreen(s); setArg(a ?? ""); },
    setGate: (g) => { setGate(g); try { localStorage.setItem("cpcp.gate", g); } catch { /* ignore */ } },
  };
  const nav = (cap: string) => me.navigation.includes(cap);
  const resident = me.active_role === "resident";
  const staff = !resident && me.active_role !== "auditor";

  return (
    <main>
      <header>
        <div><h1>{me.display_name}</h1><small>{me.active_role.replace("_", " ")} - {estate.name}</small></div>
        <span className={`dot ${online ? "on" : "off"}`} role="status">{online ? "Online" : "Offline"}</span>
      </header>
      {msg && <p role="status" className="notice" onClick={() => setMsg("")}>{msg}</p>}
      {screen === "home" && (
        <nav className="grid" aria-label="Main actions">
          {staff && nav("visitor_log") && <>
            <Big icon="IN" label="Check In" hint="Unit first, 3 taps" onClick={() => ctx.go("checkin")} />
            <Big icon="OUT" label="Check Out" hint="Visitors inside" onClick={() => ctx.go("checkout")} />
            <Big icon="?" label="Find Vehicle" onClick={() => ctx.go("find")} />
          </>}
          {staff && nav("triage_reports") && <Big icon="!" label="Resident Reports" hint="Claim, check, verify" onClick={() => ctx.go("queue")} />}
          {staff && nav("verify_incident") && <Big icon="#" label="Active Cases" hint="Contact, warning clock" onClick={() => ctx.go("cases")} />}
          {resident && <>
            <Big icon="+" label="Report a concern" hint="Not a fine - security checks first" onClick={() => ctx.go("concern")} />
            <Big icon="=" label="My reports and estate summary" onClick={() => ctx.go("report")} />
          </>}
          <Big icon="i" label="Settings and help" onClick={() => ctx.go("settings")} />
        </nav>
      )}
      {screen === "checkin" && <CheckIn c={ctx} />}
      {screen === "checkout" && <CheckOut c={ctx} />}
      {screen === "find" && <FindVehicle c={ctx} />}
      {screen === "queue" && <Queue c={ctx} />}
      {screen === "verify" && <Verify c={ctx} allegation={arg} />}
      {screen === "cases" && <Cases c={ctx} />}
      {screen === "case" && <Case c={ctx} incident={arg} />}
      {screen === "concern" && <Concern c={ctx} />}
      {screen === "report" && <MyReports c={ctx} />}
      {screen === "settings" && <Settings c={ctx} onSignOut={signOut} />}
    </main>
  );
}

function Settings({ c, onSignOut }: { c: Ctx; onSignOut: () => void }) {
  const [pending, setPending] = useState<number | null>(null);
  useEffect(() => { c.queue?.list().then((l) => setPending(l.filter((d) => d.state !== "Synced").length)); }, [c.queue]);
  const t = timings("checkin");
  return (
    <Screen title="Settings and help" onBack={() => c.go("home")}>
      {c.estate.gates.length > 1 && <label>My gate
        <select value={c.gate} onChange={(e) => c.setGate(e.target.value)}>{c.estate.gates.map((g) => <option key={g.name} value={g.name}>{g.gate_name}</option>)}</select></label>}
      <p>Saved offline, not yet sent: {c.queue ? pending ?? "..." : "offline saving is available in the installed app only"}</p>
      <p>Check-in speed on this phone: {t.n ? `${t.medianSec} s typical (last ${t.n})` : "no data yet"}. Target: 20 s or less.</p>
      <p className="hint">Camera is used only when you tap Take photo. Location is read once, only when you tap Capture location. Nothing is tracked in the background.</p>
      <p className="hint">Fines, clamping, towing and payments are off unless your association has enabled them with legal approval.</p>
      <Big icon="X" label="Sign out" hint="Removes saved offline items from this phone" onClick={onSignOut} />
    </Screen>
  );
}

function Connect({ onReady }: { onReady: (o: OrgContext, m: Me, e: EstateCtx) => void }) {
  const saved = lastOrg();
  const [url, setUrl] = useState(saved.baseUrl ?? "https://");
  const [orgId, setOrgId] = useState(saved.orgId ?? "");
  const [usr, setUsr] = useState("");
  const [pwd, setPwd] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function go(e: React.FormEvent) {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      const o = { orgId: orgId.trim(), baseUrl: url.trim().replace(/\/$/, "") };
      const cl = new FrappeClient(o);
      await cl.login(usr.trim(), pwd);
      const me = (await cl.whoami()) as Me;
      if (me.organization !== o.orgId) { await cl.logout().catch(() => undefined); throw new Error("Organization code does not match this server"); }
      const ctxs = (await cl.get("ops.estate_context")) as EstateCtx[];
      if (!ctxs.length) throw new Error("No estate is assigned to your account");
      try { localStorage.setItem("cpcp.lastOrg", JSON.stringify(o)); } catch { /* ignore */ }
      onReady(o, me, ctxs[0]);
    } catch (x) { setErr(x instanceof Error ? x.message : "Sign-in failed"); } finally { setBusy(false); }
  }
  return (
    <main>
      <h1>Community Parking &amp; Compliance</h1>
      <form onSubmit={go}>
        <label>Association code<input value={orgId} onChange={(e) => setOrgId(e.target.value)} autoCapitalize="none" autoCorrect="off" required /></label>
        <label>Server address<input value={url} onChange={(e) => setUrl(e.target.value)} inputMode="url" autoCapitalize="none" required /></label>
        <label>Email<input value={usr} onChange={(e) => setUsr(e.target.value)} inputMode="email" autoCapitalize="none" autoComplete="username" required /></label>
        <label>Password<input type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} autoComplete="current-password" required /></label>
        <Big icon="->" label={busy ? "Signing in..." : "Sign in"} onClick={() => undefined} disabled={busy} />
        <button type="submit" hidden />
        {err && <p role="alert" className="error">{err}</p>}
      </form>
      <p className="hint">For invited users only. Demo and test builds use synthetic data.</p>
    </main>
  );
}

export { uuid };
