// SPDX-License-Identifier: Apache-2.0
import { useEffect, useRef, useState } from "react";
import { Big, Chip, Screen, fmtTime } from "../components/ui";
import { normalizePlate } from "../lib/plate";
import { isNetworkError, recordTiming, uuid, type Ctx } from "../lib/types";

const recentUnits = (): string[] => { try { return JSON.parse(localStorage.getItem("cpcp.recentUnits") ?? "[]"); } catch { return []; } };
const pushRecent = (u: string) => { try { localStorage.setItem("cpcp.recentUnits", JSON.stringify([u, ...recentUnits().filter((x) => x !== u)].slice(0, 6))); } catch { /* ignore */ } };

interface Cand { kind: string; plate: string; hint?: string; make?: string; color?: string; active_session?: string | null }

/** Unit first. A suggestion is a convenience, never an authorization: the officer confirms the car and the visit. */
export function CheckIn({ c }: { c: Ctx }) {
  const t0 = useRef(performance.now());
  const [unit, setUnit] = useState("");
  const [cands, setCands] = useState<Cand[] | null>(null);
  const [plate, setPlate] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load(u: string) {
    setUnit(u); setPlate(""); setCands(null);
    if (!u) return;
    try { setCands((await c.client.get("registry.lookup_visits_for_unit", { estate: c.estate.estate, unit_label: u })).candidates); }
    catch (e) { setCands([]); c.toast(isNetworkError(e) ? "Offline: type the plate. It will be saved and sent later." : "Unit not found in this estate."); }
  }

  async function confirm() {
    let p: string;
    try { p = normalizePlate(plate); } catch (e) { c.toast((e as Error).message); return; }
    const args = { estate: c.estate.estate, host_unit_label: unit, plate: p, gate: c.gate, client_uuid: uuid(), confirm_visiting_today: 1 };
    setBusy(true);
    try {
      const r = await c.client.post("visitors.check_in_visitor", args);
      pushRecent(unit); recordTiming("checkin", performance.now() - t0.current);
      setDone(`${r.plate} entered for ${r.host_unit} at ${fmtTime(r.entry_at)}`);
    } catch (e) {
      if (isNetworkError(e) && c.queue) {
        await c.queue.enqueue("visitor_check_in", args);
        setDone(`${p} SAVED OFFLINE for ${unit}. Pending Sync - not yet on the shared register.`);
      } else c.toast((e as Error).message);
    } finally { setBusy(false); }
  }

  if (done) return (
    <Screen title="Entry recorded" onBack={() => c.go("home")}>
      <p className="notice" role="status">{done}</p>
      <Big icon="+" label="Check in another" onClick={() => { setDone(null); setUnit(""); setCands(null); setPlate(""); t0.current = performance.now(); }} />
    </Screen>
  );
  return (
    <Screen title="Check In" onBack={() => c.go("home")}>
      <label>1. Which unit is the visitor going to?
        <input value={unit} onChange={(e) => setUnit(e.target.value.toUpperCase())} onBlur={() => load(unit)} placeholder="e.g. A1" autoCapitalize="characters" inputMode="text" enterKeyHint="go" />
      </label>
      <div className="chips">{recentUnits().map((u) => <Chip key={u} onClick={() => load(u)} active={u === unit}>{u}</Chip>)}</div>
      {cands && cands.length > 0 && <>
        <p>2. Tap the vehicle that is here now:</p>
        <ul className="plain">{cands.map((x) => (
          <li key={x.plate + x.kind}>
            <Big icon={x.kind === "Resident Vehicle" ? "H" : "R"} label={x.plate} hint={`${x.kind}${x.make ? ` - ${x.make} ${x.color ?? ""}` : ""}${x.hint ? ` - ${x.hint}` : ""}`}
              onClick={() => setPlate(x.plate)} tone={plate === x.plate ? "primary" : undefined} />
            {x.active_session && <small className="warn">Already inside - use Check Out first</small>}
          </li>))}</ul>
      </>}
      <label>{cands && cands.length ? "Or a different vehicle:" : "2. Plate number:"}
        <input value={plate} onChange={(e) => setPlate(e.target.value.toUpperCase())} autoCapitalize="characters" placeholder="GR 1234-25" />
      </label>
      <p className="hint">A past visit is only a suggestion. Confirm the car is here and visiting this unit today.</p>
      <Big icon="OK" tone="ok" label="Confirm Entry" hint={plate && unit ? `${plate} -> ${unit}` : "Choose unit and plate"} onClick={confirm} disabled={!plate || !unit || busy} />
    </Screen>
  );
}

