// SPDX-License-Identifier: Apache-2.0
import { useState } from "react";
import { api } from "../api";
import { Badge, Btn, Err, Notice, Panel, Table, fmt, useLoad, daysAgo } from "../ui";

interface Ev { at_utc: string; actor: string; role: string; gate: string; action: string; record_type: string; target_unit: string; category: string; purpose: string; purpose_ref: string; result: string; reason_code: string; request_id: string }
interface Flag { name: string; rule: string; actor_user: string; summary: string; count: number; severity: string; status: string; created_at: string }
interface Person { actor: string; role: string; allowed: number; denied: number; no_match: number; emergency: number; households: number }

export default function AccessReview({ role }: { role: string }) {
  const [actor, setActor] = useState(""); const [unit, setUnit] = useState(""); const [result, setResult] = useState(""); const [from, setFrom] = useState(daysAgo(7)); const [to, setTo] = useState("");
  const events = useLoad<{ rows: Ev[] }>(() => api.get("access_review.search", { actor_user: actor, unit, result, date_from: from, date_to: to }), [actor, unit, result, from, to]);
  const summary = useLoad<{ people: Person[]; most_looked_up_households: { unit: string; lookups: number; officers: number }[]; note: string }>(() => api.get("access_review.summary", { date_from: from }), [from]);
  const flags = useLoad<Flag[]>(() => api.get("access_review.flags"), []);
  const emerg = useLoad<Record<string, unknown>[]>(() => api.get("access_review.pending_emergency_reviews"), []);
  const chain = useLoad<{ intact: boolean }>(() => api.get("access_review.verify_chain"), []);
  const audit = useLoad<{ intact: boolean }>(() => api.get("access_review.verify_audit_chain"), []);
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const canAct = role === "org_admin" || role === "estate_manager";
  const act = async (label: string, fn: () => Promise<unknown>) => { setErr(""); setMsg(""); try { const r = await fn(); setMsg(`${label}: ${typeof r === "object" ? JSON.stringify(r).slice(0, 160) : "done"}`); flags.reload(); emerg.reload(); events.reload(); } catch (e) { setErr((e as Error).message); } };
  return (
    <>
      <Notice><strong>Review signals are not findings.</strong> A flag means "look at this", never "this person did wrong". Nothing here suspends or disciplines anyone automatically. Reviewing is itself recorded.</Notice>
      <Err msg={err} />{msg && <p role="status" className="ok">{msg}</p>}
      <Panel title="Integrity" actions={canAct ? <Btn onClick={() => act("Detection run", () => api.post("access_review.run_detection"))}>Run detection now</Btn> : undefined}>
        <p>Access journal hash chain: {chain.data ? (chain.data.intact ? <Badge tone="ok">intact</Badge> : <Badge tone="danger">BROKEN - investigate</Badge>) : "checking..."}
          {"  "}General audit chain: {audit.data ? (audit.data.intact ? <Badge tone="ok">intact</Badge> : <Badge tone="danger">BROKEN - investigate</Badge>) : "checking..."}</p>
      </Panel>
      <Panel title="Review signals" note="Sent to reviewers only. Unusual volume, repeated lookups of one household, repeated denials, activity outside duty, contact reveals without a workflow, privileged volume, emergency use.">
        <Err msg={flags.error} />
        <Table rows={(flags.data ?? []) as unknown as Record<string, unknown>[]} empty="No signals." cols={[
          { key: "severity", label: "Severity", render: (r) => <Badge tone={r.severity === "High" ? "danger" : "warn"}>{String(r.severity)}</Badge> },
          { key: "rule", label: "Signal" }, { key: "actor_user", label: "Person" }, { key: "summary", label: "Summary" }, { key: "status", label: "Status" },
          { key: "created_at", label: "Raised", render: (r) => fmt(r.created_at) },
          { key: "a", label: "Review", render: (r) => (canAct && r.status !== "Closed - No Action" ? <span className="row-actions">
            {["In Review", "Closed - No Action", "Escalated"].map((o) => <Btn key={o} onClick={() => { const note = window.prompt(`Note for "${o}" (required)`); if (note) act("Reviewed", () => api.post("access_review.review_flag", { flag: r.name, outcome: o, note })); }}>{o}</Btn>)}</span> : "") },
        ]} />
      </Panel>
      <Panel title="Emergency (break-glass) reviews" note="Every emergency grant needs a review by someone other than the person who used it.">
        <Table rows={emerg.data ?? []} empty="No grants awaiting review." cols={[{ key: "name", label: "Grant" }, { key: "requested_by", label: "Used by" }, { key: "reason", label: "Reason given" }, { key: "status", label: "State" }, { key: "reveal_count", label: "Reveals" },
          { key: "a", label: "Review", render: (r) => <span className="row-actions">{["Appropriate", "Inappropriate", "Needs follow-up"].map((o) => <Btn key={o} onClick={() => { const note = window.prompt(`Review note for "${o}"`); if (note) act("Emergency reviewed", () => api.post("duty.review_emergency", { grant: r.name, outcome: o, note })); }}>{o}</Btn>)}</span> }]} />
      </Panel>
      <Panel title="Activity by person" note={summary.data?.note}>
        <Err msg={summary.error} />
        <Table rows={(summary.data?.people ?? []) as unknown as Record<string, unknown>[]} cols={[{ key: "actor", label: "Person" }, { key: "role", label: "Role" }, { key: "allowed", label: "Allowed" }, { key: "no_match", label: "No match" }, { key: "denied", label: "Denied" }, { key: "emergency", label: "Emergency" }, { key: "households", label: "Different households" }]} />
        {(summary.data?.most_looked_up_households.length ?? 0) > 0 && <><h3>Households looked up most often</h3>
          <Table rows={(summary.data?.most_looked_up_households ?? []) as unknown as Record<string, unknown>[]} cols={[{ key: "unit", label: "Unit" }, { key: "lookups", label: "Lookups" }, { key: "officers", label: "Different people" }]} /></>}
      </Panel>
      <Panel title="Access journal" actions={<span className="filters">
        <input placeholder="Person (email)" value={actor} onChange={(e) => setActor(e.target.value)} aria-label="Person" />
        <input placeholder="Unit" value={unit} onChange={(e) => setUnit(e.target.value)} aria-label="Unit" />
        <select value={result} onChange={(e) => setResult(e.target.value)} aria-label="Outcome"><option value="">All outcomes</option>{["Allowed", "Denied", "No Match", "Emergency"].map((o) => <option key={o}>{o}</option>)}</select>
        <label>From <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label><label>To <input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
        {role === "org_admin" && <Btn onClick={async () => { try { const r = await api.get("access_review.export_log", { date_from: from, date_to: to }); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([r.csv], { type: "text/csv" })); a.download = "access-journal.csv"; a.click(); } catch (e) { setErr((e as Error).message); } }}>Export CSV</Btn>}</span>}>
        <Err msg={events.error} />
        <Table rows={(events.data?.rows ?? []) as unknown as Record<string, unknown>[]} empty="No events match." cols={[
          { key: "at_utc", label: "When (UTC)" }, { key: "actor", label: "Person" }, { key: "role", label: "Role" }, { key: "action", label: "Action" }, { key: "record_type", label: "Record" },
          { key: "target_unit", label: "Unit" }, { key: "purpose", label: "Purpose" }, { key: "result", label: "Outcome", render: (r) => <Badge tone={r.result === "Denied" ? "danger" : r.result === "Emergency" ? "warn" : undefined}>{String(r.result)}</Badge> },
          { key: "reason_code", label: "Reason code" }, { key: "request_id", label: "Request" }]} />
        <p className="muted">The journal stores identifiers, outcomes and one-way search hashes. It never stores names, phone numbers, photos or report text.</p>
      </Panel>
    </>
  );
}
