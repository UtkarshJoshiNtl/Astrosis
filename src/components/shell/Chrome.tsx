import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useEpoch, epochActions, useBackendUrl } from "@/lib/astrosis/store";

const NAV: Array<{ to: "/" | "/maneuver" | "/conjunctions" | "/performance" | "/validation" | "/docs" | "/connect"; label: string; exact?: boolean }> = [
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
  return d.toISOString().replace("T", " ").replace(/\.\d+Z$/, "Z");
}

export function TopBar({ backendLabel }: { backendLabel: string }) {
  const e = useEpoch();
  return (
    <header className="h-10 surface hairline-b flex items-stretch text-[11px]">
      <div className="flex items-center gap-3 px-3 hairline-r">
        <span className="font-mono tracking-[0.18em] text-foreground">ASTROSIS</span>
        <span className="tag">v0.1 · alpha</span>
      </div>
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
        <button
          onClick={epochActions.toggle}
          className="hairline px-2 py-0.5 text-foreground hover:bg-[var(--surface-2)]"
          title="Pause/resume sim time"
        >
          {e.paused ? "▶ run" : "❚❚ pause"}
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
        <span className="tag">BACKEND</span>
        <span className="font-mono text-foreground">{backendLabel}</span>
      </div>
    </header>
  );
}

export function PageShell({ children, backendLabel = "—" }: { children: React.ReactNode; backendLabel?: string }) {
  return (
    <div className="h-screen flex flex-col bg-background text-foreground">
      <TopBar backendLabel={backendLabel} />
      <div className="flex-1 min-h-0 overflow-hidden">{children}</div>
    </div>
  );
}

export function useUtcClock(): string {
  const [s, set] = useState(() => new Date().toISOString().replace("T", " ").replace(/\.\d+Z$/, "Z"));
  useEffect(() => {
    const id = setInterval(() => set(new Date().toISOString().replace("T", " ").replace(/\.\d+Z$/, "Z")), 1000);
    return () => clearInterval(id);
  }, []);
  return s;
}