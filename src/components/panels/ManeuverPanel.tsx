import { useState, useMemo, useEffect } from "react";
import { hohmannLocal } from "@/lib/astrosis/hohmann";
import { useConstellation } from "@/hooks/useAstrosisData";
import type { HohmannResult } from "@/lib/astrosis/types";

export function ManeuverPanel({ selectedId }: { selectedId: number | null }) {
  const constellation = useConstellation(30000);
  const satellites = constellation.data?.satellites ?? [];
  const selectedSat = useMemo(
    () => satellites.find((s) => s.id === selectedId),
    [satellites, selectedId],
  );

  const [r1, setR1] = useState("7171");
  useEffect(() => {
    setR1(selectedSat?.sma_km ? String(Math.round(selectedSat.sma_km)) : "7171");
  }, [selectedId, selectedSat?.sma_km]);
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
    return (
      <div className="p-4 text-[11px] text-muted-foreground">
        Select a satellite to plan a maneuver.
      </div>
    );
  }

  const insufficientProp = result?.fuel_remaining_kg != null && result.fuel_remaining_kg < 0;

  return (
    <div className="p-4 text-[11px] flex gap-4 h-full">
      <div className="w-[200px] shrink-0 space-y-2">
        <div className="tag mb-1">Hohmann Transfer</div>
        <div className="hairline" />
        <div className="space-y-1.5">
          <div>
            <label htmlFor="mp-r1" className="text-muted-foreground">
              r₁ (km)
            </label>
            <input
              id="mp-r1"
              className="w-full hairline bg-transparent px-1.5 py-0.5 num text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
              value={r1}
              onChange={(e) => setR1(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="mp-r2" className="text-muted-foreground">
              r₂ (km)
            </label>
            <input
              id="mp-r2"
              className="w-full hairline bg-transparent px-1.5 py-0.5 num text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
              value={r2}
              onChange={(e) => setR2(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="mp-isp" className="text-muted-foreground">
              Isp (s)
            </label>
            <input
              id="mp-isp"
              className="w-full hairline bg-transparent px-1.5 py-0.5 num text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
              value={isp}
              onChange={(e) => setIsp(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="mp-dry" className="text-muted-foreground">
              Dry mass (kg)
            </label>
            <input
              id="mp-dry"
              className="w-full hairline bg-transparent px-1.5 py-0.5 num text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
              value={dryMass}
              onChange={(e) => setDryMass(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="mp-prop" className="text-muted-foreground">
              Prop mass (kg)
            </label>
            <input
              id="mp-prop"
              className="w-full hairline bg-transparent px-1.5 py-0.5 num text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
              value={propMass}
              onChange={(e) => setPropMass(e.target.value)}
            />
          </div>
          <button
            onClick={calculate}
            className="w-full hairline px-2 py-1 text-foreground hover:bg-[var(--surface-2)]"
          >
            CALCULATE
          </button>
        </div>
      </div>

      <div className="flex-1 min-w-0 overflow-auto">
        {insufficientProp && (
          <div className="text-[var(--destructive)] font-medium mb-2">
            ⚠ INSUFFICIENT PROPELLANT
          </div>
        )}

        {result && !insufficientProp && (
          <div className="space-y-3 max-w-md">
            <div>
              <div className="tag mb-1">BURN SEQUENCE</div>
              <div className="surface-2 hairline">
                <Row label="Δv₁ (periapsis burn)" value={`+${result.dv1_kms.toFixed(4)} km/s`} />
                <Row label="Δv₂ (apoapsis burn)" value={`+${result.dv2_kms.toFixed(4)} km/s`} />
                <Row label="Δv total" value={`+${result.dv_total_kms.toFixed(4)} km/s`} />
                <Row
                  label="Transfer time"
                  value={`${(result.transfer_time_s / 3600).toFixed(1)} h`}
                />
              </div>
            </div>

            {result.fuel_used_kg != null && (
              <div>
                <div className="tag mb-1">PROPELLANT BUDGET</div>
                <div className="surface-2 hairline">
                  <Row label="Fuel used" value={`${result.fuel_used_kg.toFixed(1)} kg`} />
                  <Row
                    label="Fuel remaining"
                    value={`${result.fuel_remaining_kg?.toFixed(1) ?? "—"} kg`}
                  />
                </div>
                {result.fuel_remaining_kg != null &&
                  (() => {
                    const total = result.fuel_used_kg + result.fuel_remaining_kg;
                    const usedPct = total > 0 ? (result.fuel_used_kg / total) * 100 : 0;
                    return (
                      <div className="mt-1 h-3 surface-2 hairline relative">
                        <div
                          className="absolute inset-y-0 left-0 bg-[var(--primary)]"
                          style={{ width: `${Math.min(100, usedPct)}%` }}
                        />
                        <div
                          className="absolute inset-y-0 bg-[var(--border)]"
                          style={{ left: `${Math.min(100, usedPct)}%`, right: 0 }}
                        />
                      </div>
                    );
                  })()}
              </div>
            )}

            <div>
              <div className="tag mb-1">NEW ORBIT</div>
              <div className="surface-2 hairline">
                <Row label="Semi-major axis" value={`${result.r2_km.toFixed(0)} km`} />
                <Row
                  label="Period"
                  value={`${((2 * Math.PI * Math.sqrt(result.r2_km ** 3 / 398600.4418)) / 3600).toFixed(2)} h`}
                />
              </div>
            </div>
          </div>
        )}

        {!result && <div className="text-muted-foreground">Set parameters and calculate.</div>}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between hairline-b last:border-0 py-0.5 px-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="num text-foreground">{value}</span>
    </div>
  );
}
