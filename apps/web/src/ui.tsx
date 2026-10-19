// SPDX-License-Identifier: Apache-2.0
import { useEffect, useState, type ReactNode } from "react";
import { ApiError } from "./api";

export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState(true);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    setBusy(true);
    fn().then((d) => { if (live) { setData(d); setError(""); } })
      .catch((e) => { if (live) setError(e instanceof ApiError ? e.message : "Something went wrong"); })
      .finally(() => { if (live) setBusy(false); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, error, busy, reload: () => setTick((t) => t + 1) };
}

export function Panel({ title, children, note, actions }: { title: string; children: ReactNode; note?: string; actions?: ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-head"><h2>{title}</h2><div>{actions}</div></div>
      {note && <p className="muted">{note}</p>}
      {children}
    </section>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return <div className="stat"><div className="stat-v">{value}</div><div className="stat-l">{label}</div>{sub && <div className="stat-s">{sub}</div>}</div>;
}

export function Table({ cols, rows, empty = "Nothing to show." }: { cols: { key: string; label: string; render?: (r: Record<string, unknown>) => ReactNode }[]; rows: Record<string, unknown>[]; empty?: string }) {
  if (!rows.length) return <p className="muted">{empty}</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{cols.map((c) => <th key={c.key} scope="col">{c.label}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={String(r.name ?? r.id ?? i)}>{cols.map((c) => <td key={c.key}>{c.render ? c.render(r) : String(r[c.key] ?? "")}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

export const Err = ({ msg }: { msg: string }) => (msg ? <p role="alert" className="err">{msg}</p> : null);
export const Notice = ({ children }: { children: ReactNode }) => <p className="notice" role="note">{children}</p>;
export const Badge = ({ children, tone }: { children: ReactNode; tone?: "warn" | "ok" | "danger" }) => <span className={`badge ${tone ?? ""}`}>{children}</span>;

export function Btn({ onClick, children, tone, disabled }: { onClick: () => void; children: ReactNode; tone?: "primary" | "danger"; disabled?: boolean }) {
  return <button className={`btn ${tone ?? ""}`} onClick={onClick} disabled={disabled}>{children}</button>;
}

export const fmt = (iso?: unknown) => (iso ? new Date(String(iso)).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "-");
export const today = () => new Date().toISOString().slice(0, 10);
export const daysAgo = (n: number) => new Date(Date.now() - n * 86400000).toISOString().slice(0, 10);
