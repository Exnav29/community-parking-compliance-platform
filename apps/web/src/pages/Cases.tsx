// SPDX-License-Identifier: Apache-2.0
import { useState } from "react";
import { api } from "../api";
import { Badge, Btn, Err, Notice, Panel, Table, fmt, useLoad } from "../ui";

interface Case {
  name: string; plate_snapshot: string; classification: string; episode_status: string; status: string; allegation_count: number; priority: string;
  assigned_officer: string | null; verified_at: string; ended_at: string | null; end_evidence: string | null; penalty_review: number;
}
interface Q { work_item: string; allegation: string; category: string; urgency: string; reports_label: string; claimed: boolean; claimed_by: string | null; coarse_location: string;
  possible_related_case: boolean; related_case_already_handled: boolean; needs_review: boolean; age_minutes: number }
interface Rep { allegation: string; link_state: string; reason: string; confidence: number | null; category: string; urgent: boolean; submitted_at: string; source: string }

export default function Cases({ estate, role }: { estate: string; role: string }) {
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [sel, setSel] = useState<string>("");
  const cases = useLoad<Case[]>(() => api.get("incidents.list_cases", { estate, episode_status: status, search }), [estate, status, search]);
  const queue = useLoad<Q[]>(() => api.get("allegations.triage_queue", { estate }), [estate]);
  const manager = role !== "auditor";
  return (
    <>
      <Panel title="Resident reports waiting" note="One row per actionable case. Several residents reporting the same vehicle appear once, as 'N independent reports'.">
        <Err msg={queue.error} />
        <Table rows={(queue.data ?? []) as unknown as Record<string, unknown>[]} empty="No reports are waiting." cols={[
          { key: "reports_label", label: "Reports" }, { key: "category", label: "Category" },
          { key: "urgency", label: "Priority", render: (r) => (r.urgency === "Normal" ? "Normal" : <Badge tone="danger">Urgent claimed</Badge>) },
          { key: "coarse_location", label: "Where" }, { key: "age_minutes", label: "Age (min)" },
          { key: "claimed_by", label: "Claimed by", render: (r) => String(r.claimed_by ?? "not claimed") },
          { key: "possible_related_case", label: "Note", render: (r) => (r.possible_related_case ? <Badge tone={r.related_case_already_handled ? "warn" : undefined}>{r.related_case_already_handled ? "related case already being handled" : "possible related case"}</Badge> : "") },
        ]} />
      </Panel>
      <Panel title="Cases" actions={<span className="filters">
        <input placeholder="Plate or case no." value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search cases" />
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Episode status">
          <option value="">All states</option>
          {["Verified/Open", "Warning Active", "Compliance Confirmed", "Clamp Active", "Tow Ordered", "Towed/Impounded", "Release Pending", "Resolved/Closed", "Reopened for Review"].map((s) => <option key={s}>{s}</option>)}
        </select></span>}>
        <Err msg={cases.error} />
        <Table rows={(cases.data ?? []) as unknown as Record<string, unknown>[]} empty="No cases match." cols={[
          { key: "name", label: "Case", render: (r) => <button className="link" onClick={() => setSel(String(r.name))}>{String(r.name)}</button> },
          { key: "plate_snapshot", label: "Plate" }, { key: "episode_status", label: "Episode" },
          { key: "allegation_count", label: "Reports" }, { key: "classification", label: "Type" },
          { key: "priority", label: "Priority", render: (r) => (r.priority === "Normal" ? "" : <Badge tone="danger">Urgent</Badge>) },
          { key: "assigned_officer", label: "Assigned" },
          { key: "penalty_review", label: "Ledger", render: (r) => (r.penalty_review ? <Badge tone="danger">duplicate penalty review</Badge> : "") },
          { key: "verified_at", label: "Verified", render: (r) => fmt(r.verified_at) },
        ]} />
      </Panel>
      {sel && manager && <CasePanel incident={sel} estate={estate} role={role} onClose={() => setSel("")} onChanged={() => { cases.reload(); queue.reload(); }} />}
    </>
  );
}

