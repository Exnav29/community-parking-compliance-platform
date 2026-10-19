// SPDX-License-Identifier: Apache-2.0
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import { api, type EstateCtx } from "../api";
import { Err, Notice, Panel, daysAgo, today, useLoad } from "../ui";

interface Pt { id: string; lat: number; lon: number; accuracy_m?: number; tier?: string; classification?: string; status?: string; date: string; category?: string; state?: string }
interface Hot { verified_incidents: { label: string; points: Pt[] }; allegations: { label: string; points: Pt[] }; zone_counts: Record<string, number>; caveat: string }

const TILE = (import.meta.env.VITE_TILE_URL as string | undefined) ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

export default function MapView({ estate, ctx }: { estate: string; ctx: EstateCtx | undefined }) {
  const [from, setFrom] = useState(daysAgo(90));
  const [to, setTo] = useState(today());
  const [cls, setCls] = useState("");
  const [showA, setShowA] = useState(false);
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layers = useRef<L.LayerGroup | null>(null);
  const { data, error } = useLoad<Hot>(() => api.get("reports.hotspots", { estate, date_from: from, date_to: to, classification: cls }), [estate, from, to, cls]);

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current).setView([5.605, -0.185], 17);
    L.tileLayer(TILE, { maxZoom: 20, attribution: "&copy; OpenStreetMap contributors" }).addTo(m);
    layers.current = L.layerGroup().addTo(m);
    map.current = m;
    return () => { m.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const m = map.current, g = layers.current;
    if (!m || !g || !data) return;
    g.clearLayers();
    const pts: L.LatLngExpression[] = [];
    if (ctx?.boundary?.coordinates?.[0]) {
      const ring = ctx.boundary.coordinates[0].map(([lon, lat]) => [lat, lon] as [number, number]);
      L.polygon(ring, { color: "#0b5cad", weight: 2, fill: false }).addTo(g);
      pts.push(...ring);
    }
    for (const p of data.verified_incidents.points) {
      const ll: [number, number] = [p.lat, p.lon]; pts.push(ll);
      // one marker per EPISODE; the circle shows the GPS accuracy so a pin never implies more precision than was achieved
      L.circle(ll, { radius: Math.max(p.accuracy_m ?? 10, 5), color: "#a30000", weight: 1, fillOpacity: 0.08 }).addTo(g);
      L.circleMarker(ll, { radius: 7, color: "#a30000", fillColor: "#e04040", fillOpacity: 0.9 })
        .bindPopup(`<strong>${p.id}</strong><br>${p.classification} - ${p.status}<br>${p.date}<br>accuracy: ${p.tier}`).addTo(g);
    }
    if (showA) for (const p of data.allegations.points) {
      const ll: [number, number] = [p.lat, p.lon]; pts.push(ll);
      L.circleMarker(ll, { radius: 5, color: "#555", dashArray: "3", fillOpacity: 0.2 }).bindPopup(`UNVERIFIED report<br>${p.category}<br>${p.date}`).addTo(g);
    }
    if (pts.length) m.fitBounds(L.latLngBounds(pts), { padding: [30, 30], maxZoom: 19 });
  }, [data, showA, ctx]);

  return (
    <Panel title="Violation map" note="Solid red = verified violations (one pin per parking episode, officer-confirmed). Grey dashed = unverified resident allegations (optional layer, kept separate)."
      actions={<span className="filters">
        <label>From <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <label>To <input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
        <select value={cls} onChange={(e) => setCls(e.target.value)} aria-label="Type"><option value="">All types</option><option>Ordinary</option><option>Emergency</option></select>
        <label className="row"><input type="checkbox" checked={showA} onChange={(e) => setShowA(e.target.checked)} /> show unverified allegations</label></span>}>
      <Err msg={error} />
      <div ref={el} className="map" role="application" aria-label="Estate map of verified violations" />
      {data && <p className="muted">{data.verified_incidents.points.length} verified episode(s){showA ? `, ${data.allegations.points.length} unverified report(s)` : ""} in range. {data.caveat}</p>}
      {data && Object.keys(data.zone_counts).length > 0 && <Notice>Verified episodes by zone: {Object.entries(data.zone_counts).map(([z, n]) => `${z}: ${n}`).join(", ")}</Notice>}
    </Panel>
  );
}
