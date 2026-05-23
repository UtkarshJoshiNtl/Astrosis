// Mirrors the response shapes from the Astrosis FastAPI server (alpha branch
// + the extension patch shipped on /connect). All vectors are ECI km / km·s⁻¹
// unless noted; epochs are UTC ISO-8601.

export interface BackendHealth {
  backend: string; // "CUDA 12.9", "C++/OpenMP", "NumPy", "Python", or "OFFLINE-SGP4"
  backend_kind: "cuda" | "cpp" | "numpy" | "python" | "offline";
  engine_version: string;
  cuda_available: boolean;
  cuda_device?: string;
  ok: boolean;
}

export interface SatelliteRecord {
  id: number;
  name?: string;
  pos: [number, number, number]; // km, ECI
  vel?: [number, number, number]; // km/s, ECI
  altitude_km?: number;
  inclination_deg?: number;
  period_min?: number;
  speed_kms?: number;
  // optional Keplerian elements when backend ships them
  sma_km?: number;
  ecc?: number;
  raan_deg?: number;
  argp_deg?: number;
  mean_anom_deg?: number;
}

export interface ConstellationResponse {
  satellites: SatelliteRecord[];
  epoch: string; // ISO 8601
  source: "live" | "offline-sgp4";
  backend?: string;
  count: number;
}

export interface CatalogEntry {
  norad: number;
  name: string;
  tle: [string, string];
  elements: {
    epoch: string;
    sma_km: number;
    ecc: number;
    incl_deg: number;
    raan_deg: number;
    argp_deg: number;
    mean_anom_deg: number;
    period_min: number;
    apogee_km: number;
    perigee_km: number;
  };
}

export interface EphemerisPoint {
  t: string; // ISO
  pos: [number, number, number];
  vel: [number, number, number];
}

export interface PropagateResponse {
  norad?: number;
  ephemeris: EphemerisPoint[];
  dt_seconds: number;
  hours: number;
}

export interface PassPrediction {
  aos: string; // ISO
  los: string; // ISO
  max_el_deg: number;
  az_aos_deg: number;
  az_los_deg: number;
  duration_s: number;
}

export interface ConjunctionPair {
  a: number;
  b: number;
  tca: string;
  miss_km: number;
  rel_vel_kms: number;
  pc?: number; // Chan's collision probability (experimental)
}

export interface HohmannResult {
  r1_km: number;
  r2_km: number;
  dv1_kms: number;
  dv2_kms: number;
  dv_total_kms: number;
  transfer_time_s: number;
  fuel_used_kg?: number;
  fuel_remaining_kg?: number;
  mass_ratio?: number;
  isp_s?: number;
}