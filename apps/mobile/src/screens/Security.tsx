// SPDX-License-Identifier: Apache-2.0
import { useEffect, useState } from "react";
import MapPin, { type Pin } from "../components/MapPin";
import { Big, Chip, Screen, fmtTime } from "../components/ui";
import { captureLocation, takePhoto, type LocationFix } from "../lib/device";
import { accuracyTier, normalizePlate, TIER_LABEL } from "../lib/plate";
import { uuid, type Ctx } from "../lib/types";

interface QItem { work_item: string; allegation: string; category: string; urgency: string; age_minutes: number; claimed: boolean; claimed_by: string | null; coarse_location: string; follow_up_available: boolean; reports_label: string; report_count: number; possible_related_case: boolean; related_case_already_handled: boolean; needs_review: boolean }

export function Queue({ c }: { c: Ctx }) {
  const [items, setItems] = useState<QItem[]>([]);
  const load = async () => { try { setItems(await c.client.get("allegations.triage_queue", { estate: c.estate.estate })); } catch { c.toast("Cannot load reports"); } };
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  async function claim(i: QItem) {
    try { await c.client.post("allegations.claim_work_item", { work_item: i.work_item }); c.go("verify", i.allegation); }
    catch (e) { c.toast((e as Error).message); load(); }
  }
  return (
    <Screen title="Resident Reports" onBack={() => c.go("home")}>
      <p className="hint">These are unverified reports from residents. Nothing here is a violation until you check it yourself.</p>
      <ul className="plain">{items.map((i) => (
        <li key={i.work_item} className="card">
          <strong>{i.category}</strong> {i.urgency !== "Normal" && <span className="badge danger">URGENT CLAIMED</span>}
          <div><span className="badge">{i.reports_label}</span> {i.coarse_location} - first report {i.age_minutes} min ago</div>
          {i.possible_related_case && <div className="notice">Possibly the same vehicle as a case already open{i.related_case_already_handled ? " - ALREADY BEING HANDLED. Do not start a second action." : "."}</div>}
          {!i.follow_up_available && <small>Anonymous: follow-up unavailable</small>}
          {i.claimed
            ? <Big icon=">" label="Continue" hint={`Claimed by ${i.claimed_by}`} onClick={() => c.go("verify", i.allegation)} />
            : <Big icon="+" tone="primary" label="Claim and investigate" onClick={() => claim(i)} />}
        </li>))}</ul>
      {!items.length && <p>No open reports.</p>}
    </Screen>
  );
}

interface Alg { label: string; category: string; narrative: string; alleged_plate_text: string | null; location: { lat: number | null; lon: number | null; accuracy_m: number | null }; urgent_claim: boolean }

