import { useState } from "react";
import { hohmannLocal } from "@/lib/astrosis/hohmann";
import type { HohmannResult } from "@/lib/astrosis/types";

export function ManeuverPanel({ selectedId }: { selectedId: number | null }) {
  const [r1, setR1] = useState("7171");
  const [r2, setR2] = useState("42164");
  const [isp, setIsp] = useState("300");
  const [dryMass, setDryMass] = useState("1000");
  const [propMass, setPropMass] = useState("500");
  const [result, setResult] = useState<HohmannResult | null>(null);

  function calculate() {
    setResult(
      hohmannLocal({
        r1_km: parseFloat(r1) || 7171,
        r2_km: parseFloat(r2) || 42164,
        isp_s: parseFloat(isp) || undefined,
        dry_mass_kg: parseFloat(dryMass) || undefined,
        prop_mass_kg: parseFloat(propMass) || undefined,
      }),
    );
  }

  if (!selectedId) {
    return <div className="p-4 text-[11px] text-muted-foreground">Select a satellite to plan a maneuver.</div>;
  }

  return (
    <div className="p-4 text-[11px] space-y-3">
      <div className="flex gap-2 flex-wrap">
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground">r₁ (km)</span>
          <input className="w-20 hairline bg-transparent px-1.5 py-0.5 num text-foreground" value={r1} onChange={(e) => setR1(e.target.value)} />
        </div>
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground">r₂ (km)</span>
          <input className="w-20 hairline bg-transparent px-1.5 py-0.5 num text-foreground" value={r2} onChange={(e) => setR2(e.target.value)} />
        </div>
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground">Isp (s)</span>
          <input className="w-16 hairline bg-transparent px-1.5 py-0.5 num text-foreground" value={isp} onChange={(e) => setIsp(e.target.value)} />
        </div>
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground">Dry (kg)</span>
          <input className="w-20 hairline bg-transparent px-1.5 py-0.5 num text-foreground" value={dryMass} onChange={(e) => setDryMass(e.target.value)} />
        </div>
        <div className="flex items-center gap-1">
          <span className="text-muted-foreground">Prop (kg)</span>
          <input className="w-20 hairline bg-transparent px-1.5 py-0.5 num text-foreground" value={propMass} onChange={(e) => setPropMass(e.target.value)} />
        </div>
        <button onClick={calculate} className="hairline px-2 py-0.5 text-foreground hover:bg-[var(--surface-2)]">Calc</button>
      </div>

      {result && (
        <div className="surface-2 hairline p-3 space-y-1">
          <Row label="Δv₁" value={`${result.dv1_kms.toFixed(4)} km/s`} />
          <Row label="Δv₂" value={`${result.dv2_kms.toFixed(4)} km/s`} />
          <Row label="Δv total" value={`${result.dv_total_kms.toFixed(4)} km/s`} />
          <Row label="Transfer time" value={`${(result.transfer_time_s / 3600).toFixed(1)} h`} />
          {result.fuel_used_kg != null && <Row label="Fuel used" value={`${result.fuel_used_kg.toFixed(1)} kg`} />}
          {result.fuel_remaining_kg != null && <Row label="Fuel remaining" value={`${result.fuel_remaining_kg.toFixed(1)} kg`} />}
          {result.mass_ratio != null && <Row label="Mass ratio" value={result.mass_ratio.toFixed(3)} />}
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between hairline-b last:border-0 py-0.5">
      <span className="text-muted-foreground">{label}</span>
      <span className="num text-foreground">{value}</span>
    </div>
  );
}
