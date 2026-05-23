
## What's actually in `alpha` (verified, not invented)

FastAPI server (`frontend/main.py`):
- `GET /` — serves `frontend/index.html`
- `GET /api/constellation` — 500 fake LEO seeds propagated +60 s, returns `[{id, pos:[x,y,z]}]` only

Engine surface that is **already implemented but not exposed over HTTP**:
- `engine.core.accelerator.propagate_batch(states, dt_seconds, steps)` — batch RK4 with auto-selected backend (CUDA / C++ / NumPy / Python) and `backend_info()`
- `engine.simulation.SimulationContext` — `load_tle(norad_id)`, `propagate(sat, hours, dt_seconds)`, `conjunction_assessment([sats])`, `plan_hohmann_transfer(sat, target_sma_km)`
- `engine.core.conjunction` — KDTree broad-phase, Brent TCA refinement, Chan Pc
- `engine.core.maneuver`, `engine.core.fuel` — Δv and propellant mass
- `engine.geo.frames` — ECI/ECEF/LLA/topo
- `engine.geo.analysis`, `engine.geo.visibility` — passes / elevation
- `engine.io.data` — Celestrak TLE fetch + cache
- CLI: `python main.py fetch --id N`, `passes --id N --lat --lon`, `run`, `conjunction`

This is a full orbital workbench. The current frontend exposes ~1 % of it.

## Two-part deliverable

### Part 1 — Drop-in FastAPI extension (ships as a patch the user pastes into `frontend/main.py`)

Adds CORS + the missing endpoints so the engine is actually reachable. Stays in one file, no new dependencies beyond FastAPI/pydantic already present.

```text
GET  /api/health              backend_info(), engine version, CUDA available
GET  /api/constellation       enriched: pos km, vel km/s, altitude, incl, period, epoch (UTC ISO)
                              ?n=500&seed=42  (deterministic), unchanged default behaviour
GET  /api/catalog/{norad}     SimulationContext.load_tle — TLE lines + Keplerian elements
POST /api/propagate           body: {norad|state, hours, dt_seconds}
                              returns ephemeris [{t, pos, vel}] (capped at 10k pts)
POST /api/passes              body: {norad, lat, lon, alt_m, hours}
                              returns [{aos, los, max_el, az_aos, az_los}]
POST /api/conjunctions        body: {norads:[…], hours, threshold_km}
                              returns [{a, b, tca, miss_km, rel_vel, pc}]
POST /api/maneuver/hohmann    body: {norad, target_sma_km, isp_s, dry_mass_kg, prop_mass_kg}
                              returns {dv1, dv2, dv_total, transfer_time, fuel_used_kg, fuel_remaining_kg}
```

Plus `app.add_middleware(CORSMiddleware, allow_origins=["*"], …)` so the hosted preview can talk to the user's local server. Patch is shown verbatim on an in-app **Connect Backend** screen with a copy button.

### Part 2 — Frontend rebuild (this project)

Architecture: workbench, not landing page. Restrained scientific UI. Same canvas, four "instruments" the user can pin/unpin in a grid (think DAW/Bloomberg/MATLAB-IDE feel without the cheese).

#### Design system (sober, coherent)

- Palette — **paper / ink + one technical amber accent**, period.
  - bg `oklch(0.16 0.005 250)`, surface `oklch(0.19 0.005 250)`, foreground `oklch(0.95 0.005 250)`, muted `oklch(0.65 0.01 250)`, hairline `oklch(1 0 0 / 10%)`
  - Accent: `oklch(0.78 0.13 75)` (amber). Status only: muted red `oklch(0.62 0.16 25)`, muted green `oklch(0.68 0.13 145)`. No gradients. No glow. No backdrop-blur. No "grad-text". No rainbow color ramps on data.
- Type — IBM Plex Sans (UI) + IBM Plex Mono (numbers, coords, TLE). 13 px default, 11 px mono, `font-feature-settings:"tnum","zero","ss01"`.
- Shape — `--radius: 2px`. 1 px hairlines. No drop shadows. No blur.
- Strip and rewrite `src/styles.css`; delete `.glass`, `.grad-text`, the cyan/violet ramp.

