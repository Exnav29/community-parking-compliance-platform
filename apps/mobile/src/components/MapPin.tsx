// SPDX-License-Identifier: Apache-2.0
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";

export interface Pin { lat: number; lon: number }

const TILE = (import.meta.env.VITE_TILE_URL as string | undefined) ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

/**
 * Draggable vehicle pin over the estate boundary. The device reading and the confirmed vehicle pin are separate
 * values: callers keep the raw fix and only the officer moves the pin (PRD 7). Without network tiles the map is blank
 * but the pin and coordinates still work (manual location fallback).
 */
export default function MapPin({ pin, onChange, boundary, deviceFix }: {
  pin: Pin; onChange: (p: Pin) => void; boundary?: number[][][] | null; deviceFix?: Pin | null;
}) {
  const el = useRef<HTMLDivElement>(null);
  const marker = useRef<L.Marker | null>(null);
  const map = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { zoomControl: true, attributionControl: true }).setView([pin.lat, pin.lon], 19);
    L.tileLayer(TILE, { maxZoom: 20, attribution: "&copy; OpenStreetMap contributors" }).addTo(m);
    if (boundary?.[0]) L.polygon(boundary[0].map(([lon, lat]) => [lat, lon] as [number, number]), { color: "#0b5cad", weight: 2, fill: false }).addTo(m);
    if (deviceFix) L.circleMarker([deviceFix.lat, deviceFix.lon], { radius: 6, color: "#555", fillOpacity: 0.6 }).bindTooltip("Your phone").addTo(m);
    const icon = L.divIcon({ className: "pin", html: "<span aria-hidden='true'>&#128663;</span>", iconSize: [36, 36], iconAnchor: [18, 18] });
    const mk = L.marker([pin.lat, pin.lon], { draggable: true, icon, title: "Vehicle position" }).addTo(m);
    mk.on("dragend", () => { const p = mk.getLatLng(); onChange({ lat: p.lat, lon: p.lng }); });
    m.on("click", (e: L.LeafletMouseEvent) => { mk.setLatLng(e.latlng); onChange({ lat: e.latlng.lat, lon: e.latlng.lng }); });
    marker.current = mk; map.current = m;
    return () => { m.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { marker.current?.setLatLng([pin.lat, pin.lon]); }, [pin.lat, pin.lon]);
  return <div ref={el} className="map" role="application" aria-label="Map. Tap or drag to place the vehicle position." />;
}
