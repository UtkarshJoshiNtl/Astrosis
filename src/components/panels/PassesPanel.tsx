import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { passes } from "@/lib/astrosis/client";
import type { PassPrediction } from "@/lib/astrosis/types";

function fmtDur(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}m ${sec}s`;
}

function fmtAz(deg: number): string {
  const dirs = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
  ];
  const i = Math.round(deg / 22.5) % 16;
  return `${deg.toFixed(0)}° ${dirs[i]}`;
}

export function PassesPanel({ selectedId }: { selectedId: number | null }) {
  const [lat, setLat] = useState("40.7128");
  const [lon, setLon] = useState("-74.0060");

  const { data, isFetching } = useQuery<PassPrediction[]>({
    queryKey: ["passes", selectedId, lat, lon],
    queryFn: ({ signal }) =>
      passes(
        {
          norad: selectedId!,
          lat_deg: parseFloat(lat),
          lon_deg: parseFloat(lon),
          hours: 24,
        },
        signal,
      ),
    enabled: selectedId != null,
    staleTime: 60000,
    refetchOnWindowFocus: false,
  });

  function useGeo() {
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition((pos) => {
        setLat(pos.coords.latitude.toFixed(4));
        setLon(pos.coords.longitude.toFixed(4));
      });
    }
  }

  function elevColor(el: number): string {
    if (el >= 60) return "text-[var(--ok)]";
    if (el >= 30) return "text-foreground";
    return "text-muted-foreground";
  }

  if (!selectedId) {
    return (
      <div className="p-4 text-[11px] text-muted-foreground">
        Select a satellite to predict passes.
      </div>
    );
  }

  return (
    <div className="p-4 text-[11px] space-y-3">
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1">
          <label htmlFor="pass-lat" className="text-muted-foreground">
            LAT
          </label>
          <input
            id="pass-lat"
            className="w-20 hairline bg-transparent px-1.5 py-0.5 num text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
            value={lat}
            onChange={(e) => setLat(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-1">
          <label htmlFor="pass-lon" className="text-muted-foreground">
            LON
          </label>
          <input
            id="pass-lon"
            className="w-20 hairline bg-transparent px-1.5 py-0.5 num text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
            value={lon}
            onChange={(e) => setLon(e.target.value)}
          />
        </div>
        <button
          onClick={useGeo}
          className="hairline px-2 py-0.5 text-muted-foreground hover:text-foreground text-[10px]"
        >
          use my location
        </button>
        <span className="tag">next 24h</span>
      </div>

      {isFetching && <span className="tag">predicting...</span>}

      {data && (
        <table className="w-full">
          <thead>
            <tr className="hairline-b text-muted-foreground">
              <th className="text-left px-2 py-1 font-medium">AOS UTC</th>
              <th className="text-left px-2 py-1 font-medium">LOS UTC</th>
              <th className="text-right px-2 py-1 font-medium">Max El</th>
              <th className="text-right px-2 py-1 font-medium">Az AOS</th>
              <th className="text-right px-2 py-1 font-medium">Az LOS</th>
              <th className="text-right px-2 py-1 font-medium">Duration</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p) => (
              <tr key={`${p.aos}-${p.los}`} className="hairline-b">
                <td className="px-2 py-1 font-mono text-[10px]">
                  {new Date(p.aos).toISOString().slice(11, 19)}
                </td>
                <td className="px-2 py-1 font-mono text-[10px]">
                  {new Date(p.los).toISOString().slice(11, 19)}
                </td>
                <td className={`text-right px-2 py-1 num ${elevColor(p.max_el_deg)}`}>
                  {p.max_el_deg.toFixed(1)}°
                </td>
                <td className="text-right px-2 py-1 num text-muted-foreground">
                  {fmtAz(p.az_aos_deg)}
                </td>
                <td className="text-right px-2 py-1 num text-muted-foreground">
                  {fmtAz(p.az_los_deg)}
                </td>
                <td className="text-right px-2 py-1 num">{fmtDur(p.duration_s)}</td>
              </tr>
            ))}
            {data.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center py-4 text-muted-foreground">
                  No passes in next 24h
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
