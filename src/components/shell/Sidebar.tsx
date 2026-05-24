import { useMemo, useState, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { SatelliteRecord } from "@/lib/astrosis/types";

export function Sidebar({
  satellites,
  selectedId,
  onSelect,
  demoMode,
}: {
  satellites: SatelliteRecord[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  demoMode?: boolean;
}) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    if (!query) return satellites;
    const q = query.toLowerCase();
    return satellites.filter(
      (s) =>
        String(s.id).includes(q) ||
        (s.name && s.name.toLowerCase().includes(q)),
    );
  }, [satellites, query]);

  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 28,
    overscan: 20,
  });

  return (
    <div className="w-[200px] surface hairline-r flex flex-col text-[11px]">
      <div className="px-3 py-1.5 hairline-b">
        <span className="tag">Catalog</span>
        <span className="ml-2 text-muted-foreground">{satellites.length}</span>
      </div>
      {demoMode && (
        <div className="px-3 py-1.5 hairline-b text-[10px] text-[var(--warn)]">
          ⚠ CELESTRAK OFFLINE · DEMO MODE · {satellites.length} synthetic LEO seeds
        </div>
      )}
      <div className="px-2 py-1 hairline-b">
        <input
          className="w-full hairline bg-transparent px-2 py-1 text-[11px] text-foreground placeholder:text-muted-foreground num"
          placeholder="Search NORAD / name..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="flex items-center px-3 py-1 hairline-b tag">
        <span className="w-[60px]">NORAD</span>
        <span className="flex-1 truncate">Name</span>
        <span className="w-[50px] text-right">Alt</span>
        <span className="w-[48px] text-right">Inc</span>
      </div>
      <div ref={parentRef} className="flex-1 min-h-0 overflow-auto">
        <div style={{ height: `${virtualizer.getTotalSize()}px`, position: "relative" }}>
          {virtualizer.getVirtualItems().map((vItem) => {
            const sat = filtered[vItem.index];
            const isSelected = sat.id === selectedId;
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
                className={`flex items-center px-3 hover:bg-[var(--surface-2)] text-left ${
                  isSelected ? "selected-row text-foreground" : "text-muted-foreground"
                }`}
              >
                <span className="w-[60px] num">{sat.id}</span>
                <span className="flex-1 truncate text-[10px]">{sat.name ?? ""}</span>
                <span className="w-[50px] text-right num">{sat.altitude_km?.toFixed(0) ?? "—"}</span>
                <span className="w-[48px] text-right num">{sat.inclination_deg?.toFixed(1) ?? "—"}</span>
              </button>
            );
          })}
        </div>
      </div>
      {filtered.length === 0 && (
        <div className="px-3 py-4 text-center text-muted-foreground">No matches</div>
      )}
    </div>
  );
}
