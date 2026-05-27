import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { PageShell, useUtcClock } from "@/components/shell/Chrome";
import { useBackendUrl } from "@/lib/astrosis/store";
import { fetchHealth } from "@/lib/astrosis/client";
import { FASTAPI_PATCH } from "@/lib/astrosis/cors-patch";

export const Route = createFileRoute("/connect")({
  component: ConnectPage,
});

function ConnectPage() {
  const [url, setUrl] = useBackendUrl();
  const [inputUrl, setInputUrl] = useState(url);
  const utc = useUtcClock();

  const { data: health, isFetching } = useQuery({
    queryKey: ["health", url],
    queryFn: ({ signal }) => fetchHealth(signal),
    retry: 0,
    staleTime: 5000,
    refetchInterval: 5000,
    refetchOnWindowFocus: false,
  });

  function handleConnect() {
    setUrl(inputUrl);
  }

  return (
    <PageShell backendLabel={health?.backend ?? "—"} health={health}>
      <div className="h-full flex flex-col p-4 overflow-auto max-w-2xl">
        <h1 className="text-sm font-semibold mb-4">Connect Backend</h1>

        <div className="flex gap-2 mb-4">
          <input
            className="flex-1 hairline bg-transparent px-2 py-1.5 text-[11px] num text-foreground"
            value={inputUrl}
            onChange={(e) => setInputUrl(e.target.value)}
            placeholder="http://localhost:8000"
          />
          <button
            onClick={handleConnect}
            className="hairline px-3 py-1.5 text-[11px] text-foreground hover:bg-[var(--surface-2)]"
          >
            Connect
          </button>
        </div>

        <div className="surface hairline p-3 mb-4 text-[11px]">
          {isFetching ? (
            <span className="tag">checking...</span>
          ) : health ? (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="inline-block w-2 h-2" style={{ background: "var(--ok)" }} />
                <span className="font-medium text-foreground">CONNECTED</span>
              </div>
              <div className="font-mono text-muted-foreground text-[10px]">
                {health.backend} &middot; Engine {health.engine_version} &middot; CUDA:{" "}
                {health.cuda_available ? "Yes" : "No"}
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span
                  className="inline-block w-2 h-2"
                  style={{ background: "var(--destructive)" }}
                />
                <span className="font-medium text-muted-foreground">OFFLINE</span>
              </div>
              <div className="font-mono text-muted-foreground text-[10px]">
                Run: python server.py on port 8000
              </div>
            </div>
          )}
        </div>

        <h2 className="tag mb-2">FastAPI Extension Patch</h2>
        <p className="text-[10px] text-muted-foreground mb-2">
          Paste this into <code className="text-foreground">frontend/main.py</code> to enable all
          endpoints.
        </p>

        <div className="relative surface hairline">
          <pre className="text-[10px] p-3 overflow-auto max-h-96 font-mono text-foreground leading-relaxed">
            {FASTAPI_PATCH}
          </pre>
          <button
            onClick={() => navigator.clipboard.writeText(FASTAPI_PATCH)}
            className="absolute top-2 right-2 hairline px-2 py-0.5 text-[10px] text-muted-foreground hover:text-foreground"
          >
            Copy
          </button>
        </div>
      </div>
    </PageShell>
  );
}
