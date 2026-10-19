// SPDX-License-Identifier: Apache-2.0
import { useEffect, useState } from "react";
import MapPin, { type Pin } from "../components/MapPin";
import { Big, Chip, Screen } from "../components/ui";
import { captureLocation, takePhoto } from "../lib/device";
import { uuid, type Ctx } from "../lib/types";

const CATEGORIES = ["Gate or driveway blocked", "Roadway obstruction", "Unsafe parking", "Unauthorized space", "Emergency access", "Other"];

export function Concern({ c }: { c: Ctx }) {
  const [mode, setMode] = useState<"identified" | "anonymous" | null>(null);
  const [cat, setCat] = useState(CATEGORIES[0]);
  const [narr, setNarr] = useState("");
  const [plate, setPlate] = useState("");
  const [urgent, setUrgent] = useState(false);
  const [code, setCode] = useState("");
  const [pin, setPin] = useState<Pin | null>(null);
  const [acc, setAcc] = useState<number | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [photo, setPhoto] = useState<{ dataUrl: string; base64: string } | null>(null);
  const boundary = c.estate.boundary?.coordinates ?? null;

  async function here() {
    const f = await captureLocation();
    if (f) { setPin({ lat: f.lat, lon: f.lon }); setAcc(f.accuracyM); }
    else { const z = boundary?.[0]?.[0]; if (z) setPin({ lat: z[1], lon: z[0] }); c.toast("No location. Move the pin to where the vehicle is."); }
  }
  async function send() {
    const loc = pin ? { latitude: pin.lat, longitude: pin.lon, accuracy_m: acc ?? undefined, location_source: acc != null ? "device" : "manual_pin" } : {};
    try {
      if (mode === "identified") {
        const r = await c.client.post("allegations.submit_identified", { estate: c.estate.estate, category: cat, narrative: narr, plate_text: plate || undefined, urgent: urgent ? 1 : 0, client_uuid: uuid(), ...(photo ? { photos_base64: JSON.stringify([photo.base64]) } : {}), ...loc });
        setResult(`Sent. Your reference is ${r.reference}. Security will check it. This does not start any fine or warning.`);
      } else {
        const r = await c.client.submitAnonymous({ estate: c.estate.estate, community_code: code, category: cat, narrative: narr, plate_text: plate || undefined, urgent: urgent ? 1 : 0, ...(photo ? { photos_base64: JSON.stringify([photo.base64]) } : {}), ...loc });
        setResult(`Sent. SAVE THIS NOW - it is shown once.\nReceipt: ${r.receipt_id}\nSecret: ${r.secret}\nWithout it, nobody can show you the status or contact you.`);
      }
    } catch (e) { c.toast((e as Error).message); }
  }
  if (result) return <Screen title="Thank you" onBack={() => c.go("home")}><pre className="notice" role="status">{result}</pre></Screen>;
  if (!mode) return (
    <Screen title="Report a concern" onBack={() => c.go("home")}>
      <p>How do you want to report?</p>
      <Big icon="ID" label="Give my name" hint="Security can ask you questions. Your name is not shown to the driver or other residents." onClick={() => setMode("identified")} />
      <Big icon="?" label={`${c.me.anonymous_label} report`} hint="No account details are sent. Security cannot reply unless you keep a one-time secret." onClick={() => setMode("anonymous")} />
      <p className="hint">Photos, timing and your description can still show who you are. {c.me.anonymous_label === "Confidential" ? "This option is called Confidential until its logging review is complete." : ""}</p>
    </Screen>
  );
  return (
    <Screen title={mode === "identified" ? "Report (with my name)" : `${c.me.anonymous_label} report`} onBack={() => setMode(null)}>
      <div className="chips">{CATEGORIES.map((x) => <Chip key={x} active={cat === x} onClick={() => setCat(x)}>{x}</Chip>)}</div>
      <label>What is happening?<textarea value={narr} onChange={(e) => setNarr(e.target.value)} maxLength={2000} /></label>
      <label>Number plate, if you can read it (optional)<input value={plate} onChange={(e) => setPlate(e.target.value.toUpperCase())} /></label>
      <Big icon="(+)" label="Mark where the vehicle is" hint="Uses your location once, only when you tap" onClick={here} />
      {pin && <MapPin pin={pin} onChange={(p) => { setPin(p); setAcc(null); }} boundary={boundary} />}
      <Big icon="[o]" label={photo ? "Replace photo" : "Add a photo (optional)"} hint="Taken with the camera, only when you tap" onClick={async () => setPhoto(await takePhoto())} />
      {photo && <img src={photo.dataUrl} alt="Your photo" className="thumb" />}
      <p className="hint">Location and camera details are removed from your photo before it is saved. People, cars, doors and buildings in the picture can still show who you are{mode === "anonymous" ? " - think before sending it with an anonymous report" : ""}.</p>
      <label className="row"><input type="checkbox" checked={urgent} onChange={(e) => setUrgent(e.target.checked)} /> It blocks emergency access</label>
      {urgent && <p className="notice">In an emergency call estate security now. This app cannot promise a fast response.</p>}
      {mode === "anonymous" && <label>Community code (from your association notice board)<input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} /></label>}
      <Big icon="OK" tone="ok" label="Send report" onClick={send} disabled={!narr.trim() || (mode === "anonymous" && !code)} />
    </Screen>
  );
}

export function MyReports({ c }: { c: Ctx }) {
  const [rows, setRows] = useState<{ reference: string; category: string; status: string }[]>([]);
  const [summary, setSummary] = useState<{ zones: { zone: string; count: number | string }[]; note: string } | null>(null);
  const [rid, setRid] = useState(""); const [sec, setSec] = useState(""); const [st, setSt] = useState("");
  useEffect(() => {
    c.client.get("allegations.my_reports").then(setRows).catch(() => undefined);
    c.client.get("reports.community_summary", { estate: c.estate.estate }).then(setSummary).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  async function check() {
    try { const r = await c.client.anonymousStatus(rid, sec); setSt(r.found ? `Status: ${r.status}` : "Not found. Check the receipt and secret."); }
    catch { setSt("Cannot reach the server."); }
  }
  return (
    <Screen title="My reports" onBack={() => c.go("home")}>
      <ul className="plain">{rows.map((r) => <li key={r.reference} className="card"><strong>{r.category}</strong><div>{r.reference} - {r.status}</div></li>)}</ul>
      {!rows.length && <p>No reports yet.</p>}
      <h3>Check an anonymous report</h3>
      <label>Receipt<input value={rid} onChange={(e) => setRid(e.target.value)} /></label>
      <label>Secret<input value={sec} onChange={(e) => setSec(e.target.value)} type="password" /></label>
      <Big icon="?" label="Check status" onClick={check} disabled={!rid || !sec} />
      {st && <p role="status">{st}</p>}
      <h3>Parking issues in the estate (last 90 days)</h3>
      <ul className="plain">{summary?.zones.map((z) => <li key={z.zone}>{z.zone}: {String(z.count)}</li>)}</ul>
      <small>{summary?.note}</small>
    </Screen>
  );
}
