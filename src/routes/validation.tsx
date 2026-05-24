import { createFileRoute } from "@tanstack/react-router";
import { PageShell, useUtcClock } from "@/components/shell/Chrome";
import { useHealth } from "@/hooks/useAstrosisData";

export const Route = createFileRoute("/validation")({
  component: ValidationPage,
});

const PLOTS = [
  {
    id: "1_energy_conservation",
    title: "Energy Conservation Plot",
    caption: "24-hour LEO propagation (1,000 satellites, 400 km altitude, circular orbits). RK4 at dt=10s (86,400 steps). Relative energy drift: 9.1 × 10⁻⁹ — better than theoretical O(dt⁴) bound of 1 × 10⁻⁷.",
    status: "pass" as const,
    statusText: "Δε/ε < 1e-7 over 24h",
  },
  {
    id: "2_sgp4_comparison",
    title: "ISS vs SGP4 Plot",
    caption: "ISS (NORAD 25544) propagated for 24 hours. Position error growth is expected due to TLE uncertainty (0.1–1 km inherent). Astrosis validation: perturbation model behaves consistently with SGP4.",
    status: "note" as const,
    statusText: "error > 10km (drag/SRP expected)",
  },
  {
    id: "3_raan_precession",
    title: "RAAN Precession Plot",
    caption: "Circular 700 km LEO, 60° inclination, 7 days. Analytical dΩ/dt = -3.14°/day. RK4: -3.11°/day. Error: +0.96% — J₂ gravity model correctly integrated.",
    status: "pass" as const,
    statusText: "error 0.96% vs analytical",
  },
  {
    id: "4_rk4_convergence",
    title: "RK4 Convergence Plot",
    caption: "Richardson extrapolation: error ratio ≈ 16 per dt halving confirms 4th-order accuracy (2⁴ = 16). Position error at dt=1.25s: 3.2 × 10⁻⁸ km.",
    status: "pass" as const,
    statusText: "slope = 4.19 (ideal 4.0)",
  },
  {
    id: "5_srp_divergence",
    title: "Solar Radiation Pressure Divergence",
    caption: "Low-mass (2 kg/m²) vs. high-mass (100 kg/m²) satellite. SRP acceleration ratio: 50× (exact match). 24h displacement: 1.9 km (low) vs. 38 m (high).",
    status: "pass" as const,
    statusText: "50× ratio (exact match)",
  },
];

const GITHUB_RAW = "https://raw.githubusercontent.com/UtkarshJoshiNtl/Astrosis/alpha/validation/plots";

function ValidationPage() {
  const health = useHealth();
  const utc = useUtcClock();
  const backendLabel = health.data?.backend ?? "—";

  return (
    <PageShell backendLabel={backendLabel} health={health.data}>
      <div className="h-full flex flex-col p-4 overflow-auto">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-sm font-semibold">Validation Gallery</h1>
          <span className="tag">{utc}</span>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {PLOTS.map((plot) => (
            <div key={plot.id} className="surface hairline p-3 relative">
              <div className="absolute top-2 right-2 flex items-center gap-1 px-1.5 py-0.5 hairline text-[10px] font-mono"
                style={{
                  background: plot.status === "pass" ? "rgba(74, 158, 107, 0.15)" : "rgba(200, 136, 42, 0.15)",
                  color: plot.status === "pass" ? "var(--ok)" : "var(--warn)",
                }}>
                <span>{plot.status === "pass" ? "✓" : "✗"}</span>
                <span>{plot.status === "pass" ? "PASS" : "NOTE"}</span>
              </div>
              <img
                src={`${GITHUB_RAW}/${plot.id}.png`}
                alt={plot.title}
                className="w-full mb-2"
                loading="lazy"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
              <h3 className="text-[11px] font-medium mb-1">{plot.title}</h3>
              <p className="text-[10px] text-muted-foreground">{plot.caption}</p>
              <p className="text-[10px] mt-1 font-mono" style={{ color: plot.status === "pass" ? "var(--ok)" : "var(--warn)" }}>
                {plot.statusText}
              </p>
            </div>
          ))}
        </div>
      </div>
    </PageShell>
  );
}
