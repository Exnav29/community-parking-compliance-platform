// SPDX-License-Identifier: Apache-2.0
import { useCallback, useMemo, useState } from "react";
import { FrappeClient, type OrgContext } from "./lib/api";
import { captureLocation, secureStore, takePhoto, type LocationFix } from "./lib/device";
import { accuracyTier, normalizePlate, TIER_LABEL } from "./lib/plate";
import { OfflineQueue } from "./lib/queue";
import "./styles.css";

type Me = {
  organization: string; display_name: string; active_role: string; roles_held: string[]; estates: string[];
  navigation: string[]; anonymous_label: string;
};
type Screen = "home" | "checkin" | "checkout" | "find" | "report" | "concern";

const uuid = () => crypto.randomUUID();

export default function App() {
  const [org, setOrg] = useState<OrgContext | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [screen, setScreen] = useState<Screen>("home");
  const [msg, setMsg] = useState<string>("");
  const client = useMemo(() => (org ? new FrappeClient(org) : null), [org]);
  const queue = useMemo(() => {
    const store = secureStore();
    return org && store ? new OfflineQueue(store, org.orgId) : null; // PWA fallback: no persisted drafts
  }, [org]);

  const signOut = useCallback(async () => {
    await queue?.wipe(); // nothing survives for this organization
    try { await client?.logout(); } catch { /* offline logout still clears local state */ }
    setMe(null); setOrg(null); setScreen("home");
  }, [client, queue]);

  if (!client || !me) return <Connect onReady={(o, m) => { setOrg(o); setMe(m); }} />;
  const can = (cap: string) => me.navigation.includes(cap);
  const isResident = me.active_role === "resident";

  return (
    <main>
      <header>
        <h1>{me.display_name}</h1>
        <p aria-label="role">{me.active_role.replace("_", " ")}</p>
        <button className="link" onClick={signOut}>Sign out</button>
      </header>
      {msg && <p role="status" className="notice">{msg}</p>}
      {screen === "home" && (
        <nav className="grid" aria-label="Main actions">
          {!isResident && can("visitor_log") && <>
            <Big label="Check In" hint="Unit first" onClick={() => setScreen("checkin")} />
            <Big label="Check Out" hint="Visitors inside" onClick={() => setScreen("checkout")} />
            <Big label="Find Vehicle" hint="Plate lookup" onClick={() => setScreen("find")} />
          </>}
          {!isResident && can("triage_reports") && <Big label="Resident Reports" hint="Security queue" onClick={() => setMsg("Queue screen: planned (API ready)")} />}
          {!isResident && can("capture_evidence") && <Big label="Report Violation" hint="Photo + GPS" onClick={() => setScreen("report")} />}
          {can("submit_report") && isResident && <Big label="Report a Concern" hint="Unverified until security checks" onClick={() => setScreen("concern")} />}
        </nav>
      )}
      {screen !== "home" && <button className="link" onClick={() => setScreen("home")}>&larr; Back</button>}
      {screen === "checkin" && <CheckIn client={client} queue={queue} estate={me.estates[0]} setMsg={setMsg} />}
      {screen === "checkout" && <CheckOut client={client} estate={me.estates[0]} setMsg={setMsg} />}
      {screen === "find" && <FindVehicle client={client} estate={me.estates[0]} />}
      {screen === "report" && <ReportViolation />}
      {screen === "concern" && <Concern client={client} estate={me.estates[0]} label={me.anonymous_label} setMsg={setMsg} />}
      <footer><small>Offline drafts are provisional. Fines, clamping, towing and payments are disabled until separately authorized.</small></footer>
    </main>
  );
}

function Big({ label, hint, onClick }: { label: string; hint: string; onClick: () => void }) {
  return <button className="big" onClick={onClick}><strong>{label}</strong><span>{hint}</span></button>;
}

