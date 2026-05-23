import type { HohmannResult } from "./types";

// Browser-side Hohmann transfer, used when the backend is offline.
// Pure vis-viva + Tsiolkovsky — no external libs.

const MU_EARTH = 398600.4418; // km³/s²
const G0 = 9.80665; // m/s²

export function hohmannLocal(input: {
  r1_km: number;
  r2_km: number;
  isp_s?: number;
  dry_mass_kg?: number;
  prop_mass_kg?: number;
}): HohmannResult {
  const { r1_km, r2_km } = input;
  const a_t = (r1_km + r2_km) / 2;
  const v1 = Math.sqrt(MU_EARTH / r1_km);
  const v2 = Math.sqrt(MU_EARTH / r2_km);
  const v_p = Math.sqrt(MU_EARTH * (2 / r1_km - 1 / a_t));
  const v_a = Math.sqrt(MU_EARTH * (2 / r2_km - 1 / a_t));
  const dv1 = Math.abs(v_p - v1);
  const dv2 = Math.abs(v2 - v_a);
  const dv_total = dv1 + dv2;
  const transfer_time_s = Math.PI * Math.sqrt((a_t * a_t * a_t) / MU_EARTH);

  const out: HohmannResult = {
    r1_km,
    r2_km,
    dv1_kms: dv1,
    dv2_kms: dv2,
    dv_total_kms: dv_total,
    transfer_time_s,
  };

  if (input.isp_s && input.dry_mass_kg != null && input.prop_mass_kg != null) {
    const m0 = input.dry_mass_kg + input.prop_mass_kg;
    const ve = input.isp_s * G0; // m/s
    const dv_mps = dv_total * 1000;
    const mass_ratio = Math.exp(dv_mps / ve);
    const m_final = m0 / mass_ratio;
    const fuel_used = m0 - m_final;
    out.isp_s = input.isp_s;
    out.mass_ratio = mass_ratio;
    out.fuel_used_kg = fuel_used;
    out.fuel_remaining_kg = Math.max(0, input.prop_mass_kg - fuel_used);
  }

  return out;
}

export { MU_EARTH };