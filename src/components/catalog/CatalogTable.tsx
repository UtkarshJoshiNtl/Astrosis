import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef, useMemo } from "react";
import type { SatelliteRecord } from "@/lib/astrosis/types";

export function CatalogTable({
  satellites,
  selectedId,
  onSelect,
}: {
  satellites: SatelliteRecord[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
}) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: satellites.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 24,
    overscan: 20,
  });

  return (
    <div className="h-full flex flex-col text-[11px]">
      <div className="flex items-center px-3 py-1 hairline-b tag">
        <span className="flex-1">NORAD</span>
        <span className="w-16 text-right">Alt (km)</span>
        <span className="w-16 text-right">Inc (°)</span>
        <span className="w-16 text-right">Period</span>
      </div>
      <div ref={parentRef} className="flex-1 overflow-auto">
        <div style={{ height: `${virtualizer.getTotalSize()}px`, position: "relative" }}>
          {virtualizer.getVirtualItems().map((vItem) => {
            const sat = satellites[vItem.index];
            return (
              <button
                key={sat.id}
                onClick={() => onSelect(sat.id === selectedId ? null : sat.id)}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: `${vItem.size}px`,
                  transform: `translateY(${vItem.start}px)`,
                }}
                className={`flex items-center px-3 hover:bg-[var(--surface-2)] ${
                  sat.id === selectedId
                    ? "bg-[var(--surface-2)] text-[var(--primary)]"
                    : "text-muted-foreground"
                }`}
              >
                <span className="flex-1 num text-left">{sat.id}</span>
                <span className="w-16 text-right num">{sat.altitude_km?.toFixed(0) ?? "—"}</span>
                <span className="w-16 text-right num">
                  {sat.inclination_deg?.toFixed(1) ?? "—"}
                </span>
                <span className="w-16 text-right num">{sat.period_min?.toFixed(1) ?? "—"}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