function Connect({ onReady }: { onReady: (o: OrgContext, m: Me) => void }) {
  const [url, setUrl] = useState("https://");
  const [orgId, setOrgId] = useState("");
  const [usr, setUsr] = useState("");
  const [pwd, setPwd] = useState("");
  const [err, setErr] = useState("");
  async function go(e: React.FormEvent) {
    e.preventDefault();
    try {
      const o = { orgId, baseUrl: url.replace(/\/$/, "") };
      const c = new FrappeClient(o);
      await c.login(usr, pwd);
      const me = (await c.whoami()) as Me;
      if (me.organization !== orgId) throw new Error("Organization mismatch - refusing to continue");
      onReady(o, me);
    } catch (x) { setErr(x instanceof Error ? x.message : "Sign-in failed"); }
  }
  return (
    <main>
      <h1>Community Parking &amp; Compliance</h1>
      <form onSubmit={go}>
        <label>Organization code<input value={orgId} onChange={(e) => setOrgId(e.target.value)} autoCapitalize="none" required /></label>
        <label>Organization address<input value={url} onChange={(e) => setUrl(e.target.value)} inputMode="url" required /></label>
        <label>Email<input value={usr} onChange={(e) => setUsr(e.target.value)} inputMode="email" autoCapitalize="none" required /></label>
        <label>Password<input type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} required /></label>
        <button className="big" type="submit"><strong>Sign in</strong></button>
        {err && <p role="alert" className="error">{err}</p>}
      </form>
      <p><small>Use only with an invitation from your association. Demo mode uses synthetic data.</small></p>
    </main>
  );
}

function CheckIn({ client, queue, estate, setMsg }: { client: FrappeClient; queue: OfflineQueue | null; estate: string; setMsg: (m: string) => void }) {
  const [unit, setUnit] = useState("");
  const [plate, setPlate] = useState("");
  const [cands, setCands] = useState<{ kind: string; plate: string; hint?: string; make?: string; color?: string }[]>([]);
  async function lookup() {
    try { setCands((await client.get("registry.lookup_visits_for_unit", { estate, unit_label: unit })).candidates); }
    catch { setMsg("Could not load suggestions (offline?). Enter the plate manually."); }
  }
  async function confirm() {
    let p: string;
    try { p = normalizePlate(plate); } catch (e) { setMsg((e as Error).message); return; }
    const args = { estate, host_unit_label: unit, plate: p, client_uuid: uuid(), confirm_visiting_today: 1 };
    try {
      const r = await client.post("visitors.check_in_visitor", args);
      setMsg(`Checked in ${r.plate} for ${r.host_unit}`);
    } catch (e) {
      if (queue) { await queue.enqueue("visitor_check_in", args); setMsg("Saved offline - Pending Sync (not yet committed)"); }
      else setMsg((e as Error).message);
    }
  }
  return (
    <section>
      <h2>Check In</h2>
      <label>Unit<input value={unit} onChange={(e) => setUnit(e.target.value)} autoCapitalize="characters" /></label>
      <button onClick={lookup}>Show known vehicles</button>
      <ul>{cands.map((c) => <li key={c.plate}><button className="row" onClick={() => setPlate(c.plate)}>{c.plate} <small>{c.kind}{c.hint ? ` - ${c.hint}` : ""}</small></button></li>)}</ul>
      <label>Plate<input value={plate} onChange={(e) => setPlate(e.target.value)} autoCapitalize="characters" /></label>
      <p><small>A previous visit is a suggestion, not permission. Confirm the vehicle is here and visiting this unit today.</small></p>
      <button className="big" onClick={confirm} disabled={!unit || !plate}><strong>Confirm Entry</strong></button>
    </section>
  );
}

function CheckOut({ client, estate, setMsg }: { client: FrappeClient; estate: string; setMsg: (m: string) => void }) {
  const [list, setList] = useState<{ session: string; plate: string; host_unit: string; entry_at: string }[]>([]);
  const load = async () => {
    setList(await client.get("visitors.active_visitors", { estate }));
  };
  const out = async (s: string) => {
    try { const r = await client.post("visitors.check_out_visitor", { session: s, client_uuid: uuid() }); setMsg(`Checked out after ${r.duration_minutes} min`); await load(); }
    catch (e) { setMsg((e as Error).message); }
  };
  return (
    <section>
      <h2>Visitors Inside</h2>
      <button onClick={load}>Refresh</button>
      <ul>{list.map((v) => <li key={v.session}><span>{v.plate} &rarr; {v.host_unit}</span> <button className="big" onClick={() => out(v.session)}><strong>Confirm Exit</strong></button></li>)}</ul>
    </section>
  );
}

