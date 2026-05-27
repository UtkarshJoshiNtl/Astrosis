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
import { useEpoch } from "@/lib/astrosis/store";

export const Route = createFileRoute("/object/$norad")({
  component: ObjectPage,
});

type Tab = "elements" | "ephemeris" | "passes" | "conjunctions" | "maneuver";

const TABS: { key: Tab; label: string }[] = [
  { key: "elements", label: "Elements" },
  { key: "ephemeris", label: "Ephemeris" },
  { key: "passes", label: "Passes" },
  { key: "conjunctions", label: "Conjunctions" },
  { key: "maneuver", label: "Maneuver" },
];

function ObjectPage() {
  const { norad } = Route.useParams();
  const noradId = parseInt(norad, 10);
  const [tab, setTab] = useState<Tab>("elements");
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
          selectedId={noradId}
          onSelect={(id) => {
            if (id != null) navigate({ to: `/object/${id}` });
          }}
          demoMode={demoMode}
        />
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex-1 flex min-h-0">
            <div className="flex-1 min-w-0">
              <Globe
                satellites={satellites}
                selectedId={noradId}
                onSelect={(id) => navigate({ to: `/object/${id}` })}
                when={when}
              />
            </div>
            <div className="w-[380px] hairline-l surface min-h-0 overflow-auto">
              <GroundTrack sats={satellites} selectedId={noradId} when={when} />
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
              {tab === "elements" && <ElementsPanel selectedId={noradId} />}
              {tab === "ephemeris" && <EphemerisPanel selectedId={noradId} />}
              {tab === "passes" && <PassesPanel selectedId={noradId} />}
              {tab === "conjunctions" && <ConjunctionsPanel selectedId={noradId} />}
              {tab === "maneuver" && <ManeuverPanel selectedId={noradId} />}
            </div>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
