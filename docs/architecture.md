# Architecture

```mermaid
graph TB
    subgraph UI["User Interface"]
        CLI["astrosis/cli.py"]
        TUI["astrosis/tui.py"]
        API["astrosis.*"]
    end

    subgraph CORE["Physics Core (astrosis/core/)"]
        PROP["Propagator<br/>RK4 · J2–J4 · Drag · SRP<br/>Lunisolar"]
        CONJ["Conjunction Detector<br/>KDTree · Brent TCA<br/>Chan Pc"]
        PASS["Pass Predictor<br/>SGP4→RK4 · AER<br/>Eclipse check"]
        EPHEM["Ephemeris<br/>Sun VSOP87 · Moon ELP-2000"]
        ACCEL["Accelerator<br/>Auto-backend router"]
    end

    subgraph GEO["Coordinate Frames (astrosis/geo/)"]
        FRAMES["ECI ↔ ECEF ↔ Geodetic<br/>TEME→ECI · Topocentric"]
        VIS["Visibility<br/>Eclipse check<br/>Optical visibility"]
    end

    subgraph BACKEND["Backend Layer (auto-selected)"]
        CUDA["CUDA GPU<br/>SoA kernels"]
        CPP["C++ / OpenMP<br/>pybind11"]
        NUMPY["NumPy batch<br/>Vectorised"]
        PYTHON["Python fallback"]
    end

    subgraph DATA["Data Sources"]
        TLE["TLE Ingestor<br/>CelesTrak / Space-Track"]
        CITIES["City Database<br/>~85 cities"]
    end

    CLI --> CORE
    TUI --> API
    API --> CORE
    PROP --> ACCEL
    CONJ --> ACCEL
    PASS --> FRAMES
    PASS --> PROP
    PASS --> EPHEM
    CONJ --> PROP
    TLE --> PASS
    CITIES --> PASS
```

The router in `astrosis/core/accelerator.py` probes `cuda_available()`, C++ module
presence, and falls back through the layers.

## Backend Selection

Auto-chooses the best backend based on hardware:

```
CUDA available?
  ├─ CUDA (conjunction pairs)     → CUDA (125 ms for 400×400 pairs)
  ├─ CUDA (batch prop < 5000)     → C++/OpenMP (lower latency)
  └─ No CUDA ─┬─ C++ compiled? ─┬─ Yes → C++/OpenMP
               │                 └─ No  ──┬─ NumPy? → NumPy batch
               │                          └─ No     → pure Python
```

| Factor | Decision |
|--------|----------|
| Conjunction screening | Always prefer CUDA (31× over C++) |
| Batch propagation < 5000 | C++/OpenMP (no PCIe overhead) |
| Batch propagation 5000+ | C++/OpenMP typically faster; CUDA competitive with streamed mode |

Manual override: `ASTROSIS_MOCK_GPU=1` forces CPU.

## Data Flow: Batch Propagation

```
propagate_batch(states, dt_seconds=10, steps=8640)   # 1000 sats, 24h

  accelerator.py
    → Detects 1000 sats → C++ selected (OpenMP)
    → Python ↔ C++ FFI (pybind11)
    → One satellite per thread, aligned to 64-byte cache lines
    → C++ returns (n, 6) array in ~13 ms
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
