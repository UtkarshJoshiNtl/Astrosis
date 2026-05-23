import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageShell } from "@/components/shell/Chrome";
import { conjunctions } from "@/lib/astrosis/client";
import { useConstellation, useHealth } from "@/hooks/useAstrosisData";
import type { ConjunctionPair } from "@/lib/astrosis/types";

export const Route = createFileRoute("/conjunctions")({
  component: ConjunctionsPage,
});

function PcBand({ pc }: { pc?: number }) {
  if (pc == null) return <span className="text-muted-foreground">—</span>;
  const level = pc > 1e-4 ? "destructive" : pc > 1e-6 ? "text-[var(--warn)]" : "text-muted-foreground";
  return <span className={`num ${level}`}>{pc.toExponential(2)}</span>;
}

function ConjunctionsPage() {
  const constellation = useConstellation(30000);
  const health = useHealth();
  const backendLabel = health.data?.backend ?? constellation.data?.backend ?? "OFFLINE SGP4";
  const satellites = constellation.data?.satellites ?? [];
  const norads = satellites.map((s) => s.id);

  const { data: pairs, isFetching } = useQuery<ConjunctionPair[]>({
    queryKey: ["conjunctions", norads.join(",")],
    queryFn: ({ signal }) => conjunctions({ norads: norads.slice(0, 100), hours: 24, threshold_km: 5 }, signal),
    enabled: norads.length > 0,
    refetchOnWindowFocus: false,
    staleTime: 60000,
  });

  return (
    <PageShell backendLabel={backendLabel}>
      <div className="h-full flex flex-col p-4">
        <div className="flex items-center justify-between mb-3">
          <h1 className="text-sm font-semibold">Conjunction Assessment</h1>
          {isFetching && <span className="tag">scanning...</span>}
        </div>
        <div className="flex-1 min-h-0 overflow-auto">
          <table className="w-full text-[11px] num">
            <thead>
              <tr className="hairline-b text-muted-foreground">
                <th className="text-left px-3 py-1.5 font-medium">Object A</th>
                <th className="text-left px-3 py-1.5 font-medium">Object B</th>
                <th className="text-right px-3 py-1.5 font-medium">TCA</th>
                <th className="text-right px-3 py-1.5 font-medium">Miss (km)</th>
                <th className="text-right px-3 py-1.5 font-medium">Rel Vel (km/s)</th>
                <th className="text-right px-3 py-1.5 font-medium">Pc</th>
              </tr>
            </thead>
            <tbody>
              {pairs?.length === 0 && (
                <tr><td colSpan={6} className="text-center py-8 text-muted-foreground">No conjunctions detected</td></tr>
              )}
              {pairs?.map((p, i) => (
                <tr key={i} className="hairline-b hover:bg-[var(--surface-2)]">
                  <td className="px-3 py-1.5">{p.a}</td>
                  <td className="px-3 py-1.5">{p.b}</td>
                  <td className="text-right px-3 py-1.5 font-mono">{new Date(p.tca).toISOString().replace("T", " ").slice(0, 19)}</td>
                  <td className="text-right px-3 py-1.5">{p.miss_km.toFixed(3)}</td>
                  <td className="text-right px-3 py-1.5">{p.rel_vel_kms.toFixed(3)}</td>
                  <td className="text-right px-3 py-1.5"><PcBand pc={p.pc} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-2 text-[10px] text-muted-foreground italic">
          Pc model experimental — Chan spherical-Gaussian approximation. Not for operational use.
        </div>
      </div>
    </PageShell>
  );
}
