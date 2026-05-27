import * as satellite from "satellite.js";
import type { ConstellationResponse, SatelliteRecord } from "./types";
import { enrichSatellite } from "./client";

// SGP4 fallback used only when the Astrosis engine is unreachable.
// Clearly labelled in the UI as "OFFLINE · SGP4 reference" so nothing
// is silently faked. Same data source the engine uses (Celestrak TLEs),
// just propagated in the browser via a reference SGP4 implementation.

export interface ParsedTLE {
  name: string;
  line1: string;
  line2: string;
  satrec: ReturnType<typeof satellite.twoline2satrec>;
  norad: number;
}

export function parseTLEs(text: string, limit?: number): ParsedTLE[] {
  const out: ParsedTLE[] = [];
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length - 2; i++) {
    const a = lines[i].trim();
    const b = lines[i + 1].trim();
    const c = lines[i + 2].trim();
    if (!b.startsWith("1 ") || !c.startsWith("2 ")) continue;
    try {
      const satrec = satellite.twoline2satrec(b, c);
      const norad = parseInt(b.substring(2, 7).trim(), 10);
      if (Number.isFinite(norad)) {
        out.push({ name: a || `OBJ-${norad}`, line1: b, line2: c, satrec, norad });
        i += 2;
        if (limit && out.length >= limit) break;
      }
    } catch {
      /* skip malformed */
    }
  }
  return out;
}

export function propagateAt(tle: ParsedTLE, when: Date): SatelliteRecord | null {
  const pv = satellite.propagate(tle.satrec, when);
  if (!pv || typeof pv.position === "boolean" || typeof pv.velocity === "boolean") return null;
  const p = pv.position as { x: number; y: number; z: number };
  const v = pv.velocity as { x: number; y: number; z: number };
  return enrichSatellite({
    id: tle.norad,
    name: tle.name,
    pos: [p.x, p.y, p.z],
    vel: [v.x, v.y, v.z],
  });
}

export function propagateAll(tles: ParsedTLE[], when: Date): SatelliteRecord[] {
  const out: SatelliteRecord[] = [];
  for (const t of tles) {
    const r = propagateAt(t, when);
    if (r) out.push(r);
  }
  return out;
}

export async function fetchTLEs(group = "active", signal?: AbortSignal): Promise<ParsedTLE[]> {
  // Goes through our same-origin server route to avoid Celestrak CORS.
  const res = await fetch(`/api/public/tle?group=${encodeURIComponent(group)}`, {
    signal,
    headers: { Accept: "text/plain" },
  });
  if (!res.ok) throw new Error(`TLE proxy ${res.status}`);
  return parseTLEs(await res.text(), 600);
}

export function generateSyntheticSeeds(count = 500): SatelliteRecord[] {
  const out: SatelliteRecord[] = [];
  const now = Date.now();
  for (let i = 0; i < count; i++) {
    const inc = 50 + Math.random() * 50;
    const raan = Math.random() * 360;
    const a = 6371 + 400 + Math.random() * 500;
    const M = Math.random() * 360;
    const r = a;
    const x =
      r *
      (Math.cos((M * Math.PI) / 180) * Math.cos((raan * Math.PI) / 180) -
        Math.sin((M * Math.PI) / 180) *
          Math.sin((raan * Math.PI) / 180) *
          Math.cos((inc * Math.PI) / 180));
    const y =
      r *
      (Math.cos((M * Math.PI) / 180) * Math.sin((raan * Math.PI) / 180) +
        Math.sin((M * Math.PI) / 180) *
          Math.cos((raan * Math.PI) / 180) *
          Math.cos((inc * Math.PI) / 180));
    const z = r * Math.sin((M * Math.PI) / 180) * Math.sin((inc * Math.PI) / 180);
    out.push({
      id: i,
      name: `DEMO-${i}`,
      pos: [x, y, z],
      altitude_km: a - 6371,
      inclination_deg: inc,
      period_min: (2 * Math.PI * Math.sqrt((a * a * a) / 398600.4418)) / 60,
      speed_kms: Math.sqrt(398600.4418 / a),
    });
  }
  return out;
}

export async function offlineConstellation(group = "active"): Promise<ConstellationResponse> {
  let satellites: SatelliteRecord[];
  let source: "live" | "offline-sgp4" = "offline-sgp4";
  let backend = "OFFLINE · SGP4 reference (satellite.js)";
  try {
    const tles = await fetchTLEs(group);
    const now = new Date();
    satellites = propagateAll(tles, now);
  } catch {
    satellites = generateSyntheticSeeds(500);
    source = "offline-sgp4";
    backend = "OFFLINE · CELESTRAK UNAVAILABLE · DEMO MODE";
  }
  return {
    satellites,
    epoch: new Date().toISOString(),
    source,
    backend,
    count: satellites.length,
  };
}

// Sub-satellite point + simple visibility footprint for ground-track plots.
export interface GroundPoint {
  lat_deg: number;
  lon_deg: number;
  alt_km: number;
}

export function eciToGeodetic(pos: [number, number, number], when: Date): GroundPoint {
  const gmst = satellite.gstime(when);
  const g = satellite.eciToGeodetic({ x: pos[0], y: pos[1], z: pos[2] }, gmst);
  return {
    lat_deg: satellite.degreesLat(g.latitude),
    lon_deg: satellite.degreesLong(g.longitude),
    alt_km: g.height,
  };
}
