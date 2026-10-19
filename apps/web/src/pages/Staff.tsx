// SPDX-License-Identifier: Apache-2.0
import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Btn, Err, Notice, Panel, Table, fmt, useLoad } from "../ui";

const ROLES = ["org_admin", "estate_manager", "security_manager", "security_officer", "resident", "auditor", "finance", "tow_provider", "board_observer"];

export default function Staff({ estate, role }: { estate: string; role: string }) {
  const isAdmin = role === "org_admin" || role === "estate_manager";
  // Role assignments are an organization-admin register. Security managers act on staff from the on-duty list below (revoke / suspend).
  const roles = useLoad(() => (isAdmin ? api.list("CPCP Role Assignment", ["name", "user", "cpcp_role", "estate", "unit", "status", "valid_until", "approved_by"], {}, 200) : Promise.resolve([])), [isAdmin]);
  const shifts = useLoad(() => api.list("CPCP Gate Shift", ["name", "user", "gate", "status", "started_at", "ends_at", "ended_reason"], { estate }, 60), [estate]);
  const [user, setUser] = useState(""); const [r, setR] = useState("security_officer"); const [until, setUntil] = useState("");
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const manager = ["org_admin", "security_manager", "estate_manager"].includes(role);
  const act = async (label: string, fn: () => Promise<unknown>) => { setErr(""); setMsg(""); try { await fn(); setMsg(label); roles.reload(); shifts.reload(); } catch (e) { setErr((e as Error).message); } };
  return (
    <>
      <Notice>Staff are named individuals with explicit estate scope. Privileged roles need a second approver; shared logins are not supported. Revoking a device or suspending a person takes effect on the very next request.</Notice>
      <Err msg={err || roles.error} />{msg && <p role="status" className="ok">{msg}</p>}
      {isAdmin && <Panel title="Role assignments">
        <Table rows={roles.data ?? []} cols={[{ key: "user", label: "Person" }, { key: "cpcp_role", label: "Role" }, { key: "estate", label: "Estate" }, { key: "status", label: "Status" }, { key: "valid_until", label: "Expires" }, { key: "approved_by", label: "Approved by" },
          { key: "a", label: "Actions", render: (x) => (manager && x.status === "Active" ? <span className="row-actions">
            <Btn onClick={() => { const why = window.prompt("Reason for revoking this person's device(s)"); if (why) act("Device revoked and sessions cleared", () => api.post("duty.revoke_device", { user: x.user, reason: why })); }}>Revoke device</Btn>
            <Btn tone="danger" onClick={() => { const why = window.prompt("Reason for suspending ALL access"); if (why) act("User suspended", () => api.post("duty.suspend_user", { user: x.user, reason: why })); }}>Suspend</Btn></span> : "") }]} />
        {role === "org_admin" && <form className="inline" onSubmit={(e: FormEvent) => { e.preventDefault(); act("Role assigned", () => api.create("CPCP Role Assignment", { user, cpcp_role: r, estate: r === "org_admin" ? undefined : estate, valid_until: until || undefined })); }}>
          <input value={user} onChange={(e) => setUser(e.target.value)} placeholder="Person's email (account must exist)" required aria-label="Person email" />
          <select value={r} onChange={(e) => setR(e.target.value)} aria-label="Role">{ROLES.map((x) => <option key={x}>{x}</option>)}</select>
          <label>Expires <input type="date" value={until} onChange={(e) => setUntil(e.target.value)} /></label><button className="btn primary">Assign</button></form>}
      </Panel>}
      <Panel title="Gate shifts" note="A shift is the server's proof that someone is on duty at a gate on a registered device. It expires on its own.">
        <Table rows={shifts.data ?? []} cols={[{ key: "user", label: "Officer" }, { key: "gate", label: "Gate" }, { key: "status", label: "Status" }, { key: "started_at", label: "Started", render: (x) => fmt(x.started_at) }, { key: "ends_at", label: "Ends", render: (x) => fmt(x.ends_at) }, { key: "ended_reason", label: "Why ended" },
          { key: "a", label: "Actions", render: (x) => (manager && x.status === "On Duty" ? <span className="row-actions">
            <Btn onClick={() => { const why = window.prompt("Reason for revoking this officer's device"); if (why) act("Device revoked and sessions cleared", () => api.post("duty.revoke_device", { user: x.user, reason: why })); }}>Revoke device</Btn>
            <Btn tone="danger" onClick={() => { const why = window.prompt("Reason for suspending ALL access"); if (why) act("User suspended", () => api.post("duty.suspend_user", { user: x.user, reason: why })); }}>Suspend</Btn></span> : "") }]} />
      </Panel>
    </>
  );
}
