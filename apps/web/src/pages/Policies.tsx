// SPDX-License-Identifier: Apache-2.0
import { useState, type FormEvent } from "react";
import { api, type Me } from "../api";
import { Badge, Btn, Err, Notice, Panel, Table, useLoad } from "../ui";

export default function Policies({ role, me }: { role: string; me: Me }) {
  const pol = useLoad(() => api.list("CPCP Policy Version", ["name", "version_label", "status", "grace_minutes", "violation_penalty", "storage_rate_per_period", "created_by_user", "approved_by"], {}, 50), []);
  const [label, setLabel] = useState(""); const [grace, setGrace] = useState("15"); const [pen, setPen] = useState(""); const [sto, setSto] = useState("");
  const [err, setErr] = useState(""); const [ok, setOk] = useState("");
  const admin = role === "org_admin";
  const run = async (m: string, fn: () => Promise<unknown>) => { setErr(""); setOk(""); try { await fn(); setOk(m); pol.reload(); } catch (e) { setErr((e as Error).message); } };
  const g = me.enforcement_gates;
  return (
    <>
      <Panel title="Legal and policy gates" note="Switching any of these on needs a recorded legal approval reference and is audited. Setting a fee does not give legal authority.">
        <div className="gates">{Object.entries(g).map(([k, v]) => <Badge key={k} tone={v ? "warn" : "ok"}>{k.replace(/_enabled$/, "").replace(/_/g, " ")}: {v ? "ON" : "off"}</Badge>)}</div>
        {Object.values(g).every((v) => !v) && <p className="muted">Everything that can fine, clamp, tow or collect money is off. Release and cancellation remain possible at all times.</p>}
      </Panel>
      <Panel title="Policy versions" note="Draft -> approved -> active. The approver must be a different person from the author. Active versions are frozen; each incident keeps the policy it was opened under.">
        <Err msg={err || pol.error} />{ok && <p role="status" className="ok">{ok}</p>}
        <Table rows={pol.data ?? []} cols={[{ key: "version_label", label: "Version" }, { key: "status", label: "Status", render: (r) => <Badge tone={r.status === "Active" ? "ok" : undefined}>{String(r.status)}</Badge> },
          { key: "grace_minutes", label: "Grace (min)" }, { key: "violation_penalty", label: "Base penalty" }, { key: "storage_rate_per_period", label: "Storage / period" }, { key: "created_by_user", label: "Author" }, { key: "approved_by", label: "Approver" },
          { key: "a", label: "", render: (r) => (admin && r.status === "Draft" ? <Btn onClick={() => run("Activated (server checks the approver is independent)", () => api.update("CPCP Policy Version", String(r.name), { status: "Active" }))}>Approve and activate</Btn> : "") }]} />
        {admin && <form className="inline" onSubmit={(e: FormEvent) => { e.preventDefault(); run("Draft saved", () => api.create("CPCP Policy Version", { version_label: label, grace_minutes: Number(grace), violation_penalty: pen === "" ? undefined : Number(pen), storage_rate_per_period: sto === "" ? undefined : Number(sto), status: "Draft" })); }}>
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Version name" required aria-label="Version name" />
          <label>Grace minutes <input type="number" min={1} value={grace} onChange={(e) => setGrace(e.target.value)} /></label>
          <input type="number" min={0} value={pen} onChange={(e) => setPen(e.target.value)} placeholder="Base penalty (blank = not set)" aria-label="Base penalty" />
          <input type="number" min={0} value={sto} onChange={(e) => setSto(e.target.value)} placeholder="Storage rate (blank = not set)" aria-label="Storage rate" /><button className="btn primary">Save draft</button></form>}
        <Notice>No fee is ever assumed. A blank amount means "not configured" and blocks any charge that needs it.</Notice>
      </Panel>
    </>
  );
}
