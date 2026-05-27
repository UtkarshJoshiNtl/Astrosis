import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useEpoch, epochActions, useSelection } from "@/lib/astrosis/store";
import { fetchCatalogEntry } from "@/lib/astrosis/client";
import { useConstellation } from "@/hooks/useAstrosisData";
import type { BackendHealth } from "@/lib/astrosis/types";

const NAV: Array<{
  to: "/" | "/maneuver" | "/conjunctions" | "/performance" | "/validation" | "/docs" | "/connect";
  label: string;
  exact?: boolean;
}> = [
  { to: "/", label: "Workbench", exact: true },
  { to: "/maneuver", label: "Maneuver" },
  { to: "/conjunctions", label: "Conjunctions" },
  { to: "/performance", label: "Performance" },
  { to: "/validation", label: "Validation" },
  { to: "/docs", label: "Docs" },
  { to: "/connect", label: "Connect" },
];

function fmtUTC(ms: number): string {
  if (!ms) return "—";
  const d = new Date(ms);
  return d
    .toISOString()
    .replace("T", " ")
    .replace(/\.\d+Z$/, "Z");
}

export function TopBar({
  backendLabel,
  health,
}: {
  backendLabel: string;
  health?: BackendHealth | undefined;
}) {
  const e = useEpoch();
  const [, setSelectedId] = useSelection();
  const [searchVal, setSearchVal] = useState("");
  const [searching, setSearching] = useState(false);
  const constellation = useConstellation(30000);
  const satellites = constellation.data?.satellites ?? [];

  async function handleSearchSubmit(e: React.FormEvent | React.KeyboardEvent) {
    e.preventDefault();
    const q = searchVal.trim();
    if (!q) return;

    const numeric = parseInt(q, 10);
    if (Number.isFinite(numeric) && numeric > 0) {
      setSearching(true);
      try {
        const entry = await fetchCatalogEntry(numeric);
        if (entry?.norad) {
          setSelectedId(entry.norad);
          setSearchVal("");
        }
      } catch {
        const match = satellites.find((s) => s.id === numeric);
        if (match) setSelectedId(match.id);
      } finally {
        setSearching(false);
      }
    } else {
      const match = satellites.find((s) => s.name?.toLowerCase() === q.toLowerCase());
      if (match) setSelectedId(match.id);
    }
  }

  const isOnline = health?.ok ?? false;

  return (
    <header className="h-10 surface hairline-b flex items-stretch text-[11px]">
      <div className="flex items-center gap-3 px-3 hairline-r">
        <span className="font-mono tracking-[0.3em] text-foreground text-[12px]">ASTROSIS</span>
      </div>
      <form onSubmit={handleSearchSubmit} className="flex items-center px-2 hairline-r">
        <input
          className="w-56 hairline bg-transparent px-2 py-1 text-[11px] text-foreground placeholder:text-muted-foreground num focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
          placeholder="NORAD ID or name — try 25544"
          value={searchVal}
          onChange={(e) => setSearchVal(e.target.value)}
        />
        {searching && <span className="tag ml-2">searching...</span>}
      </form>
      <nav className="flex items-stretch">
        {NAV.map((n) => (
          <Link
            key={n.to}
            to={n.to}
            activeOptions={{ exact: n.exact ?? false }}
            className="px-3 flex items-center text-muted-foreground hover:text-foreground hairline-r data-[status=active]:text-foreground data-[status=active]:bg-[var(--surface-2)]"
          >
            {n.label}
          </Link>
        ))}
      </nav>
      <div className="flex-1" />
      <div className="flex items-center gap-4 px-3 num">
        <div className="flex items-center gap-1.5">
          <span className="tag">UTC</span>
          <span className="tabular text-foreground">{fmtUTC(e.epoch_ms)}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block w-2 h-2"
            style={{ background: isOnline ? "var(--ok)" : "var(--destructive)" }}
          />
          <span className="text-muted-foreground text-[10px]">{backendLabel}</span>
        </div>
        <button
          onClick={epochActions.toggle}
          className="hairline px-2 py-0.5 text-foreground hover:bg-[var(--surface-2)]"
          title="Pause/resume sim time"
        >
          {e.paused ? "▶" : "❚❚"}
        </button>
        <select
          value={e.rate}
          onChange={(ev) => epochActions.setRate(Number(ev.target.value))}
          className="bg-transparent hairline px-1 py-0.5 text-foreground"
        >
          <option value={1}>1×</option>
          <option value={60}>60×</option>
          <option value={600}>600×</option>
          <option value={3600}>3600×</option>
        </select>
        <button
          onClick={epochActions.resetToNow}
          className="hairline px-2 py-0.5 text-muted-foreground hover:text-foreground"
        >
          now
        </button>
      </div>
    </header>
  );
}

export function PageShell({
  children,
  backendLabel = "—",
  health,
}: {
  children: React.ReactNode;
  backendLabel?: string;
  health?: BackendHealth | undefined;
}) {
  return (
    <div className="h-screen flex flex-col bg-background text-foreground">
      <TopBar backendLabel={backendLabel} health={health} />
      <div className="flex-1 min-h-0 overflow-hidden">{children}</div>
    </div>
  );
}

export function useUtcClock(): string {
  const [s, set] = useState(() =>
    new Date()
      .toISOString()
      .replace("T", " ")
      .replace(/\.\d+Z$/, "Z"),
  );
  useEffect(() => {
    const id = setInterval(
      () =>
        set(
          new Date()
            .toISOString()
            .replace("T", " ")
            .replace(/\.\d+Z$/, "Z"),
        ),
      1000,
    );
    return () => clearInterval(id);
  }, []);
  return s;
}