function FindVehicle({ client, estate }: { client: FrappeClient; estate: string }) {
  const [plate, setPlate] = useState("");
  const [res, setRes] = useState<Record<string, unknown> | null>(null);
  const go = async () => setRes(await client.get("registry.lookup_plate", { estate, plate }));
  return (
    <section>
      <h2>Find Vehicle</h2>
      <label>Plate<input value={plate} onChange={(e) => setPlate(e.target.value)} autoCapitalize="characters" /></label>
      <button className="big" onClick={go}><strong>Search</strong></button>
      {res && <pre aria-label="result">{JSON.stringify(res, null, 2)}</pre>}
    </section>
  );
}

function ReportViolation() {
  const [fix, setFix] = useState<LocationFix | null | undefined>(undefined);
  const [photo, setPhoto] = useState<string | null>(null);
  const tier = accuracyTier(fix?.accuracyM);
  return (
    <section>
      <h2>Report Violation</h2>
      <button className="big" onClick={async () => setPhoto((await takePhoto())?.dataUrl ?? null)}><strong>Take photo</strong></button>
      {photo && <img src={photo} alt="Captured evidence" width={160} />}
      <button className="big" onClick={async () => setFix(await captureLocation())}><strong>Capture location</strong></button>
      {fix === null && <p role="alert">Location unavailable. Choose a zone or place the pin manually; the report is never blocked.</p>}
      {fix && <p>{fix.lat.toFixed(5)}, {fix.lon.toFixed(5)} &plusmn;{Math.round(fix.accuracyM)} m - {TIER_LABEL[tier]}. This is where YOU are; drag the pin to the vehicle before saving.</p>}
    </section>
  );
}

function Concern({ client, estate, label, setMsg }: { client: FrappeClient; estate: string; label: string; setMsg: (m: string) => void }) {
  const [mode, setMode] = useState<"identified" | "anonymous" | null>(null);
  const [narr, setNarr] = useState("");
  const [code, setCode] = useState("");
  async function send() {
    try {
      if (mode === "identified") {
        const r = await client.post("allegations.submit_identified", { estate, category: "Other", narrative: narr, client_uuid: uuid() });
        setMsg(`Received (${r.reference}). Security will review; this does not start any fine or warning.`);
      } else {
        const r = await client.submitAnonymous({ estate, community_code: code, category: "Other", narrative: narr });
        setMsg(`Save this secret now: ${r.secret}  (receipt ${r.receipt_id})`);
      }
    } catch (e) { setMsg((e as Error).message); }
  }
  return (
    <section>
      <h2>Report a Concern</h2>
      <p>Choose how to report:</p>
      <button onClick={() => setMode("identified")}>Identified - security can ask follow-up questions; your name is not shown to the driver or other residents.</button>
      <button onClick={() => setMode("anonymous")}>{label} - no account details are sent; no follow-up is possible unless you save the one-time secret.</button>
      {mode === "anonymous" && <>
        <p><small>Timing, photos or descriptions can still reveal who you are. {label === "Confidential" ? "This route is labelled Confidential until its logging review is complete." : ""}</small></p>
        <label>Community code<input value={code} onChange={(e) => setCode(e.target.value)} /></label>
      </>}
      {mode && <>
        <label>What is happening?<textarea value={narr} onChange={(e) => setNarr(e.target.value)} maxLength={2000} /></label>
        <p><small>In an active emergency call estate security directly - this app does not guarantee a response time.</small></p>
        <button className="big" onClick={send} disabled={!narr}><strong>Submit</strong></button>
      </>}
    </section>
  );
}
