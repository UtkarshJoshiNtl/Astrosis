import { useQuery } from "@tanstack/react-query";
import { fetchCatalogEntry } from "@/lib/astrosis/client";
import { useConstellation } from "@/hooks/useAstrosisData";
import type { CatalogEntry } from "@/lib/astrosis/types";

export function ElementsPanel({ selectedId }: { selectedId: number | null }) {
  const { data, isFetching } = useQuery<CatalogEntry>({
    queryKey: ["catalog", selectedId],
    queryFn: ({ signal }) => fetchCatalogEntry(selectedId!, signal),
    enabled: selectedId != null,
    staleTime: 60000,
    refetchOnWindowFocus: false,
  });

  const constellation = useConstellation(30000);
  const satellites = constellation.data?.satellites ?? [];
  const liveSat = satellites.find((s) => s.id === selectedId);

  if (!selectedId) {
    return (
      <div className="p-4 text-[11px] text-muted-foreground">
        Select a satellite from the catalog.
      </div>
    );
  }

  if (isFetching) {
    return <div className="p-4 text-[11px] text-muted-foreground">Loading elements...</div>;
  }

  if (!data) {
    return (
      <div className="p-4 text-[11px] text-muted-foreground">No data for NORAD {selectedId}.</div>
    );
  }

  const { elements, tle } = data;

  return (
    <div className="p-4 text-[11px] space-y-3">
      <div className="surface-2 hairline p-3 space-y-1">
        <div className="tag mb-1">TLE</div>
        <div className="font-mono text-[10px] text-muted-foreground break-all">{tle[0]}</div>
        <div className="font-mono text-[10px] text-muted-foreground break-all">{tle[1]}</div>
      </div>

      <div>
        <div className="tag mb-1">Keplerian Elements</div>
        <div className="surface-2 hairline">
          <Row label="Epoch" value={elements.epoch} />
          <Row label="SMA" value={`${elements.sma_km.toFixed(2)} km`} />
          <Row label="Eccentricity" value={elements.ecc.toFixed(6)} />
          <Row label="Inclination" value={`${elements.incl_deg.toFixed(3)}°`} />
          <Row label="RAAN" value={`${elements.raan_deg.toFixed(3)}°`} />
          <Row label="Arg of Perigee" value={`${elements.argp_deg.toFixed(3)}°`} />
          <Row label="Mean Anomaly" value={`${elements.mean_anom_deg.toFixed(3)}°`} />
          <Row label="Period" value={`${elements.period_min.toFixed(2)} min`} />
          <Row label="Apogee" value={`${elements.apogee_km.toFixed(1)} km`} />
          <Row label="Perigee" value={`${elements.perigee_km.toFixed(1)} km`} />
        </div>
      </div>

      {liveSat && (
        <div>
          <div className="tag mb-1">State Vector (ECI)</div>
          <div className="surface-2 hairline">
            <Row
              label="Position"
              value={`[${liveSat.pos.map((v) => v.toFixed(1)).join(", ")}] km`}
            />
            {liveSat.vel && (
              <Row
                label="Velocity"
                value={`[${liveSat.vel.map((v) => v.toFixed(3)).join(", ")}] km/s`}
              />
            )}
            <Row label="Speed" value={`${(liveSat.speed_kms ?? 0).toFixed(3)} km/s`} />
            <Row label="Altitude" value={`${(liveSat.altitude_km ?? 0).toFixed(1)} km`} />
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between px-3 py-1 hairline-b last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="num text-foreground tabular-nums">{value}</span>
    </div>
  );
}
