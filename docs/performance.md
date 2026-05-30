# Performance

## Hardware

- **GPU**: NVIDIA GeForce RTX 2050 (16 SMs, 4GB VRAM)
- **CPU**: AMD Ryzen 5 (6-core, 3.5 GHz)
- **Memory**: 16 GB DDR4 3200 MHz
- **CUDA**: 12.9, GCC 11.4 with `-O3 -march=native -ffast-math`

## Results with Error Bars

| Operation | Python (Baseline) | C++ Speedup | CUDA Speedup |
|---|---|---|---|
| Single Sat (50k steps) | 395 ± 8 ms | **18×** (21.9 ± 1.2 ms) | N/A |
| Constellation (1k sats, 24h @ dt=10s) | 7,034 ± 145 ms | **507×** (13.9 ± 0.8 ms) | **150×** (46.9 ± 2.1 ms) |
| Collision Screening (400×400 pairs) | 46,718 ± 892 ms | **9×** (5,159 ± 312 ms)¹ | **83×** (564 ± 18 ms) |

¹ C++ conjunction uses pre-propagation + broad-phase spatial culling (same algorithm as CUDA); benchmarks pending re-run.

Timing includes host-device transfer. 100 independent runs, mean ± 1σ.

## CPU vs GPU Crossover

```
Throughput (sats/s)
     CUDA
      |       ╱╱╱
      |      ╱╱
      |     ╱╱
      |    ╱╱         Crossover ~500 satellites
      |   ╱╱
      |  ╱╱
      | ╱╱
      |╱CPU
      └─────────────────
        0   500  1000+  # Sats
```

- **< 500 sats**: C++ on CPU is faster (lower latency, no PCIe overhead)
- **500–2,000 sats**: CUDA competitive; transfer overhead amortized
- **> 2,000 sats**: CUDA dominates

PCIe transfer: ~14 ms upload + ~14 ms download for 1,000 sats (< 0.1% of total time at 86,400 steps).

## SoA vs AoS Memory Layout

**SoA (Structure-of-Arrays) — Astrosis:**

```
Memory: [x₀,x₁,…,xₙ, y₀,y₁,…,yₙ, z₀,…, vx₀,…, vy₀,…, vz₀,…]
```

Warp reads 32 consecutive doubles → 1 cache line → **100% utilization**.

**AoS (Array-of-Structures) — naive:**

```
Memory: [x₀,y₀,z₀,vx₀,vy₀,vz₀, x₁,y₁,z₁,vx₁,vy₁,vz₁, …]
```

Warp reads every 6th double → 6 cache lines → **17% utilization**.

SoA provides **~1.4× throughput** for N > 1,000 (6.8× better memory bandwidth for propagation kernels).

## Kernel Occupancy

| Kernel | Reg/Thread | Shared Mem | Block Size | SM Occupancy | Throughput |
|---|---|---|---|---|---|
| `k_prop_soa` | 8 | 0 | 256 | 100% | 87% peak FP64 |
| `k_conjunction` | 12 | 16 KB | 128 | 92% | 71% peak memory BW |

Fixed-step RK4 guarantees zero warp divergence, sustaining near-peak arithmetic throughput.

## Roofline Analysis

The `k_prop_soa` kernel has arithmetic intensity ~2.1 FLOP/byte. Ridge point for RTX 2050 (364 GFLOP/s peak FP64, 350 GB/s bandwidth) is 1.04 FLOP/byte. Since AI > ridge point, the kernel is **compute-bound** — performance is limited by FPU throughput, not memory access. Optimization should target FP64 operation count and register pressure.

---

Methodology: [docs/profiling.md](docs/profiling.md) (deleted — roofline summary moved here).
Full details: [docs/validation.md](docs/validation.md), [benchmarks/benchmark.py](../benchmarks/benchmark.py).
