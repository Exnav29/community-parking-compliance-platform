// SPDX-License-Identifier: Apache-2.0
import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Err, Notice, Panel, Table, fmt, useLoad } from "../ui";

type Tab = "Residents" | "Units" | "Vehicles" | "Visitors";

export default function Registry({ estate, role }: { estate: string; role: string }) {
  const [tab, setTab] = useState<Tab>("Units");
  const canEdit = ["org_admin", "security_manager", "estate_manager"].includes(role);
  return (
    <>
      <Notice><strong>These records are personal data.</strong> Every time you open one of these lists it is recorded and independently reviewed. Gate staff cannot open this page; their lookups go through purpose-checked screens.</Notice>
      <div className="tabs" role="tablist">{(["Units", "Residents", "Vehicles", "Visitors"] as Tab[]).map((t) => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>{t}</button>)}</div>
      {tab === "Units" && <Units estate={estate} canEdit={canEdit} />}
      {tab === "Residents" && <Residents canEdit={canEdit} />}
      {tab === "Vehicles" && <Vehicles estate={estate} canEdit={canEdit} />}
      {tab === "Visitors" && <Visitors estate={estate} />}
    </>
  );
}

function useForm(onDone: () => void) {
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  return { err, ok, run: async (fn: () => Promise<unknown>, msg: string) => { setErr(""); setOk(""); try { await fn(); setOk(msg); onDone(); } catch (e) { setErr((e as Error).message); } } };
}

function Units({ estate, canEdit }: { estate: string; canEdit: boolean }) {
  const units = useLoad(() => api.list("CPCP Unit", ["name", "unit_label", "block", "occupancy_status"], { estate }), [estate]);
  const [label, setLabel] = useState("");
  const f = useForm(units.reload);
  return (
    <Panel title="Units">
      <Err msg={units.error || f.err} />{f.ok && <p className="ok" role="status">{f.ok}</p>}
      <Table rows={units.data ?? []} cols={[{ key: "unit_label", label: "Unit" }, { key: "block", label: "Block" }, { key: "occupancy_status", label: "Occupancy" }, { key: "name", label: "Record" }]} />
      {canEdit && <form className="inline" onSubmit={(e: FormEvent) => { e.preventDefault(); f.run(() => api.create("CPCP Unit", { estate, unit_label: label }), `Unit ${label.toUpperCase()} added`); setLabel(""); }}>
        <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="New unit, e.g. A5" required aria-label="New unit label" /><button className="btn primary">Add unit</button></form>}
    </Panel>
  );
}

function Residents({ canEdit }: { canEdit: boolean }) {
  const people = useLoad(() => api.list("CPCP Person", ["name", "full_name", "phone_e164", "active", "privacy_notice_status"]), []);
  const units = useLoad(() => api.list("CPCP Unit", ["name", "unit_label"], {}, 300), []);
  const [name, setName] = useState(""); const [phone, setPhone] = useState("");
  const [person, setPerson] = useState(""); const [unit, setUnit] = useState(""); const [kind, setKind] = useState("Owner"); const [primary, setPrimary] = useState(false);
  const f = useForm(people.reload);
  return (
    <Panel title="Residents" note="Numbers are shown only to roles that manage the register; officers see masked contact actions inside an assigned case only.">
      <Err msg={people.error || f.err} />{f.ok && <p className="ok" role="status">{f.ok}</p>}
      <Table rows={people.data ?? []} cols={[{ key: "full_name", label: "Name" }, { key: "phone_e164", label: "Phone" }, { key: "active", label: "Active", render: (r) => (r.active ? "yes" : "no") }, { key: "privacy_notice_status", label: "Notice" }, { key: "name", label: "Record" }]} />
      {canEdit && <>
        <form className="inline" onSubmit={(e: FormEvent) => { e.preventDefault(); f.run(() => api.create("CPCP Person", { full_name: name, phone_source: phone || undefined }), "Person added"); setName(""); setPhone(""); }}>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" required aria-label="Full name" />
          <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone (024... or +233...)" aria-label="Phone" /><button className="btn primary">Add person</button></form>
        <form className="inline" onSubmit={(e: FormEvent) => { e.preventDefault(); f.run(() => api.create("CPCP Unit Membership", { person, unit, membership_type: kind, is_primary_contact: primary ? 1 : 0, valid_from: new Date().toISOString().slice(0, 10) }), "Added to unit"); }}>
          <select value={person} onChange={(e) => setPerson(e.target.value)} required aria-label="Person"><option value="">Person...</option>{(people.data ?? []).map((p) => <option key={String(p.name)} value={String(p.name)}>{String(p.full_name)}</option>)}</select>
          <select value={unit} onChange={(e) => setUnit(e.target.value)} required aria-label="Unit"><option value="">Unit...</option>{(units.data ?? []).map((u) => <option key={String(u.name)} value={String(u.name)}>{String(u.unit_label)}</option>)}</select>
          <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Relationship">{["Owner", "Tenant", "Occupant", "Authorized Host"].map((k) => <option key={k}>{k}</option>)}</select>
          <label className="row"><input type="checkbox" checked={primary} onChange={(e) => setPrimary(e.target.checked)} /> primary contact</label><button className="btn">Assign to unit</button></form></>}
    </Panel>
  );
}

