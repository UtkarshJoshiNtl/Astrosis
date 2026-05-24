import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { PageShell } from "@/components/shell/Chrome";
import { hohmannLocal } from "@/lib/astrosis/hohmann";
import { hohmann } from "@/lib/astrosis/client";
import { useHealth } from "@/hooks/useAstrosisData";
import type { HohmannResult } from "@/lib/astrosis/types";

export const Route = createFileRoute("/maneuver")({
  component: ManeuverPage,
});

function ManeuverPage() {
  const health = useHealth();
  const backendLabel = health.data?.backend ?? "OFFLINE";
  const isOnline = health.data?.ok ?? false;

  const [r1, setR1] = useState("7171");
  const [r2, setR2] = useState("42164");
  const [isp, setIsp] = useState("300");
  const [dryMass, setDryMass] = useState("1000");
  const [propMass, setPropMass] = useState("500");
  const [result, setResult] = useState<HohmannResult | null>(null);

  function calculate() {
    const input = {
      r1_km: parseFloat(r1),
      r2_km: parseFloat(r2),
      isp_s: parseFloat(isp) || undefined,
      dry_mass_kg: parseFloat(dryMass) || undefined,
      prop_mass_kg: parseFloat(propMass) || undefined,
    };
    if (!isOnline) {
      setResult(hohmannLocal(input));
    } else {
      hohmann(input).then(setResult).catch(() => setResult(hohmannLocal(input)));
    }
  }

  return (
    <PageShell backendLabel={backendLabel} health={health.data}>
      <div className="h-full flex">
        <div className="w-72 p-4 surface hairline-r space-y-3 text-[11px]">
          <h2 className="tag mb-2">Hohmann Transfer</h2>
          <div>
            <label className="text-muted-foreground">Source radius (km)</label>
            <input className="w-full hairline bg-transparent px-2 py-1 num text-foreground" value={r1} onChange={(e) => setR1(e.target.value)} />
          </div>
          <div>
            <label className="text-muted-foreground">Target radius (km)</label>
            <input className="w-full hairline bg-transparent px-2 py-1 num text-foreground" value={r2} onChange={(e) => setR2(e.target.value)} />
          </div>
          <div>
            <label className="text-muted-foreground">Isp (s)</label>
            <input className="w-full hairline bg-transparent px-2 py-1 num text-foreground" value={isp} onChange={(e) => setIsp(e.target.value)} />
          </div>
          <div>
            <label className="text-muted-foreground">Dry mass (kg)</label>
            <input className="w-full hairline bg-transparent px-2 py-1 num text-foreground" value={dryMass} onChange={(e) => setDryMass(e.target.value)} />
          </div>
          <div>
            <label className="text-muted-foreground">Propellant mass (kg)</label>
            <input className="w-full hairline bg-transparent px-2 py-1 num text-foreground" value={propMass} onChange={(e) => setPropMass(e.target.value)} />
          </div>
          <button onClick={calculate} className="w-full hairline px-3 py-1.5 text-foreground hover:bg-[var(--surface-2)]">
            Calculate
          </button>
          <div className="text-[10px] text-muted-foreground italic">
            Fixed-step RK4 limitations apply. Not for operational use.
          </div>
        </div>
        <div className="flex-1 p-4 overflow-auto">
          {result && (
            <div className="space-y-4 text-[11px] max-w-lg">
              <h3 className="tag">Results</h3>
              <div className="space-y-1.5">
                <Row label="Δv₁ (periapsis)" value={`${result.dv1_kms.toFixed(4)} km/s`} />
                <Row label="Δv₂ (apoapsis)" value={`${result.dv2_kms.toFixed(4)} km/s`} />
                <Row label="Δv total" value={`${result.dv_total_kms.toFixed(4)} km/s`} />
                <Row label="Transfer time" value={`${(result.transfer_time_s / 3600).toFixed(1)} h`} />
                {result.fuel_used_kg != null && (
                  <Row label="Fuel used" value={`${result.fuel_used_kg.toFixed(1)} kg`} />
                )}
                {result.fuel_remaining_kg != null && (
                  <Row label="Fuel remaining" value={`${result.fuel_remaining_kg.toFixed(1)} kg`} />
                )}
                {result.mass_ratio != null && (
                  <Row label="Mass ratio" value={result.mass_ratio.toFixed(3)} />
                )}
              </div>
              {result.fuel_used_kg != null && result.fuel_remaining_kg != null && (
                <div className="hairline p-3">
                  <div className="flex justify-between text-muted-foreground mb-1">
                    <span>Fuel remaining</span>
                    <span>{result.fuel_remaining_kg.toFixed(0)} kg</span>
                  </div>
                  <div className="h-2 surface-2 relative">
                    {(() => {
                      const total = result.fuel_used_kg! + result.fuel_remaining_kg!;
                      const pct = total > 0 ? (result.fuel_remaining_kg! / total) * 100 : 0;
                      return (
                        <div className="absolute inset-y-0 left-0 bg-[var(--primary)]" style={{ width: `${100 - pct}%` }} />
                      );
                    })()}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </PageShell>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between hairline-b py-1">
      <span className="text-muted-foreground">{label}</span>
      <span className="num text-foreground">{value}</span>
    </div>
  );
}
