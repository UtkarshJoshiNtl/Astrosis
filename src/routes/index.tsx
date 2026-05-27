import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { PageShell, useUtcClock } from "@/components/shell/Chrome";
import { Sidebar } from "@/components/shell/Sidebar";
import { Globe } from "@/components/globe/Globe";
import { GroundTrack } from "@/components/groundtrack/GroundTrack";
import { ElementsPanel } from "@/components/panels/ElementsPanel";
import { EphemerisPanel } from "@/components/panels/EphemerisPanel";
import { PassesPanel } from "@/components/panels/PassesPanel";
import { ConjunctionsPanel } from "@/components/panels/ConjunctionsPanel";
import { ManeuverPanel } from "@/components/panels/ManeuverPanel";
import { useConstellation, useHealth } from "@/hooks/useAstrosisData";
import { useSelection, useEpoch } from "@/lib/astrosis/store";

export const Route = createFileRoute("/")({
  component: WorkbenchPage,
});

type Tab = "elements" | "ephemeris" | "passes" | "conjunctions" | "maneuver";

const TABS: { key: Tab; label: string }[] = [
  { key: "elements", label: "Elements" },
  { key: "ephemeris", label: "Ephemeris" },
  { key: "passes", label: "Passes" },
  { key: "conjunctions", label: "Conjunctions" },
  { key: "maneuver", label: "Maneuver" },
];

function WorkbenchPage() {
  const [tab, setTab] = useState<Tab>("elements");
  const [selectedId, setSelectedId] = useSelection();
  const epoch = useEpoch();
  const health = useHealth();
  const constellation = useConstellation();
  const utc = useUtcClock();
  const navigate = useNavigate();

  const satellites = constellation.data?.satellites ?? [];
  const backendLabel = health.data?.backend ?? constellation.data?.backend ?? "OFFLINE";
  const demoMode = constellation.data?.source === "offline-sgp4" || !health.data?.ok;
  const when = new Date(epoch.epoch_ms);

  return (
    <PageShell backendLabel={backendLabel} health={health.data}>
      <div className="h-full flex">
        <Sidebar
          satellites={satellites}
          selectedId={selectedId}
          onSelect={(id) => {
            if (id != null) navigate({ to: `/object/${id}` });
            else setSelectedId(null);
          }}
          demoMode={demoMode}
        />
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex-1 flex min-h-0">
            <div className="flex-1 min-w-0">
              <Globe
                satellites={satellites}
                selectedId={selectedId}
                onSelect={setSelectedId}
                when={when}
              />
            </div>
            <div className="w-[380px] hairline-l surface min-h-0 overflow-auto">
              <GroundTrack sats={satellites} selectedId={selectedId} when={when} />
            </div>
          </div>
          <div className="h-[240px] hairline-t surface flex flex-col">
            <div className="flex items-stretch text-[11px]">
              {TABS.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={`px-3 py-1.5 hairline-r ${
                    tab === t.key
                      ? "text-foreground bg-[var(--surface-2)]"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {t.label}
                </button>
              ))}
              <div className="flex-1" />
              <span className="tag px-3 py-1.5">{utc}</span>
            </div>
            <div className="flex-1 min-h-0 overflow-auto">
              {tab === "elements" && <ElementsPanel selectedId={selectedId} />}
              {tab === "ephemeris" && <EphemerisPanel selectedId={selectedId} />}
              {tab === "passes" && <PassesPanel selectedId={selectedId} />}
              {tab === "conjunctions" && <ConjunctionsPanel selectedId={selectedId} />}
              {tab === "maneuver" && <ManeuverPanel selectedId={selectedId} />}
            </div>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
