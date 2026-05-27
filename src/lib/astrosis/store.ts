import { useSyncExternalStore } from "react";

// Lightweight external store with a single subscribe/notify pattern.
// Used for the backend URL (persisted) and the simulation epoch (transient).

type Listener = () => void;

function makeStore<T>(initial: T) {
  let value = initial;
  const listeners = new Set<Listener>();
  return {
    get: () => value,
    set: (next: T | ((prev: T) => T)) => {
      value = typeof next === "function" ? (next as (p: T) => T)(value) : next;
      listeners.forEach((l) => l());
    },
    subscribe: (l: Listener) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
  };
}

// --- Backend URL --------------------------------------------------

const BACKEND_KEY = "astrosis.backend_url";
const DEFAULT_BACKEND = "http://localhost:8000";

function loadBackend(): string {
  if (typeof window === "undefined") return DEFAULT_BACKEND;
  try {
    return localStorage.getItem(BACKEND_KEY) || DEFAULT_BACKEND;
  } catch {
    return DEFAULT_BACKEND;
  }
}

const backendStore = makeStore<string>(DEFAULT_BACKEND);
if (typeof window !== "undefined") {
  backendStore.set(loadBackend());
}

export function useBackendUrl(): [string, (u: string) => void] {
  const url = useSyncExternalStore(backendStore.subscribe, backendStore.get, () => DEFAULT_BACKEND);
  const set = (u: string) => {
    const trimmed = u.trim().replace(/\/$/, "") || DEFAULT_BACKEND;
    backendStore.set(trimmed);
    try {
      localStorage.setItem(BACKEND_KEY, trimmed);
    } catch {
      /* ignore */
    }
  };
  return [url, set];
}

export function getBackendUrl(): string {
  return backendStore.get();
}

// --- Simulation epoch --------------------------------------------
// Wall-clock UTC by default. The time control bar can pause and accelerate.

interface EpochState {
  epoch_ms: number; // sim time in ms (UTC epoch)
  paused: boolean;
  rate: number; // 1 = real time
  wall_ms: number; // last tick wall time
}

const epochStore = makeStore<EpochState>({
  epoch_ms: Date.now(),
  paused: false,
  rate: 1,
  wall_ms: Date.now(),
});

if (typeof window !== "undefined") {
  // 1 Hz tick. Time-sensitive panels can refresh on their own faster cadence.
  setInterval(() => {
    const s = epochStore.get();
    const now = Date.now();
    const dt = now - s.wall_ms;
    epochStore.set({
      ...s,
      wall_ms: now,
      epoch_ms: s.paused ? s.epoch_ms : s.epoch_ms + dt * s.rate,
    });
  }, 1000);
}

export function useEpoch() {
  const getServerSnapshot = () => {
    if (typeof window === "undefined") {
      return { epoch_ms: 0, paused: true, rate: 1, wall_ms: 0 };
    }
    return epochStore.get();
  };
  return useSyncExternalStore(epochStore.subscribe, epochStore.get, getServerSnapshot);
}

export const epochActions = {
  pause: () => epochStore.set((s) => ({ ...s, paused: true })),
  resume: () => epochStore.set((s) => ({ ...s, paused: false, wall_ms: Date.now() })),
  toggle: () => epochStore.set((s) => ({ ...s, paused: !s.paused, wall_ms: Date.now() })),
  setRate: (rate: number) => epochStore.set((s) => ({ ...s, rate, wall_ms: Date.now() })),
  step: (seconds: number) =>
    epochStore.set((s) => ({ ...s, epoch_ms: s.epoch_ms + seconds * 1000 })),
  resetToNow: () => epochStore.set((s) => ({ ...s, epoch_ms: Date.now(), wall_ms: Date.now() })),
};

// --- Selection ----------------------------------------------------

const selectionStore = makeStore<number | null>(null);

export function useSelection(): [number | null, (id: number | null) => void] {
  const id = useSyncExternalStore(selectionStore.subscribe, selectionStore.get, () => null);
  return [id, (next) => selectionStore.set(next)];
}