function CasePanel({ incident, estate, role, onClose, onChanged }: { incident: string; estate: string; role: string; onClose: () => void; onChanged: () => void }) {
  const d = useLoad<{ episode_status: string; already_being_handled: boolean; reports: Rep[] }>(() => api.get("incidents.incident_candidates", { incident }), [incident]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const canManage = ["security_manager", "org_admin", "estate_manager"].includes(role);
  async function run(label: string, fn: () => Promise<unknown>) {
    setErr(""); setMsg("");
    try { await fn(); setMsg(`${label}: done`); d.reload(); onChanged(); } catch (e) { setErr((e as Error).message); }
  }
  const ask = (q: string) => window.prompt(q)?.trim() || null;
  return (
    <Panel title={`Case ${incident}`} actions={<Btn onClick={onClose}>Close</Btn>}
      note="Every action here needs a reason, is audited, and never deletes history or a ledger line.">
      <Err msg={err} />{msg && <p role="status" className="ok">{msg}</p>}
      {d.data?.already_being_handled && <Notice><strong>Already being handled</strong> ({d.data.episode_status}). New reports are added to this case; no second clamp, tow or warning can be started.</Notice>}
      <h3>Reports in this case ({d.data?.reports.length ?? 0})</h3>
      <Table rows={(d.data?.reports ?? []) as unknown as Record<string, unknown>[]} cols={[
        { key: "allegation", label: "Report" }, { key: "source", label: "Source" }, { key: "category", label: "Category" },
        { key: "urgent", label: "Urgent", render: (r) => (r.urgent ? <Badge tone="danger">urgent</Badge> : "") },
        { key: "link_state", label: "Link", render: (r) => <Badge tone={r.link_state === "Auto Candidate" ? "warn" : undefined}>{String(r.link_state)}</Badge> },
        { key: "confidence", label: "Match confidence", render: (r) => (r.confidence == null ? "" : `${Math.round(Number(r.confidence) * 100)}%`) },
        { key: "submitted_at", label: "Submitted", render: (r) => fmt(r.submitted_at) },
        { key: "act", label: "Review", render: (r) => (r.link_state === "Auto Candidate" ? <span className="row-actions">
          <Btn onClick={() => { const why = ask("Why is this the same vehicle/event?"); if (why) run("Linked", () => api.post("incidents.review_candidate", { incident, allegation: r.allegation, action: "link", reason: why })); }}>Same</Btn>
          <Btn onClick={() => { const why = ask("Why is this a different event?"); if (why) run("Separated", () => api.post("incidents.review_candidate", { incident, allegation: r.allegation, action: "not_related", reason: why })); }}>Not related</Btn></span> : "") },
      ]} />
      {canManage && <div className="actions">
        <Btn onClick={() => { const to = ask("Merge THIS case into which case number?"); const why = to && ask("Reason for the merge"); if (to && why) run("Merged", () => api.post("incidents.merge_incidents", { source: incident, target: to, reason: why })); }}>Merge into another case</Btn>
        <Btn onClick={() => { const ids = ask("Report numbers to move out (comma separated)"); const why = ids && ask("Reason for the split"); if (ids && why) run("Split", () => api.post("incidents.split_incident", { incident, allegations: ids, reason: why })); }}>Split reports out</Btn>
        <Btn onClick={() => { const u = ask("Officer email to take over this case"); const why = u && ask("Reason (e.g. shift handover)"); if (u && why) run("Reassigned", () => api.post("incidents.reassign_incident", { incident, user: u, reason: why })); }}>Reassign officer</Btn>
        <Btn onClick={() => { const note = ask("Describe the documented determination"); if (note) run("Episode ended", () => api.post("incidents.end_episode", { incident, evidence: "manager_determination", note })); }}>Record manager determination (episode ended)</Btn>
        <Btn onClick={() => { const why = ask("Reason to reopen for review"); if (why) run("Reopened", () => api.post("incidents.reopen_episode", { incident, reason: why })); }}>Reopen for review</Btn>
        {role === "org_admin" && <Btn tone="danger" onClick={() => { const why = ask("Reason for crediting the duplicate base penalty"); if (why) run("Credit added", () => api.post("incidents.credit_duplicate_penalty", { incident, reason: why })); }}>Credit duplicate penalty</Btn>}
      </div>}
      <p className="muted">Estate {estate}. Payment, a cleared clamp or a new day never end an episode; only positive evidence that the vehicle left does.</p>
    </Panel>
  );
}
