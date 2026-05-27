import { useQuery } from "@tanstack/react-query";
import { fetchHealth, fetchConstellation } from "@/lib/astrosis/client";
import { offlineConstellation } from "@/lib/astrosis/fallback";
import { getBackendUrl } from "@/lib/astrosis/store";
import type { BackendHealth, ConstellationResponse } from "@/lib/astrosis/types";

export function useHealth() {
  return useQuery<BackendHealth>({
    queryKey: ["health", getBackendUrl()],
    queryFn: ({ signal }) => fetchHealth(signal),
    retry: 0,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}

export function useConstellation(intervalMs = 30000) {
  return useQuery<ConstellationResponse>({
    queryKey: ["constellation", getBackendUrl()],
    queryFn: async ({ signal }) => {
      try {
        return await fetchConstellation(signal);
      } catch {
        // Engine unreachable — fall back to in-browser SGP4 over Celestrak TLEs.
        return await offlineConstellation("active");
      }
    },
    refetchInterval: intervalMs,
    refetchOnWindowFocus: false,
    staleTime: 15000,
  });
}
