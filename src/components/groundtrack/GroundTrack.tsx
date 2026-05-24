import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { eciToGeodetic } from "@/lib/astrosis/fallback";
import { propagate } from "@/lib/astrosis/client";
import type { SatelliteRecord, PropagateResponse } from "@/lib/astrosis/types";

const W = 720;
const H = 360;

function proj(lon: number, lat: number): [number, number] {
  return [((lon + 180) / 360) * W, ((90 - lat) / 180) * H];
}

export function GroundTrack({ sats, selectedId, when }: { sats: SatelliteRecord[]; selectedId: number | null; when: Date }) {
  const points = useMemo(
    () =>
      sats.slice(0, 250).map((s) => {
        const g = eciToGeodetic(s.pos, when);
        const [x, y] = proj(g.lon_deg, g.lat_deg);
        return { id: s.id, x, y };
      }),
    [sats, when],
  );
  const sel = points.find((p) => p.id === selectedId);

  const { data: traceData } = useQuery<PropagateResponse>({
    queryKey: ["groundtrack-trace", selectedId],
    queryFn: ({ signal }) =>
      propagate({ norad: selectedId!, hours: 1.5, dt_seconds: 60 }, signal),
    enabled: selectedId != null,
    staleTime: 30000,
    refetchOnWindowFocus: false,
  });

  const tracePath = useMemo(() => {
    if (!traceData?.ephemeris) return [];
    return traceData.ephemeris.map((p) => {
      const g = eciToGeodetic(p.pos, new Date(p.t));
      return proj(g.lon_deg, g.lat_deg);
    });
  }, [traceData]);

  const footprintRadius = useMemo(() => {
    if (!sel) return 0;
    const selSat = sats.find((s) => s.id === selectedId);
    if (!selSat?.altitude_km) return 40;
    const alt = selSat.altitude_km;
    const angle = Math.acos(RE / (RE + alt));
    return (angle / Math.PI) * H;
  }, [sel, sats, selectedId]);

  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-1.5 hairline-b flex items-center justify-between text-[11px]">
        <span className="tag">Ground Track · Equirectangular</span>
        <span className="text-muted-foreground">no land overlay · {points.length} pts</span>
      </div>
      <div className="flex-1 min-h-0 surface relative">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" className="absolute inset-0 w-full h-full">
          <rect width={W} height={H} fill="#0a0c0f" />
          {Array.from({ length: 13 }).map((_, i) => {
            const lon = -180 + i * 30;
            const x = ((lon + 180) / 360) * W;
            return (
              <g key={`lon-${i}`}>
                <line x1={x} y1={0} x2={x} y2={H} stroke="#1e2530" strokeWidth={lon === 0 ? 0.8 : 0.5} />
                <text x={x + 2} y={H - 4} fill="#5a6a7a" fontSize="8" fontFamily="IBM Plex Mono">{lon}°</text>
              </g>
            );
          })}
          {Array.from({ length: 7 }).map((_, i) => {
            const lat = -90 + i * 30;
            const y = ((90 - lat) / 180) * H;
            return (
              <g key={`lat-${i}`}>
                <line x1={0} y1={y} x2={W} y2={y} stroke="#1e2530" strokeWidth={lat === 0 ? 0.8 : 0.5} />
                <text x={2} y={y - 2} fill="#5a6a7a" fontSize="8" fontFamily="IBM Plex Mono">{lat}°</text>
              </g>
            );
          })}
          {sel && footprintRadius > 0 && (
            <circle
              cx={sel.x} cy={sel.y} r={footprintRadius}
              stroke="#e8943a" fill="none" opacity={0.3} strokeWidth={0.5}
            />
          )}
          {sel && tracePath.length > 1 && (
            <polyline
              points={tracePath.map(([x, y]) => `${x},${y}`).join(" ")}
              stroke="#e8943a" strokeWidth={1} fill="none" opacity={0.6}
            />
          )}
          {points.map((p) => (
            <circle key={p.id} cx={p.x} cy={p.y} r={p.id === selectedId ? 4 : 1.5} fill={p.id === selectedId ? "var(--primary)" : "#2a3a4a"} />
          ))}
          {sel && (
            <g>
              <line x1={0} y1={sel.y} x2={W} y2={sel.y} stroke="var(--primary)" strokeWidth={0.5} strokeDasharray="2,3" />
              <line x1={sel.x} y1={0} x2={sel.x} y2={H} stroke="var(--primary)" strokeWidth={0.5} strokeDasharray="2,3" />
            </g>
          )}
        </svg>
      </div>
    </div>
  );
}

const RE = 6371;
