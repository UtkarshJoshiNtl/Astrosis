# Architecture

## System Overview

```
                    User Interfaces
                ┌──────────┬──────────────┐
                │  CLI     │  Python API  │
                │ main.py  │  engine.*    │
                └──────────┴──────────────┘
                              │
                ┌─────────────┴─────────────┐
                │     Physics Core          │
                │  (engine/core/)           │
                │  propagator, conjunction, │
                │  ephemeris, accelerator   │
                └─────────────┬─────────────┘
                              │
        ┌─────────────────────┼──────────────────────┐
        │                     │                      │
  ┌─────┴──────────┐  ┌───────┴─────────┐  ┌────────┴──────────┐
  │  Coordinate    │  │  I/O & Catalog  │  │  Backend Layer   │
  │  Transforms    │  │  TLE, caching   │  │  (auto-detected) │
  │  (geo/)        │  │  (io/)          │  │                   │
  └────────────────┘  └─────────────────┘  │  CUDA → C++       │
                                           │  → NumPy → Python │
                                           └────────────────────┘
```

## Backend Selection

Astrosis automatically chooses the best backend based on hardware availability:

```
CUDA available?
  ├─ Yes ──┬─ Problem size > 500 sats? → CUDA (82× speedup)
  │        └─ No                        → C++ (lower latency)
  └─ No ───┬─ C++ compiled? ──┬─ Yes → C++/OpenMP (18× speedup)
           │                  └─ No  ──┬─ NumPy? → NumPy (3–5×)
           │                           └─ No     → pure Python
```

| Factor | Threshold | Decision |
|--------|-----------|----------|
| Satellites | < 500 | Prefer C++ (lower launch overhead) |
| Satellites | 500–2,000 | CUDA competitive |
| Satellites | > 2,000 | Strongly prefer CUDA |
| Steps | < 10,000 | CPU typically adequate |
| Steps | > 100,000 | CUDA essential for real-time |
| dt | > 60 s | CPU competitive (fewer steps) |
| dt | 1–10 s | CUDA advantage grows |

Manual override: `ASTROSIS_MOCK_GPU=1` forces CPU.

## Data Flow: Batch Propagation

```
propagate_batch(states, dt_seconds=10, steps=8640)   # 1,000 sats, 24h

  accelerator.py
    → Detects 1,000 sats → CUDA selected
    → Python ↔ C++ FFI (pybind11)
    → GPU Memory: SoA layout [x₀..xₙ₋₁, y₀..yₙ₋₁, ..., vz₀..vzₙ₋₁] (48 KB)
    → CUDA Kernel: 1 launch, all 4 RK4 stages internally
      for step in 0..8640:
        rk4_step_device(x, y, z, vx, vy, vz)
    → GPU → host download (48 KB, ~14 ms)
    → Final: 1,000 × 6 state array in 46.9 ± 2.1 ms
```

## Data Flow: Conjunction Screening

```
detect_conjunctions(sats, debs, lookahead=36000, step_s=60)   # 500×500 pairs

  CUDA Path (2-phase):

  Phase 1 — Pre-propagation (k_prepropagate)
    Propagate 500 sats + 500 debs for 600 steps each
    Store trajectory as SoA per timestep
    Cost: O((ns+nd) × nsteps) = 600K propagations

  Phase 2 — Pair Scan (k_scan_pairs)
    Grid: (500/16, 500/16) blocks × (16,16) threads
    Coalesced reads of pre-propagated SoA arrays
    Cost: O(ns × nd × nsteps) = 150M distance calcs (no RK4)

  Speedup vs naive: ~250× (every distance calc avoids 1 propagation)
```

C++ fallback: pre-propagates all objects via `batch_propagate_full_history`,
then pairwise distance scan + Brent refinement from nearest pre-propagated frame.
