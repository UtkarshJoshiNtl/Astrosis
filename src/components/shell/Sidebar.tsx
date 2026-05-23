import { useMemo, useState } from "react";
import type { SatelliteRecord } from "@/lib/astrosis/types";

export function Sidebar({
  satellites,
  selectedId,
  onSelect,
}: {
  satellites: SatelliteRecord[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
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

  return (
    <div className="w-52 surface hairline-r flex flex-col text-[11px]">
      <div className="px-3 py-1.5 hairline-b">
        <span className="tag">Catalog</span>
        <span className="ml-2 text-muted-foreground">{satellites.length}</span>
      </div>
      <div className="px-2 py-1 hairline-b">
        <input
          className="w-full hairline bg-transparent px-2 py-1 text-[11px] text-foreground placeholder:text-muted-foreground num"
          placeholder="Search NORAD / name..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto">
        {filtered.map((sat) => (
          <button
            key={sat.id}
            onClick={() => onSelect(sat.id === selectedId ? null : sat.id)}
            className={`w-full text-left px-3 py-1 hover:bg-[var(--surface-2)] flex items-center justify-between ${
              sat.id === selectedId ? "bg-[var(--surface-2)] text-[var(--primary)]" : "text-muted-foreground"
            }`}
          >
            <span className="num">{sat.id}</span>
            <span className="truncate ml-2 text-[10px]">{sat.name ?? ""}</span>
          </button>
        ))}
        {filtered.length === 0 && (
          <div className="px-3 py-4 text-center text-muted-foreground">No matches</div>
        )}
      </div>
    </div>
  );
}
