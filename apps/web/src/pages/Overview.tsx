// SPDX-License-Identifier: Apache-2.0
import { useState } from "react";
import { api } from "../api";
import { Err, Notice, Panel, Stat, useLoad, daysAgo, today } from "../ui";

interface Dash {
  range: { from: string; to: string };
  allegations: { submitted: number; verified: number; by_source: Record<string, number>; conversion_rate: { numerator: number; denominator: number; value: number | null }; note: string };
  episodes: { unique_incidents: number; verified_violations: number; duplicate_reports_linked: number; enforcement_actions_executed: Record<string, number>;
    repeat_vehicles_distinct_episodes: number; median_first_response_minutes: number | null; note: string };
  verified_incidents: { total: number; by_status: Record<string, number>; by_classification: Record<string, number> };
  compliance: { warned: number; corrected_without_fee: number; corrected_rate: { numerator: number; denominator: number | null; value: number | null } };
  visitors: { arrivals: number; inside_now_estimate: number; verified_duration_minutes: { count: number; median: number | null; max: number | null }; excluded_from_duration: number; caveat: string };
  communications: Record<string, number>;
  finance?: Record<string, { total: string; lines: number } | number>;
}

const pct = (v: number | null | undefined) => (v == null ? "n/a" : `${Math.round(v * 100)}%`);

export default function Overview({ estate }: { estate: string }) {
  const [from, setFrom] = useState(daysAgo(30));
  const [to, setTo] = useState(today());
  const { data: d, error, busy } = useLoad<Dash>(() => api.get("reports.dashboard", { estate, date_from: from, date_to: to }), [estate, from, to]);
  return (
    <>
      <Panel title="Overview" note="Every figure states what it counts. Allegations are unverified reports; incidents are physical parking episodes." actions={
        <span className="filters"><label>From <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
          <label>To <input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label></span>}>
        <Err msg={error} />
        {busy && !d && <p className="muted">Loading...</p>}
      </Panel>
      {d && <>
        <Panel title="Reports vs episodes" note={d.episodes.note}>
          <div className="stats">
            <Stat label="Allegations (reports)" value={d.allegations.submitted} sub={`identified ${d.allegations.by_source.Identified ?? 0} / anonymous submissions ${d.allegations.by_source.Anonymous ?? 0}`} />
            <Stat label="Unique incidents (episodes)" value={d.episodes.unique_incidents} />
            <Stat label="Duplicate reports linked to a case" value={d.episodes.duplicate_reports_linked} />
            <Stat label="Report-to-incident rate" value={pct(d.allegations.conversion_rate.value)} sub={`${d.allegations.conversion_rate.numerator} of ${d.allegations.conversion_rate.denominator}`} />
            <Stat label="Repeat vehicles (2+ distinct episodes)" value={d.episodes.repeat_vehicles_distinct_episodes} />
            <Stat label="Median first response" value={d.episodes.median_first_response_minutes == null ? "n/a" : `${d.episodes.median_first_response_minutes} min`} />
          </div>
          <Notice>{d.allegations.note} Anonymous submissions are counted as submissions, never as distinct people.</Notice>
        </Panel>
        <Panel title="Compliance and enforcement">
          <div className="stats">
            <Stat label="Warned (clock started)" value={d.compliance.warned} />
            <Stat label="Corrected without a fee" value={d.compliance.corrected_without_fee} sub={`rate ${pct(d.compliance.corrected_rate.value)} of ${d.compliance.corrected_rate.denominator ?? 0} warned`} />
            {Object.entries(d.episodes.enforcement_actions_executed).map(([k, v]) => <Stat key={k} label={`${k} actions executed`} value={v} />)}
            {Object.entries(d.verified_incidents.by_status).map(([k, v]) => <Stat key={k} label={`Status: ${k.replace(/_/g, " ")}`} value={v} />)}
          </div>
          {!Object.keys(d.episodes.enforcement_actions_executed).length && <p className="muted">No clamp or tow has been executed. Enforcement stays switched off until legal approval is recorded.</p>}
        </Panel>
        <Panel title="Gate" note={d.visitors.caveat}>
          <div className="stats">
            <Stat label="Visitor arrivals" value={d.visitors.arrivals} />
            <Stat label="Inside now (estimate)" value={d.visitors.inside_now_estimate} />
            <Stat label="Median verified stay" value={d.visitors.verified_duration_minutes.median == null ? "n/a" : `${d.visitors.verified_duration_minutes.median} min`} sub={`${d.visitors.verified_duration_minutes.count} verified, ${d.visitors.excluded_from_duration} excluded`} />
          </div>
        </Panel>
        <Panel title="Communications" note="Attempts, officer-reported results and provider-confirmed results are different things and are never merged.">
          <div className="stats">
            {Object.entries(d.communications).map(([k, v]) => <Stat key={k} label={k.replace(/_/g, " ")} value={v} />)}
          </div>
        </Panel>
        {d.finance && <Panel title="Enforcement ledger (finance roles only)" note="Penalty, towing and storage are separate lines. One base penalty per episode.">
          <div className="stats">
            {Object.entries(d.finance).map(([k, v]) => typeof v === "number" ? <Stat key={k} label={k.replace(/_/g, " ")} value={v} /> : <Stat key={k} label={k} value={v.total} sub={`${v.lines} line(s)`} />)}
          </div>
        </Panel>}
      </>}
    </>
  );
}