interface Visit { session: string; plate: string; host_unit: string; entry_at: string; presence: string }

export function CheckOut({ c }: { c: Ctx }) {
  const [list, setList] = useState<Visit[]>([]);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<Visit | null>(null);
  const load = async () => { try { setList(await c.client.get("visitors.active_visitors", { estate: c.estate.estate })); } catch { c.toast("Cannot load visitors (offline?)"); } };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  const shown = list.filter((v) => !q || v.plate.replace(/\W/g, "").includes(q.replace(/\W/g, "").toUpperCase()) || v.host_unit === q.toUpperCase());

  async function out() {
    if (!sel) return;
    const args = { session: sel.session, gate: c.gate, client_uuid: uuid() };
    try {
      const r = await c.client.post("visitors.check_out_visitor", args);
      c.toast(`${sel.plate} out after ${r.duration_minutes ?? "?"} min`); setSel(null); await load();
    } catch (e) {
      if (isNetworkError(e) && c.queue) { await c.queue.enqueue("visitor_check_out", args); c.toast("Saved offline - Pending Sync"); setSel(null); }
      else c.toast((e as Error).message);
    }
  }
  if (sel) return (
    <Screen title="Confirm Exit" onBack={() => setSel(null)}>
      <p className="notice"><strong>{sel.plate}</strong> for unit {sel.host_unit}, in since {fmtTime(sel.entry_at)}</p>
      <p className="hint">Check this is the vehicle leaving now.</p>
      <Big icon="OK" tone="ok" label="Confirm Exit" onClick={out} />
    </Screen>
  );
  return (
    <Screen title={`Visitors inside (${list.length})`} onBack={() => c.go("home")}>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search plate or unit" aria-label="Search plate or unit" />
      <ul className="plain">{shown.map((v) => <li key={v.session}><Big icon="-&gt;" label={v.plate} hint={`Unit ${v.host_unit} - in ${fmtTime(v.entry_at)}`} onClick={() => setSel(v)} /></li>)}</ul>
      {!shown.length && <p>No visitors match.</p>}
      <button className="link" onClick={load}>Refresh</button>
    </Screen>
  );
}

export function FindVehicle({ c }: { c: Ctx }) {
  const [plate, setPlate] = useState("");
  const [res, setRes] = useState<Record<string, string> | null>(null);
  async function go() {
    try { setRes(await c.client.get("registry.lookup_plate", { estate: c.estate.estate, plate })); }
    catch (e) { c.toast(isNetworkError(e) ? "Offline" : "Not permitted or invalid plate"); }
  }
  const text: Record<string, string> = { resident_vehicle: "Resident vehicle", active_visitor: "Visitor inside now", none: "No match", ambiguous: "More than one match - ask a supervisor" };
  return (
    <Screen title="Find Vehicle" onBack={() => c.go("home")}>
      <label>Plate<input value={plate} onChange={(e) => setPlate(e.target.value.toUpperCase())} autoCapitalize="characters" enterKeyHint="search" /></label>
      <Big icon="?" label="Search" onClick={go} disabled={!plate} />
      {res && <div className="notice" role="status">
        <strong>{text[res.match] ?? res.match}</strong>
        {res.unit && <div>Unit {res.unit}</div>}{res.host_unit && <div>Visiting unit {res.host_unit}</div>}
        {res.vehicle && <div>{(res.vehicle as unknown as { make?: string; color?: string }).make} {(res.vehicle as unknown as { color?: string }).color}</div>}
        <small>A plate match is a candidate, not proof of who is driving.</small>
      </div>}
    </Screen>
  );
}