function Vehicles({ estate, canEdit }: { estate: string; canEdit: boolean }) {
  const veh = useLoad(() => api.list("CPCP Vehicle", ["name", "plate", "make", "color", "status"]), []);
  const units = useLoad(() => api.list("CPCP Unit", ["name", "unit_label"], { estate }, 300), [estate]);
  const [plate, setPlate] = useState(""); const [make, setMake] = useState(""); const [color, setColor] = useState(""); const [unit, setUnit] = useState("");
  const f = useForm(veh.reload);
  return (
    <Panel title="Registered vehicles" note="A plate is a search key, not an identity. Two active records for one plate must be resolved first.">
      <Err msg={veh.error || f.err} />{f.ok && <p className="ok" role="status">{f.ok}</p>}
      <Table rows={veh.data ?? []} cols={[{ key: "plate", label: "Plate" }, { key: "make", label: "Make" }, { key: "color", label: "Colour" }, { key: "status", label: "Status" }, { key: "name", label: "Record" }]} />
      {canEdit && <form className="inline" onSubmit={async (e: FormEvent) => {
        e.preventDefault();
        f.run(async () => { const v = await api.create("CPCP Vehicle", { plate, make, color }); await api.create("CPCP Vehicle Unit Association", { vehicle: v.name, unit, verification_status: "Verified" }); }, `Vehicle ${plate.toUpperCase()} registered`);
        setPlate(""); setMake(""); setColor("");
      }}>
        <input value={plate} onChange={(e) => setPlate(e.target.value)} placeholder="Plate" required aria-label="Plate" />
        <input value={make} onChange={(e) => setMake(e.target.value)} placeholder="Make" aria-label="Make" /><input value={color} onChange={(e) => setColor(e.target.value)} placeholder="Colour" aria-label="Colour" />
        <select value={unit} onChange={(e) => setUnit(e.target.value)} required aria-label="Household unit"><option value="">Unit...</option>{(units.data ?? []).map((u) => <option key={String(u.name)} value={String(u.name)}>{String(u.unit_label)}</option>)}</select>
        <button className="btn primary">Register vehicle</button></form>}
    </Panel>
  );
}

function Visitors({ estate }: { estate: string }) {
  const active = useLoad(() => api.get("visitors.active_visitors", { estate }), [estate]);
  const hist = useLoad(() => api.list("CPCP Visitor Session", ["name", "plate_snapshot", "host_unit_label", "category", "status", "presence", "entry_at", "exit_at", "duration_minutes", "estimated"], { estate }, 100), [estate]);
  return (
    <>
      <Panel title="Inside now (estimate)" note="Based on recorded arrivals and departures. Not a census of everyone on site."><Err msg={active.error} />
        <Table rows={(active.data ?? []) as Record<string, unknown>[]} empty="No visitors are recorded as inside." cols={[{ key: "plate", label: "Plate" }, { key: "host_unit", label: "Unit" }, { key: "category", label: "Type" }, { key: "entry_at", label: "In", render: (r) => fmt(r.entry_at) }, { key: "presence", label: "Presence" }]} /></Panel>
      <Panel title="Visit history" note="Verified durations exclude estimated or unconfirmed exits."><Err msg={hist.error} />
        <Table rows={hist.data ?? []} cols={[{ key: "plate_snapshot", label: "Plate" }, { key: "host_unit_label", label: "Unit" }, { key: "status", label: "Status" },
          { key: "entry_at", label: "In", render: (r) => fmt(r.entry_at) }, { key: "exit_at", label: "Out", render: (r) => fmt(r.exit_at) },
          { key: "duration_minutes", label: "Minutes", render: (r) => (r.estimated ? `~${r.duration_minutes ?? "?"} (estimated)` : String(r.duration_minutes ?? "")) }]} /></Panel>
    </>
  );
}
