import { useQuery } from "@tanstack/react-query";
import { propagate } from "@/lib/astrosis/client";
import { eciToGeodetic } from "@/lib/astrosis/fallback";
import type { PropagateResponse } from "@/lib/astrosis/types";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export function EphemerisPanel({ selectedId }: { selectedId: number | null }) {
  const { data, isFetching } = useQuery<PropagateResponse>({
    queryKey: ["propagate", selectedId],
    queryFn: ({ signal }) => propagate({ norad: selectedId!, hours: 6, dt_seconds: 60 }, signal),
    enabled: selectedId != null,
    staleTime: 30000,
    refetchOnWindowFocus: false,
  });

  if (!selectedId) {
    return (
      <div className="p-4 text-[11px] text-muted-foreground">
        Select a satellite to view ephemeris.
      </div>
    );
  }

  if (isFetching) {
    return <div className="p-4 text-[11px] text-muted-foreground">Propagating orbit...</div>;
  }

  if (!data?.ephemeris?.length) {
    return (
      <div className="p-4 text-[11px] text-muted-foreground">No ephemeris data available.</div>
    );
  }

  const chartData = data.ephemeris.map((p) => {
    const r = Math.sqrt(p.pos[0] ** 2 + p.pos[1] ** 2 + p.pos[2] ** 2);
    const alt = Math.max(0, r - 6371);
    const g = eciToGeodetic(p.pos, new Date(p.t));
    return {
      t: new Date(p.t).toISOString().slice(11, 16),
      alt_km: alt,
      lat: g.lat_deg,
      lon: g.lon_deg,
      speed: Math.sqrt(p.vel[0] ** 2 + p.vel[1] ** 2 + p.vel[2] ** 2),
      rawT: p.t,
    };
  });

  const step = Math.max(1, Math.floor(data.ephemeris.length / 7));
  const tablePoints = [0, ...Array.from({ length: 7 }, (_, i) => (i + 1) * step)]
    .slice(0, 8)
    .map((i) => chartData[Math.min(i, chartData.length - 1)]);

  const CustomTooltip = ({
    active,
    payload,
  }: {
    active?: boolean;
    payload?: Record<string, unknown>[];
  }) => {
    if (!active || !payload?.[0]) return null;
    const d = payload[0].payload as Record<string, number | string>;
    return (
      <div className="surface-2 hairline px-2 py-1 text-[10px] font-mono">
        <div>
          {d.t} &middot; {Number(d.alt_km).toFixed(1)} km
        </div>
        <div className="text-muted-foreground">
          [{Number(d.lat).toFixed(1)}°, {Number(d.lon).toFixed(1)}°]
        </div>
      </div>
    );
  };

  return (
    <div className="p-4 text-[11px] space-y-3">
      <div className="flex justify-between">
        <span className="tag">Altitude over 6 hours</span>
        <span className="text-muted-foreground">{data.ephemeris.length} points</span>
      </div>
      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#1e2530" strokeWidth={1} />
            <XAxis
              dataKey="t"
              tick={{ fontSize: 9, fill: "#5a6a7a", fontFamily: "IBM Plex Mono" }}
            />
            <YAxis tick={{ fontSize: 9, fill: "#5a6a7a", fontFamily: "IBM Plex Mono" }} />
            <Tooltip content={<CustomTooltip />} />
            <Line type="monotone" dataKey="alt_km" stroke="#4a8bbf" dot={false} strokeWidth={1.5} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div>
        <div className="tag mb-1">Key Ephemeris Points</div>
        <table className="w-full text-[10px]">
          <thead>
            <tr className="hairline-b text-muted-foreground">
              <th className="text-left px-1 py-0.5 font-medium">Time UTC</th>
              <th className="text-right px-1 py-0.5 font-medium">Alt (km)</th>
              <th className="text-right px-1 py-0.5 font-medium">Lat</th>
              <th className="text-right px-1 py-0.5 font-medium">Lon</th>
              <th className="text-right px-1 py-0.5 font-medium">Speed</th>
            </tr>
          </thead>
          <tbody>
            {tablePoints.map((p) => (
              <tr key={p.t} className="hairline-b">
                <td className="px-1 py-0.5 font-mono">{p.t}Z</td>
                <td className="text-right px-1 py-0.5 num">{p.alt_km.toFixed(1)}</td>
                <td className="text-right px-1 py-0.5 num">{p.lat.toFixed(1)}°</td>
                <td className="text-right px-1 py-0.5 num">{p.lon.toFixed(1)}°</td>
                <td className="text-right px-1 py-0.5 num">{p.speed.toFixed(3)} km/s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
