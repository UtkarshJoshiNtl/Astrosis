import { useMemo } from "react";
import { eciToGeodetic } from "@/lib/astrosis/fallback";
import type { SatelliteRecord } from "@/lib/astrosis/types";

// Equirectangular SVG ground track. Graticule + sub-satellite points.
// No continent overlay (kept lightweight) — labelled as "no land overlay".

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

  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-1.5 hairline-b flex items-center justify-between text-[11px]">
        <span className="tag">Ground Track · Equirectangular</span>
        <span className="text-muted-foreground">no land overlay · {points.length} pts</span>
      </div>
      <div className="flex-1 min-h-0 surface relative">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" className="absolute inset-0 w-full h-full">
          <rect width={W} height={H} fill="#16191e" />
          {/* Graticule */}
          {Array.from({ length: 13 }).map((_, i) => {
            const lon = -180 + i * 30;
            const x = ((lon + 180) / 360) * W;
            return (
              <g key={`lon-${i}`}>
                <line x1={x} y1={0} x2={x} y2={H} stroke="oklch(1 0 0 / 6%)" strokeWidth={lon === 0 ? 0.8 : 0.4} />
                <text x={x + 2} y={H - 4} fill="oklch(1 0 0 / 35%)" fontSize="9" fontFamily="IBM Plex Mono">{lon}°</text>
              </g>
            );
          })}
          {Array.from({ length: 7 }).map((_, i) => {
            const lat = -90 + i * 30;
            const y = ((90 - lat) / 180) * H;
            return (
              <g key={`lat-${i}`}>
                <line x1={0} y1={y} x2={W} y2={y} stroke="oklch(1 0 0 / 6%)" strokeWidth={lat === 0 ? 0.8 : 0.4} />
                <text x={2} y={y - 2} fill="oklch(1 0 0 / 35%)" fontSize="9" fontFamily="IBM Plex Mono">{lat}°</text>
              </g>
            );
          })}
          {/* Sub-satellite points */}
          {points.map((p) => (
            <circle key={p.id} cx={p.x} cy={p.y} r={p.id === selectedId ? 3.5 : 1.2} fill={p.id === selectedId ? "var(--primary)" : "#a8b1bc"} />
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