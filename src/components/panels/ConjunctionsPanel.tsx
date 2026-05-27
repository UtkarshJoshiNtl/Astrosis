import { useQuery } from "@tanstack/react-query";
import { conjunctions } from "@/lib/astrosis/client";
import { useConstellation } from "@/hooks/useAstrosisData";
import type { ConjunctionPair } from "@/lib/astrosis/types";

export function ConjunctionsPanel({ selectedId }: { selectedId: number | null }) {
  const constellation = useConstellation(30000);
  const allIds = (constellation.data?.satellites ?? []).map((s) => s.id);

  const candidates =
    selectedId != null
      ? [selectedId, ...allIds.filter((id) => id !== selectedId).slice(0, 49)]
      : allIds.slice(0, 50);

  const { data, isFetching } = useQuery<ConjunctionPair[]>({
    queryKey: ["conjunctions-panel", candidates.join(",")],
    queryFn: ({ signal }) =>
      conjunctions({ norads: candidates, hours: 24, threshold_km: 5 }, signal),
    enabled: candidates.length > 1,
    staleTime: 60000,
    refetchOnWindowFocus: false,
  });

  function missColor(km: number): string {
    if (km < 1) return "text-[var(--destructive)]";
    if (km < 5) return "text-[var(--warn)]";
    return "text-foreground";
  }

  function pcColor(pc?: number): string {
    if (pc == null) return "text-muted-foreground";
    if (pc > 1e-4) return "text-[var(--destructive)]";
    if (pc > 1e-6) return "text-[var(--warn)]";
    return "text-muted-foreground";
  }

  const hasData = data && data.length > 0;

  return (
    <div className="p-4 text-[11px] space-y-2">
      <div className="flex items-center justify-between tag">
        <span>
          Screening {candidates.length} objects &middot; lookahead 24h &middot; threshold 5km
        </span>
        {isFetching && <span>SCANNING...</span>}
      </div>
      {!selectedId && (
        <div className="text-muted-foreground">Select a satellite to screen conjunctions.</div>
      )}
      {selectedId && !isFetching && !hasData && (
        <div className="text-muted-foreground">No conjunctions within threshold.</div>
      )}
      {hasData && (
        <table className="w-full">
          <thead>
            <tr className="hairline-b text-muted-foreground">
              <th className="text-left px-2 py-1 font-medium">Object A</th>
              <th className="text-left px-2 py-1 font-medium">Object B</th>
              <th className="text-right px-2 py-1 font-medium">TCA</th>
              <th className="text-right px-2 py-1 font-medium">Miss (km)</th>
              <th className="text-right px-2 py-1 font-medium">Rel Vel</th>
              <th className="text-right px-2 py-1 font-medium">Pc</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p) => (
              <tr key={`${p.a}-${p.b}-${p.tca}`} className="hairline-b">
                <td className="px-2 py-1 num">{p.a}</td>
                <td className="px-2 py-1 num">{p.b}</td>
                <td className="text-right px-2 py-1 font-mono text-[10px]">
                  {new Date(p.tca).toISOString().slice(11, 19)}Z
                </td>
                <td className={`text-right px-2 py-1 num ${missColor(p.miss_km)}`}>
                  {p.miss_km.toFixed(3)}
                </td>
                <td className="text-right px-2 py-1 num">{p.rel_vel_kms.toFixed(2)} km/s</td>
                <td className={`text-right px-2 py-1 num ${pcColor(p.pc)}`}>
                  {p.pc != null ? p.pc.toExponential(2) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="text-[10px] text-muted-foreground italic pt-2">
        Pc model experimental — Chan spherical-Gaussian approximation. Not for operational use.
      </div>
    </div>
  );
}
