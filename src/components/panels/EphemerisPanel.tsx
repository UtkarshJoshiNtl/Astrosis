import { useQuery } from "@tanstack/react-query";
import { propagate } from "@/lib/astrosis/client";
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
    queryFn: ({ signal }) =>
      propagate({ norad: selectedId!, hours: 6, dt_seconds: 60 }, signal),
    enabled: selectedId != null,
    staleTime: 30000,
    refetchOnWindowFocus: false,
  });

  if (!selectedId) {
    return <div className="p-4 text-[11px] text-muted-foreground">Select a satellite to view ephemeris.</div>;
  }

  if (isFetching) {
    return <div className="p-4 text-[11px] text-muted-foreground">Propagating orbit...</div>;
  }

  if (!data?.ephemeris?.length) {
    return <div className="p-4 text-[11px] text-muted-foreground">No ephemeris data available.</div>;
  }

  const chartData = data.ephemeris.map((p) => {
    const r = Math.sqrt(p.pos[0] ** 2 + p.pos[1] ** 2 + p.pos[2] ** 2);
    const alt = Math.max(0, r - 6371);
    return {
      t: new Date(p.t).toISOString().slice(11, 16),
      alt_km: alt,
    };
  });

  return (
    <div className="p-4 text-[11px] space-y-3">
      <div className="flex justify-between">
        <span className="tag">Altitude over 6 hours</span>
        <span className="text-muted-foreground">{data.ephemeris.length} points</span>
      </div>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="oklch(1 0 0 / 6%)" />
            <XAxis dataKey="t" tick={{ fontSize: 9, fill: "oklch(0.65 0.01 250)" }} />
            <YAxis tick={{ fontSize: 9, fill: "oklch(0.65 0.01 250)" }} />
            <Tooltip
              contentStyle={{ background: "oklch(0.19 0.005 250)", border: "1px solid oklch(1 0 0 / 10%)", borderRadius: 2, fontSize: 11 }}
              labelStyle={{ color: "oklch(0.95 0.005 250)" }}
            />
            <Line type="monotone" dataKey="alt_km" stroke="var(--primary)" dot={false} strokeWidth={1} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
