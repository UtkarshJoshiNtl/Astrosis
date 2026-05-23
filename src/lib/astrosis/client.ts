import { getBackendUrl } from "./store";
import type {
  BackendHealth,
  ConstellationResponse,
  CatalogEntry,
  PropagateResponse,
  PassPrediction,
  ConjunctionPair,
  HohmannResult,
  SatelliteRecord,
} from "./types";

// All requests go to the FastAPI server the user runs locally (see /connect
// for the drop-in patch that exposes these endpoints).

const RE_KM = 6371.0;

function timeoutSignal(ms: number, outer?: AbortSignal): AbortSignal {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(new Error("timeout")), ms);
  outer?.addEventListener("abort", () => ctrl.abort(outer.reason), { once: true });
  // Best-effort: leak nothing if the caller drops the signal.
  const orig = ctrl.signal;
  orig.addEventListener("abort", () => clearTimeout(t), { once: true });
  return orig;
}

async function get<T>(path: string, opts: { timeoutMs?: number; signal?: AbortSignal } = {}): Promise<T> {
  const base = getBackendUrl();
  const res = await fetch(`${base}${path}`, {
    signal: timeoutSignal(opts.timeoutMs ?? 3500, opts.signal),
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown, opts: { timeoutMs?: number; signal?: AbortSignal } = {}): Promise<T> {
  const base = getBackendUrl();
  const res = await fetch(`${base}${path}`, {
    method: "POST",
    signal: timeoutSignal(opts.timeoutMs ?? 15000, opts.signal),
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// --- Enrichment ---------------------------------------------------
// The stock /api/constellation endpoint on alpha returns only positions.
// We compute altitude, speed, inclination (from h = r × v) when possible so
// the UI still has scientifically meaningful columns even before the user
// applies the patch on /connect.

export function enrichSatellite(raw: {
  id: number;
  name?: string;
  pos: [number, number, number];
  vel?: [number, number, number];
}): SatelliteRecord {
  const [x, y, z] = raw.pos;
  const r = Math.sqrt(x * x + y * y + z * z);
  const altitude_km = Math.max(0, r - RE_KM);
  let inclination_deg: number | undefined;
  let speed_kms: number | undefined;
  let period_min: number | undefined;
  if (raw.vel) {
    const [vx, vy, vz] = raw.vel;
    speed_kms = Math.sqrt(vx * vx + vy * vy + vz * vz);
    const hx = y * vz - z * vy;
    const hy = z * vx - x * vz;
    const hz = x * vy - y * vx;
    const hMag = Math.sqrt(hx * hx + hy * hy + hz * hz);
    if (hMag > 0) inclination_deg = (Math.acos(Math.max(-1, Math.min(1, hz / hMag))) * 180) / Math.PI;
    // Approx period from vis-viva: a = 1 / (2/r - v²/μ)
    const mu = 398600.4418;
    const v2 = speed_kms * speed_kms;
    const a = 1 / (2 / r - v2 / mu);
    if (a > 0) period_min = (2 * Math.PI * Math.sqrt((a * a * a) / mu)) / 60;
  }
  return {
    id: raw.id,
    name: raw.name,
    pos: raw.pos,
    vel: raw.vel,
    altitude_km,
    inclination_deg,
    period_min,
    speed_kms,
  };
}

// --- Endpoints ----------------------------------------------------

export async function fetchHealth(signal?: AbortSignal): Promise<BackendHealth> {
  // /api/health is part of the extension patch — fall back to probing
  // /api/constellation to know the server is at least up.
  try {
    return await get<BackendHealth>("/api/health", { timeoutMs: 1500, signal });
  } catch {
    // Probe the stock endpoint as a liveness check.
    await get("/api/constellation", { timeoutMs: 1500, signal });
    return {
      backend: "unknown (stock alpha endpoint detected)",
      backend_kind: "python",
      engine_version: "unknown",
      cuda_available: false,
      ok: true,
    };
  }
}

export async function fetchConstellation(signal?: AbortSignal): Promise<ConstellationResponse> {
  type Raw =
    | Array<{ id: number; pos: [number, number, number]; vel?: [number, number, number] }>
    | ConstellationResponse;
  const data = await get<Raw>("/api/constellation", { timeoutMs: 4000, signal });
  if (Array.isArray(data)) {
    // Stock alpha shape — array of {id,pos}. Enrich what we can.
    return {
      satellites: data.map(enrichSatellite),
      epoch: new Date().toISOString(),
      source: "live",
      count: data.length,
    };
  }
  // Patched shape from /connect — already structured.
  return {
    ...data,
    satellites: data.satellites.map((s) => enrichSatellite(s as never)),
    source: "live",
  };
}

export const fetchCatalogEntry = (norad: number, signal?: AbortSignal) =>
  get<CatalogEntry>(`/api/catalog/${norad}`, { timeoutMs: 8000, signal });

export const propagate = (
  body: { norad?: number; state?: number[]; hours: number; dt_seconds: number },
  signal?: AbortSignal,
) => post<PropagateResponse>("/api/propagate", body, { signal });

export const passes = (
  body: { norad: number; lat_deg: number; lon_deg: number; alt_m?: number; hours?: number },
  signal?: AbortSignal,
) => post<PassPrediction[]>("/api/passes", body, { signal });

export const conjunctions = (
  body: { norads: number[]; hours?: number; threshold_km?: number },
  signal?: AbortSignal,
) => post<ConjunctionPair[]>("/api/conjunctions", body, { signal });

export const hohmann = (
  body: {
    r1_km: number;
    r2_km: number;
    isp_s?: number;
    dry_mass_kg?: number;
    prop_mass_kg?: number;
  },
  signal?: AbortSignal,
) => post<HohmannResult>("/api/maneuver/hohmann", body, { signal });