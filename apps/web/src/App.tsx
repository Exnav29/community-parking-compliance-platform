// SPDX-License-Identifier: Apache-2.0
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, type EstateCtx, type Me } from "./api";
import AccessReview from "./pages/AccessReview";
import Cases from "./pages/Cases";
import MapView from "./pages/MapView";
import Overview from "./pages/Overview";
import Policies from "./pages/Policies";
import Registry from "./pages/Registry";
import Staff from "./pages/Staff";
import { Err, Notice } from "./ui";

import { pagesFor, type PageKey } from "./nav";

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [estates, setEstates] = useState<EstateCtx[]>([]);
  const [estate, setEstate] = useState("");
  const [page, setPage] = useState<PageKey>("overview");
  const [state, setState] = useState<"loading" | "login" | "ready">("loading");
  const [error, setError] = useState("");

  const boot = useCallback(async () => {
    try {
      const m = (await api.get("session.whoami")) as Me;
      const e = (await api.get("ops.estate_context")) as EstateCtx[];
      setMe(m); setEstates(e); setEstate((cur) => cur || e[0]?.estate || "");
      const first = pagesFor(m)[0];
      if (first) setPage(first.key);
      setState("ready");
    } catch { setState("login"); }
  }, []);
  useEffect(() => { boot(); }, [boot]);

  async function login(ev: FormEvent<HTMLFormElement>) {
    ev.preventDefault(); setError("");
    const f = new FormData(ev.currentTarget);
    try { await api.login(String(f.get("usr")), String(f.get("pwd"))); await boot(); } catch (e) { setError((e as Error).message || "Sign-in failed"); }
  }

  if (state === "loading") return <main><p className="muted">Loading...</p></main>;
  if (state === "login" || !me) return (
    <div className="login panel">
      <h1>CPCP Management Console</h1>
      <form onSubmit={login}>
        <label>Email<input name="usr" type="email" autoComplete="username" required /></label>
        <label>Password<input name="pwd" type="password" autoComplete="current-password" required /></label>
        <button className="btn primary">Sign in</button><Err msg={error} />
      </form>
      <p className="muted">For association management, security supervisors, finance and designated auditors. Security officers and residents use the mobile app.</p>
    </div>
  );

  const pages = pagesFor(me);
  const cur = pages.find((p) => p.key === page) ?? pages[0];
  const ectx = estates.find((e) => e.estate === estate);
  return (
    <div className="shell">
      <nav className="side" aria-label="Main">
        <h1>{me.display_name}</h1>
        <small>{me.active_role.replace("_", " ")}</small>
        {estates.length > 1 && <select value={estate} onChange={(e) => setEstate(e.target.value)} aria-label="Estate">{estates.map((e) => <option key={e.estate} value={e.estate}>{e.name}</option>)}</select>}
        {estates.length === 1 && <small>{estates[0].name}</small>}
        {pages.map((p) => <button key={p.key} className={cur?.key === p.key ? "on" : ""} onClick={() => setPage(p.key)}>{p.label}</button>)}
        <button onClick={async () => { await api.logout(); setMe(null); setState("login"); }}>Sign out</button>
        <Notice>Access to personal data is recorded and reviewed.</Notice>
      </nav>
      <main>
        {!cur && <Notice>Your role has no pages in this console. Security officers and residents use the mobile app.</Notice>}
        {cur?.key === "overview" && <Overview estate={estate} />}
        {cur?.key === "cases" && <Cases estate={estate} role={me.active_role} />}
        {cur?.key === "map" && <MapView estate={estate} ctx={ectx} />}
        {cur?.key === "registry" && <Registry estate={estate} role={me.active_role} />}
        {cur?.key === "staff" && <Staff estate={estate} role={me.active_role} />}
        {cur?.key === "policies" && <Policies role={me.active_role} me={me} />}
        {cur?.key === "access" && <AccessReview role={me.active_role} />}
      </main>
    </div>
  );
}