export function Verify({ c, allegation }: { c: Ctx; allegation: string }) {
  const [a, setA] = useState<Alg | null>(null);
  const [plate, setPlate] = useState("");
  const [photo, setPhoto] = useState<{ dataUrl: string; base64: string; sha256: string } | null>(null);
  const [fix, setFix] = useState<LocationFix | null | undefined>(undefined);
  const [pin, setPin] = useState<Pin | null>(null);
  const [reason, setReason] = useState("");
  const [emergency, setEmergency] = useState(false);
  const [busy, setBusy] = useState(false);
  const [rphotos, setRphotos] = useState<{ attachment: string; data_url: string }[]>([]);
  const boundary = c.estate.boundary?.coordinates ?? null;

  useEffect(() => { c.client.get("allegations.open_allegation", { allegation }).then((r) => { setA(r); setPlate(r.alleged_plate_text ?? ""); }).catch(() => c.toast("Cannot open report")); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  useEffect(() => { c.client.get("allegations.allegation_photos", { allegation }).then(setRphotos).catch(() => setRphotos([])); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  async function locate() {
    const f = await captureLocation();
    setFix(f);
    if (f) setPin({ lat: f.lat, lon: f.lon });
    else if (!pin) { const z = boundary?.[0]?.[0]; setPin(z ? { lat: z[1], lon: z[0] } : null); c.toast("Location unavailable. Place the pin by hand on the map."); }
  }
  const moved = fix && pin && (Math.abs(fix.lat - pin.lat) > 1e-5 || Math.abs(fix.lon - pin.lon) > 1e-5);
  const manualOnly = !fix && !!pin;

  async function verify() {
    let p: string;
    try { p = normalizePlate(plate); } catch (e) { c.toast((e as Error).message); return; }
    if (!photo) { c.toast("Take a photo of the vehicle first"); return; }
    if (!pin) { c.toast("Confirm the vehicle position on the map"); return; }
    if ((moved || manualOnly) && !reason.trim()) { c.toast("Say why the pin is not at your phone's position"); return; }
    setBusy(true);
    try {
      const r = await c.client.post("allegations.verify_and_create_violation", {
        allegation, plate: p, officer_photo_sha256: photo.sha256, photo_base64: photo.base64, photo_name: "evidence.jpg",
        device_lat: fix?.lat ?? pin.lat, device_lon: fix?.lon ?? pin.lon, device_accuracy_m: fix?.accuracyM ?? 999,
        pin_lat: pin.lat, pin_lon: pin.lon, pin_source: manualOnly ? "manual_pin" : moved ? "manual_pin" : "device",
        pin_reason: reason || undefined, classification: emergency ? "Emergency" : "Ordinary",
      });
      c.toast("Violation created. Contact the responsible person."); c.go("case", r.incident);
    } catch (e) { c.toast((e as Error).message); } finally { setBusy(false); }
  }
  async function reject(outcome: string) {
    const r = prompt(`Reason for "${outcome}" (required)`);
    if (!r) return;
    try { await c.client.post("allegations.close_allegation", { allegation, outcome, reason: r }); c.toast("Report closed. No fee or warning was created."); c.go("queue"); }
    catch (e) { c.toast((e as Error).message); }
  }
  if (!a) return <Screen title="Report" onBack={() => c.go("queue")}><p>Loading...</p></Screen>;
  return (
    <Screen title="Check and verify" onBack={() => c.go("queue")}>
      <div className="card"><span className="badge">{a.label}</span><strong>{a.category}</strong><p>{a.narrative}</p>
        {a.location.lat != null && <small>Reporter's pin: {a.location.lat?.toFixed(5)}, {a.location.lon?.toFixed(5)} (not verified)</small>}</div>
      {rphotos.length > 0 && <div><small>Reporter's photos (unverified, location data removed)</small><div className="chips">{rphotos.map((x) => <img key={x.attachment} src={x.data_url} alt="Reporter photo" className="thumb" style={{ maxWidth: 140 }} />)}</div></div>}
      <label>Plate you see<input value={plate} onChange={(e) => setPlate(e.target.value.toUpperCase())} autoCapitalize="characters" /></label>
      <Big icon="[o]" label={photo ? "Retake photo" : "Take photo"} onClick={async () => setPhoto(await takePhoto())} />
      {photo && <img src={photo.dataUrl} alt="Evidence preview" className="thumb" />}
      <Big icon="(+)" label="Capture my location" hint="Asked once, only now" onClick={locate} />
      {fix && <p>Phone position: &plusmn;{Math.round(fix.accuracyM)} m - <strong>{TIER_LABEL[accuracyTier(fix.accuracyM)]}</strong></p>}
      {fix === null && <p role="alert" className="error">No location. Place the pin by hand - you can still continue.</p>}
      {pin && <>
        <p>Drag the car to where the vehicle really is:</p>
        <MapPin pin={pin} onChange={setPin} boundary={boundary} deviceFix={fix ? { lat: fix.lat, lon: fix.lon } : null} />
        {(moved || manualOnly) && <label>Why is it different from your phone?
          <div className="chips">{["Vehicle is away from me", "GPS is weak", "No GPS signal"].map((t) => <Chip key={t} onClick={() => setReason(t)} active={reason === t}>{t}</Chip>)}</div>
          <input value={reason} onChange={(e) => setReason(e.target.value)} /></label>}
      </>}
      <label className="row"><input type="checkbox" checked={emergency} onChange={(e) => setEmergency(e.target.checked)} /> Blocks gate / emergency access (needs urgent removal, never clamp)</label>
      <Big icon="OK" tone="ok" label="Verify and create violation" onClick={verify} disabled={busy} />
      <div className="chips">
        <Chip onClick={() => reject("Not Substantiated")}>Not substantiated</Chip>
        <Chip onClick={() => reject("Resolved without Violation")}>Resolved - no violation</Chip>
        <Chip onClick={() => reject("Duplicate / Merged")}>Duplicate</Chip>
      </div>
    </Screen>
  );
}

interface CaseRow { incident: string; plate: string; status: string; classification: string; notice_deadline: string | null; attempts: number; episode_status: string; reports: number; already_being_handled: boolean; priority: string }

export function Cases({ c }: { c: Ctx }) {
  const [rows, setRows] = useState<CaseRow[]>([]);
  useEffect(() => { c.client.get("ops.active_cases", { estate: c.estate.estate }).then(setRows).catch(() => c.toast("Cannot load cases")); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  return (
    <Screen title="Active Cases" onBack={() => c.go("home")}>
      <ul className="plain">{rows.map((r) => <li key={r.incident}><Big icon={r.priority !== "Normal" ? "!!" : "!"} label={`${r.plate} - ${r.episode_status}`}
        hint={`${r.reports} report${r.reports === 1 ? "" : "s"}${r.already_being_handled ? " - Already being handled" : ""}${r.notice_deadline ? ` - deadline ${fmtTime(r.notice_deadline)}` : " - no warning clock yet"}`} onClick={() => c.go("case", r.incident)} /></li>)}</ul>
      {!rows.length && <p>No active cases.</p>}
    </Screen>
  );
}

interface Contact { contact_id: string; relationship: string; first_name: string; number: string }
interface Rep { allegation: string; link_state: string; reason: string; category: string; urgent: boolean; submitted_at: string; source: string }
interface Tl { attempts: { attempt: string; channel: string; relationship: string; outcome: string | null; provenance: string; duration: string; sms_status: string | null; acknowledged: boolean; initiated_at: string; message_text: string | null }[]; notice: { deadline: string; effective_at: string; proof_basis: string } | null }

export function Case({ c, incident }: { c: Ctx; incident: string }) {
  const [res, setRes] = useState<{ basis: string; label: string; contacts: Contact[]; next_if_unreachable: string[] } | null>(null);
  const [tl, setTl] = useState<Tl | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [sms, setSms] = useState<{ text: string; recipient: string; contact: string } | null>(null);
  const [now, setNow] = useState(Date.now());
  const [reps, setReps] = useState<{ episode_status: string; already_being_handled: boolean; reports: Rep[] } | null>(null);
  const load = async () => {
    try {
      setRes(await c.client.get("communications.resolve_violation_contacts", { incident }));
      setTl(await c.client.get("communications.comms_timeline", { incident }));
      setReps(await c.client.get("incidents.incident_candidates", { incident }));
    }
    catch { c.toast("Cannot load case"); }
  };
  useEffect(() => { load(); const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  async function call(ct: Contact) {
    try {
      const r = await c.client.post("communications.initiate_call", { incident, contact_id: ct.contact_id, client_uuid: uuid() });
      setPending(r.attempt); setConfirmed(false);
      if (r.dial) window.location.href = `tel:${r.dial}`; // opens the phone dialer: this is NOT a connected call
    } catch (e) { c.toast((e as Error).message); }
  }
  async function outcome(o: string) {
    if (!pending) return;
    try {
      const r = await c.client.post("communications.record_call_outcome", { attempt: pending, outcome: o, warning_confirmed: confirmed ? 1 : 0 });
      if (r.can_establish_notice) { await c.client.post("communications.establish_notice_clock", { incident, attempt: pending }); c.toast("Warning clock started (server time)."); }
      else c.toast(o === "Answered" ? "Recorded. Clock not started: warning not confirmed." : "Recorded. Not a notice - try a backup contact or tell the manager.");
      setPending(null); load();
    } catch (e) { c.toast((e as Error).message); }
  }
  async function previewSms(ct: Contact) {
    try { const r = await c.client.get("communications.preview_sms", { incident, contact_id: ct.contact_id }); setSms({ text: r.text, recipient: r.recipient, contact: ct.contact_id }); }
    catch (e) { c.toast((e as Error).message); }
  }
  async function sendSms() {
    if (!sms) return;
    try { await c.client.post("communications.send_case_sms", { incident, contact_id: sms.contact, client_uuid: uuid() }); c.toast("SMS accepted by provider. That is not delivery."); setSms(null); load(); }
    catch (e) { c.toast((e as Error).message); }
  }
  async function review(allegation: string, action: string) {
    const reason = prompt(action === "link" ? "Why is this the same vehicle? (required)" : "Why is this a different vehicle or event? (required)");
    if (!reason) return;
    try { await c.client.post("incidents.review_candidate", { incident, allegation, action, reason }); c.toast("Recorded."); load(); }
    catch (e) { c.toast((e as Error).message); }
  }
  async function ended(evidence: string, label: string) {
    const note = prompt(`${label} - describe what you saw (required)`);
    if (!note) return;
    try { const r = await c.client.post("incidents.end_episode", { incident, evidence, note }); c.toast(r.identity_released ? "Episode ended. A later offense will be a new case." : "Closed, but the vehicle is still treated as the same case."); c.go("cases"); }
    catch (e) { c.toast((e as Error).message); }
  }
  async function corrected() {
    const note = prompt("What happened? (e.g. vehicle moved at 10:42)"); if (!note) return;
    try { await c.client.post("enforcement.mark_corrected", { incident, note }); c.toast("Closed without fee."); c.go("cases"); } catch (e) { c.toast((e as Error).message); }
  }
  const left = tl?.notice ? Math.max(0, Math.floor((new Date(tl.notice.deadline).getTime() - now) / 1000)) : null;
  return (
    <Screen title="Case" onBack={() => c.go("cases")}>
      <p className="hint">{incident}{reps ? ` - ${reps.episode_status} - ${reps.reports.length} report${reps.reports.length === 1 ? "" : "s"}` : ""}</p>
      {reps?.already_being_handled && <p className="notice"><strong>Already being handled.</strong> New reports are added here. Do not start another clamp, tow or warning.</p>}
      {tl?.notice
        ? <p className="notice" role="timer">Warning clock running. Deadline <strong>{fmtTime(tl.notice.deadline)}</strong> ({left! > 0 ? `${Math.floor(left! / 60)}:${String(left! % 60).padStart(2, "0")} left` : "expired - needs manager approval for any action"})</p>
        : <p className="notice">No warning clock. An unanswered call or a sent SMS does not start it.</p>}
      <h3>Who to contact</h3>
      <p className="hint">{res?.label}</p>
      <ul className="plain">{res?.contacts.map((ct) => (
        <li key={ct.contact_id} className="card"><strong>{ct.relationship}</strong> {ct.first_name} <small>{ct.number}</small>
          <div className="chips"><Big icon="Tel" label="Call" onClick={() => call(ct)} /><Big icon="SMS" label="Text" onClick={() => previewSms(ct)} /></div></li>))}</ul>
      {res && !res.contacts.length && <div className="notice"><strong>No verified contact.</strong> Tell the security manager. Do not guess who the driver is.</div>}
      {pending && <div className="card" role="group" aria-label="Call outcome">
        <strong>How did the call go?</strong>
        <div className="chips">{["Answered", "No Answer", "Busy", "Wrong Number", "Could Not Place Call", "Callback Requested"].map((o) => <Chip key={o} onClick={() => outcome(o)}>{o}</Chip>)}</div>
        <label className="row"><input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /> I told them to move the vehicle and they understood</label>
      </div>}
      {sms && <div className="card"><strong>Send this text to {sms.recipient}?</strong><p className="quote">{sms.text}</p>
        <Big icon="OK" tone="ok" label="Send SMS" onClick={sendSms} /><button className="link" onClick={() => setSms(null)}>Cancel</button></div>}
      <h3>History</h3>
      <ul className="plain">{tl?.attempts.map((a) => <li key={a.attempt} className="card"><strong>{a.channel === "sms" ? "SMS" : "Call"}</strong> to {a.relationship} at {fmtTime(a.initiated_at)}
        <div>{a.channel === "sms" ? `Status: ${a.sms_status}${a.acknowledged ? " - acknowledged" : ""}` : `Outcome: ${a.outcome ?? "not recorded (dialer opened only)"}`}</div>
        <small>{a.provenance}{a.channel !== "sms" ? ` - ${a.duration}` : ""}</small></li>)}</ul>
      {reps && reps.reports.length > 0 && <>
        <h3>Reports in this case</h3>
        <ul className="plain">{reps.reports.map((r) => (
          <li key={r.allegation} className="card"><strong>{r.category}</strong> {r.urgent && <span className="badge danger">URGENT</span>} <small>{r.source} - {fmtTime(r.submitted_at)} - {r.link_state}</small>
            {r.link_state === "Auto Candidate" && <div className="chips"><Chip onClick={() => review(r.allegation, "link")}>Same vehicle</Chip><Chip onClick={() => review(r.allegation, "not_related")}>Not related</Chip></div>}</li>))}</ul>
      </>}
      <Big icon="OK" label="Vehicle moved - close without fee" onClick={corrected} />
      <h3>Did the vehicle leave?</h3>
      <p className="hint">Only seeing it leave ends this case. Paying a fee, removing a clamp or a new day does not.</p>
      <div className="chips"><Chip onClick={() => ended("departure_verified", "I saw it leave")}>I saw it leave</Chip><Chip onClick={() => ended("resolved_without_departure", "Close without proof it left")}>Close - not sure it left</Chip></div>
      {!c.me.enforcement_gates.clamping_enabled && !c.me.enforcement_gates.towing_enabled && <small>Clamping, towing and fees are switched off for this association.</small>}
    </Screen>
  );
}