#### Layout (single screen, dense)

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ ASTROSIS · UTC 2026-05-23T11:07:43Z · backend: CUDA 12.9 (16 SMs) · ●live │  ← top bar
├──────────┬───────────────────────────────────────────────────────────────┤
│ catalog  │  3D globe (restrained)        │  2D ground track             │
│ tree     │  ECI axes, equator ring,      │  equirectangular SVG, lat/lon│
│ filters  │  no atmosphere haze, single   │  graticule, sub-sat point    │
│ search   │  amber accent for selection   │  + footprint circle          │
│ TLE drop ├───────────────────────────────┴───────────────────────────────┤
│          │ Inspector / Workbench tabs:                                  │
│          │ [Elements] [Ephemeris] [Passes] [Conjunctions] [Maneuver]    │
│          │ (dense table or labeled chart, tabular numerals)             │
└──────────┴───────────────────────────────────────────────────────────────┘
```

No floating glass cards. Solid surfaces, hairline dividers.

#### Routes (file-based, real per-page metadata)

- `/` — workbench (default catalog: `/api/constellation`)
- `/object/$norad` — same workbench, focus locked on one object, ephemeris auto-loaded
- `/conjunctions` — full-screen pair table + 3D miss-distance plot
- `/maneuver` — Hohmann planner: source orbit, target SMA, Isp, mass → Δv stages + fuel bar + new orbit overlay
- `/performance` — real numbers from `docs/performance.md` (markdown-rendered table + Recharts bar of the actual values; not a fake live benchmark)
- `/validation` — gallery of the *actual* PNGs from `validation/plots/` referenced from `raw.githubusercontent.com/.../alpha/...` with captions pulled from `docs/validation.md`
- `/docs` — markdown render of `docs/architecture.md`, `design.md`, `profiling.md`, `validation.md` with TOC
- `/connect` — backend URL input, health check, CORS patch copy-block, link to local install

#### Data layer

- `src/lib/astrosis/client.ts` — typed client over the new endpoints, configurable base URL (persisted to localStorage, default `http://localhost:8000`).
- TanStack Query, `ensureQueryData` in loaders + `useSuspenseQuery` in components (canonical shape).
- `src/lib/astrosis/fallback.ts` — if `/api/health` is unreachable: keep the app fully functional by parsing Celestrak TLEs (via a `/api/public/tle` server route in TanStack to dodge CORS) and propagating with `satellite.js` SGP4 in the browser. Banner clearly labels it `OFFLINE · SGP4 reference (Astrosis engine unavailable)`. No silent fake data ever.
- Time control bar (UTC clock, ±speed, pause, step). All views read from a shared `useEpoch()` store.

#### Components (focused, replacing the current ones)

- `components/shell/TopBar.tsx`, `Sidebar.tsx` — workstation chrome.
- `components/globe/Earth.tsx` (rewrite) — solid shaded sphere, ECI axes, equator + prime meridian rings, no wireframe overlay, no haze.
- `components/globe/SatelliteLayer.tsx` — instanced points, **single accent**, size encodes selection only.
- `components/groundtrack/GroundTrack2D.tsx` — SVG world map (lightweight topojson), graticule, ground-track polyline for selected object, sub-satellite marker + visibility footprint.
- `components/panels/ElementsPanel.tsx` — Keplerian elements + TLE + state vector, hairline label/value rows.
- `components/panels/EphemerisPanel.tsx` — line plot of altitude/range and 3D mini-trajectory; calls `/api/propagate`.
- `components/panels/PassesPanel.tsx` — calls `/api/passes` with a ground-station input (geolocation button). Table of next 24 h passes + azimuth polar plot.
- `components/panels/ConjunctionsPanel.tsx` — calls `/api/conjunctions`, lists TCA / miss / Pc with Pc colour bands explained in a footnote.
- `components/panels/ManeuverPanel.tsx` — Hohmann form, Δv breakdown, fuel mass before/after, new orbit overlay on the 3D view.
- `components/catalog/CatalogTable.tsx` — virtualised, sortable, keyboard-navigable.
- `components/charts/Plot.tsx` — Recharts wrapper with consistent grid/axes (no decorations, real units on axes, monospace tick labels).

#### Files to delete / rewrite

Delete: `components/globe/*` (rewrite smaller), `components/panels/*` (replaced), `lib/mock-constellation.ts` (replaced by labeled SGP4 fallback), `lib/astrosis-api.ts`, `hooks/useConstellation.ts`. Update `styles.css`, `routes/index.tsx`, `routes/__root.tsx`, `routes/constellation.tsx`, `routes/performance.tsx`, `routes/about.tsx` (becomes `/connect` + `/docs`). Add `routes/object.$norad.tsx`, `routes/conjunctions.tsx`, `routes/maneuver.tsx`, `routes/validation.tsx`, `routes/docs.tsx`, `routes/api/public/tle.ts`.

#### Dependencies

Add: `satellite.js` (SGP4 fallback only), `react-markdown` + `remark-gfm` (docs), `recharts` (plots), `@tanstack/react-virtual` (catalog table). Keep `three`/`@react-three/fiber` for the small globe; drop `@react-three/drei` extras we don't need (no stars background, no html labels).

## Honesty rules baked in

- Every panel surfaces the active backend (CUDA / C++ / NumPy / Python / `OFFLINE-SGP4`) and the data epoch.
- No invented endpoints. Every fetch hits an endpoint that exists either in the patched FastAPI or the explicit `/api/public/tle` server route.
- Pc, conjunctions, and the maneuver panel reproduce the README's caveats inline ("Pc model experimental", "fixed-step RK4 limitations") — small italic footnotes, not marketing copy.

## Out of scope (this turn)

- Hosting the Python engine ourselves (would need a long-running Python host; Cloudflare Worker can't run it).
- Auth, persistence, Cloud — not needed.
- Replacing the SGP4 fallback with WASM-compiled Astrosis (interesting follow-up).
