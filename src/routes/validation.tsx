import { createFileRoute } from "@tanstack/react-router";
import { PageShell, useUtcClock } from "@/components/shell/Chrome";
import { useHealth } from "@/hooks/useAstrosisData";

export const Route = createFileRoute("/validation")({
  component: ValidationPage,
});

const PLOTS = [
  {
    id: "1_energy_conservation",
    title: "Energy Conservation (Canonical Test)",
    caption: "24-hour LEO propagation (1,000 satellites, 400 km altitude, circular orbits). RK4 at dt=10s (86,400 steps). Relative energy drift: 9.1 × 10⁻⁹ — better than theoretical O(dt⁴) bound of 1 × 10⁻⁷.",
  },
  {
    id: "2_sgp4_comparison",
    title: "ISS Propagation vs. SGP4",
    caption: "ISS (NORAD 25544) propagated for 24 hours. Position error growth is expected due to TLE uncertainty (0.1–1 km inherent). Astrosis validation: perturbation model behaves consistently with SGP4.",
  },
  {
    id: "3_raan_precession",
    title: "J2 Nodal Regression (RAAN)",
    caption: "Circular 700 km LEO, 60° inclination, 7 days. Analytical dΩ/dt = -3.14°/day. RK4: -3.11°/day. Error: +0.96% — J₂ gravity model correctly integrated.",
  },
  {
    id: "4_rk4_convergence",
    title: "RK4 Convergence Verification",
    caption: "Richardson extrapolation: error ratio ≈ 16 per dt halving confirms 4th-order accuracy (2⁴ = 16). Position error at dt=1.25s: 3.2 × 10⁻⁸ km.",
  },
  {
    id: "5_srp_divergence",
    title: "Solar Radiation Pressure Divergence",
    caption: "Low-mass (2 kg/m²) vs. high-mass (100 kg/m²) satellite. SRP acceleration ratio: 50× (exact match). 24h displacement: 1.9 km (low) vs. 38 m (high).",
  },
];

const GITHUB_RAW = "https://raw.githubusercontent.com/UtkarshJoshiNtl/Astrosis/alpha/validation/plots";

function ValidationPage() {
  const health = useHealth();
  const utc = useUtcClock();
  const backendLabel = health.data?.backend ?? "—";

  return (
    <PageShell backendLabel={backendLabel}>
      <div className="h-full flex flex-col p-4 overflow-auto">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-sm font-semibold">Validation Gallery</h1>
          <span className="tag">{utc}</span>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {PLOTS.map((plot) => (
            <div key={plot.id} className="surface hairline p-3">
              <img
                src={`${GITHUB_RAW}/${plot.id}.png`}
                alt={plot.title}
                className="w-full mb-2"
                loading="lazy"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
              <h3 className="text-[11px] font-medium mb-1">{plot.title}</h3>
              <p className="text-[10px] text-muted-foreground">{plot.caption}</p>
            </div>
          ))}
        </div>
      </div>
    </PageShell>
  );
}
