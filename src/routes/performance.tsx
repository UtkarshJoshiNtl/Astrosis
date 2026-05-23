import { createFileRoute } from "@tanstack/react-router";
import { PageShell, useUtcClock } from "@/components/shell/Chrome";
import { useHealth } from "@/hooks/useAstrosisData";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

export const Route = createFileRoute("/performance")({
  component: PerformancePage,
});

const BENCH_DATA = [
  { name: "Single Sat\n(50k steps)", Python: 395, "C++": 21.9, CUDA: 0 },
  { name: "Constellation\n(1k sats, 24h)", Python: 7034, "C++": 13.9, CUDA: 46.9 },
  { name: "Collision Scr.\n(400×400 pairs)", Python: 46718, "C++": 5159, CUDA: 564 },
  { name: "Maneuver Plan.\n(10k ΔV)", Python: 425, "C++": 6.0, CUDA: 0 },
];

const SPEEDUP_DATA = [
  { operation: "Single Sat (50k steps)", cpp: "18×", cuda: "N/A" },
  { operation: "Constellation (1k sats, 24h)", cpp: "507×", cuda: "150×" },
  { operation: "Collision Screening (400×400)", cpp: "9×", cuda: "83×" },
  { operation: "Maneuver Planning (10k ΔV)", cpp: "71×", cuda: "N/A" },
];

function PerformancePage() {
  const health = useHealth();
  const utc = useUtcClock();
  const backendLabel = health.data?.backend ?? "—";

  return (
    <PageShell backendLabel={backendLabel}>
      <div className="h-full flex flex-col p-4 overflow-auto">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-sm font-semibold">Performance Benchmarks</h1>
          <span className="tag">{utc}</span>
        </div>

        <div className="text-[10px] text-muted-foreground mb-4">
          Hardware: NVIDIA RTX 2050 (16 SMs) · AMD Ryzen 5 · 16 GB DDR4 · CUDA 12.9
        </div>

        <div className="h-64 mb-6">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={BENCH_DATA} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
              <CartesianGrid stroke="oklch(1 0 0 / 6%)" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: "oklch(0.65 0.01 250)" }} />
              <YAxis tick={{ fontSize: 10, fill: "oklch(0.65 0.01 250)" }} label={{ value: "Time (ms)", angle: -90, position: "insideLeft", style: { fill: "oklch(0.65 0.01 250)", fontSize: 10 } }} />
              <Tooltip
                contentStyle={{ background: "oklch(0.19 0.005 250)", border: "1px solid oklch(1 0 0 / 10%)", borderRadius: 2, fontSize: 11 }}
                labelStyle={{ color: "oklch(0.95 0.005 250)" }}
              />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Bar dataKey="Python" fill="oklch(0.62 0.08 25)" />
              <Bar dataKey="C++" fill="oklch(0.68 0.06 220)" />
              <Bar dataKey="CUDA" fill="oklch(0.78 0.13 75)" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <h2 className="tag mb-2">Speedup Factors</h2>
        <table className="w-full text-[11px] num mb-6">
          <thead>
            <tr className="hairline-b text-muted-foreground">
              <th className="text-left px-3 py-1.5 font-medium">Operation</th>
              <th className="text-right px-3 py-1.5 font-medium">C++ Speedup</th>
              <th className="text-right px-3 py-1.5 font-medium">CUDA Speedup</th>
            </tr>
          </thead>
          <tbody>
            {SPEEDUP_DATA.map((row, i) => (
              <tr key={i} className="hairline-b">
                <td className="px-3 py-1.5">{row.operation}</td>
                <td className="text-right px-3 py-1.5 text-[var(--chart-2)]">{row.cpp}</td>
                <td className="text-right px-3 py-1.5 text-[var(--primary)]">{row.cuda}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="text-[10px] text-muted-foreground space-y-1">
          <p>Benchmarks from docs/performance.md. Python baseline in ms (lower is better).</p>
          <p>CUDA includes host-device transfer overhead. FP64 arithmetic throughout.</p>
        </div>
      </div>
    </PageShell>
  );
}
