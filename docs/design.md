# Design Decisions

Technical rationale for key engineering decisions in Astrosis.

## 1. Why RK4 and not an adaptive step-size integrator (RK45 / Dormand-Prince)?

Fixed step sizes are GPU-friendly, SIMD-vectorizable, and produce predictable memory
usage. Adaptive methods offer better accuracy per CPU cycle for a single satellite;
fixed methods win decisively for batches of thousands.

**GPU argument:** A CUDA kernel processes all N satellites in a warp. If each satellite
uses a different step size, warp divergence destroys throughput. Fixed steps ensure
all threads execute the same number of instructions — zero divergence.

**Memory argument:** Adaptive methods store internal state per satellite (~6× state
vector). For 10,000 satellites this competes with L2 cache. Fixed-step RK4 uses
8 registers per thread with no dynamic memory.

**Accuracy:** RK4 with dt=10s for circular LEO:
- Local truncation error: O(dt⁵) ≈ 10⁻¹³ km per step
- Global error after 24h: O(dt⁴) ≈ 10⁻⁷ relative energy drift

For conjunction analysis, position accuracy < 0.1 km at 24h suffices (TLE uncertainty
itself is 0.1–1 km). RK4 at dt=10s is well within this margin.

| Context | Preferred method |
|---------|-----------------|
| Single high-eccentricity trajectory, long-arc maneuver design, re-entry | Adaptive (e.g., Dormand-Prince) |
| GPU-parallel batch propagation, real-time conjunction screening | Fixed RK4 |

## 2. Why J2/J3/J4 and not the full EGM2008 gravity model?

EGM2008 has 2,190 × 2,190 = 4.8 million spherical harmonic coefficients. Computing
them per satellite per step requires ~10 million FP64 multiply-adds and a 37 MB
coefficient table (exceeds GPU constant memory 16 MB limit).

**Perturbation contribution (LEO, 400 km circular):**

| Term | Acceleration | Contribution |
|------|-------------|-------------|
| Two-body | 8.7 km/s² | 100% |
| J2 | 2.6 × 10⁻³ km/s² | 0.030% |
| J3 | 2.0 × 10⁻⁶ km/s² | 0.000023% |
| J4 | 1.6 × 10⁻⁶ km/s² | 0.000018% |
| J5+ | < 5 × 10⁻⁷ km/s² | < 0.000006% |
| EGM2008 tesseral | < 2 × 10⁻⁷ km/s² | < 0.000002% |

J2–J4 captures >99.97% of the gravitational perturbation with 3 extra arithmetic
expressions per evaluation. Higher-order terms are swamped by TLE epoch uncertainty
(~0.3 km / orbit) within a few hours.

## 3. When does the propagator break down?

| Regime | Why it fails | Mitigation |
|--------|-------------|------------|
| High eccentricity (e > 0.5) | dt=10s too coarse near periapsis | Use smaller dt or adaptive method near periapsis |
| Very low altitude (< 180 km) | Drag model degrades; deceleration becomes large | Re-entry requires atmospheric uncertainty models |
| Long propagation (> 7 days) | J4/drag/SRP cross-coupling accumulates; error > 10 km | Refresh TLE every 1–2 days |
| Resonant orbits (GPS, Molniya) | Higher harmonics dominate at resonance | Add J5+ or switch to EGM2008 for these altitudes |
| Near-GEO | SRP and lunisolar become significant | Already included in force model |

## 4. AoS vs SoA Memory Layout

**AoS (Array-of-Structures):**
```
Memory: [x0,y0,z0,vx0,vy0,vz0, x1,y1,z1,vx1,vy1,vz1, ...]
```
Warp of 32 threads each reads `vy[threadIdx.x]` → offsets `{4, 10, 16, ...}` —
every 6th double. Requires 6 cache line loads for 32 doubles — **17% utilisation.**

**SoA (Structure-of-Arrays):**
```
Memory: [x0,x1,...,xN, y0,y1,...,yN, z0,..., vx0,..., vy0,..., vz0,...]
```
Warp reads `VY[threadIdx.x]` → offsets `{4N, 4N+1, ..., 4N+31}` —
32 consecutive doubles, one cache line — **100% utilisation.**

Measured improvement: ~1.4× throughput for N > 1000.

## 5. False Sharing in OpenMP Batch Propagator

The OpenMP batch propagator assigns one satellite per thread. With AoS layout,
two consecutive satellites (48 bytes each) share a 64-byte cache line. When
thread 0 writes satellite 0 and thread 1 writes satellite 1, they invalidate
each other's cache lines on every write.

**Fix:** `StateVector` is `alignas(64)` with 8 doubles (64 bytes). Each satellite
owns exactly one cache line.

## 6. C++ vs CUDA crossover

For **batch propagation**, C++/OpenMP beats CUDA at all tested problem sizes
(1k sats × 864 steps: C++ 13 ms vs CUDA 245 ms; 5k sats: C++ 55 ms vs CUDA
291 ms). CUDA launch overhead and PCIe transfer (~28 ms round trip) erode the
GPU advantage for pure integration.

CUDA dominates for **conjunction screening**, where pairwise distance calculations
are compute-bound and benefit from massive parallelism (400×400 pairs 2h:
C++ 3856 ms vs CUDA 125 ms — 31× speedup).

| Operation | Best backend |
|-----------|-------------|
| Batch propagation < 100 sats | Python or C++ |
| Batch propagation 100–5000 sats | C++/OpenMP |
| Batch propagation 5000+ sats | C++/OpenMP (CUDA competitive with streamed mode) |
| Conjunction screening | CUDA (31× over C++ for 400×400 pairs) |

## 7. Roofline Analysis (RTX 2050, FP64 RK4 kernel)

The `k_prop_soa` kernel was analysed using Nsight Compute:

| Metric | Value |
|--------|-------|
| Arithmetic intensity (AI) | ~2.5 FLOP/byte |
| Peak FP64 compute | 364 GFLOP/s |
| Peak memory bandwidth | 350 GB/s |
| Ridge point | 364 / 350 ≈ 1.04 FLOP/byte |

Since AI ≈ 2.5 > 1.04, the kernel is **compute-bound** on FP64 — performance
limited by FPU throughput, not memory access.

## 8. Conjunction TCA Accuracy

Before Brent's method, TCA accuracy was limited to ±step_s (typically ±60s).
At 7.66 km/s relative velocity, this translates to ±460 km uncertainty in miss
distance — unusable.

With Brent's method, the coarse sweep finds the bracket and Brent's 1D minimiser
converges to ±0.1s TCA accuracy in ≤ 50 iterations. At 7.66 km/s this gives
±0.76 km miss-distance accuracy — meaningful for CDM generation.

## 9. Probability of Collision (Chan's Method)

The simplified circular encounter:

```
Pc ≈ (HBR² / 2σ²) × exp(-x²/2)
```

where `HBR` = hard-body radius (10 m default), `σ` = combined 1-sigma position
uncertainty at TCA (km), `x` = miss_distance / σ.

Valid for dilute encounter regime (miss_distance >> σ), covering the vast
majority of CDM events. For miss_distance < σ, numerical integration of the
2D Gaussian is required (Foster/Patera refinement — not yet implemented).

Position uncertainty estimated from TLE age: `σ ≈ 0.3 × sqrt(TLE_age_days) km`
(Vallado 2013 empirical model for LEO).
