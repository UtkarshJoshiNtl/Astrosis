"""
benchmark.py — Performance Benchmark Suite
===========================================
Compares every available backend across:
  - Single-satellite propagation
  - Batch propagation (strong/weak scaling)
  - Conjunction detection
  - Fuel calculation
  - Maneuver planning

Generates:
  - Terminal report with speedups
  - CSV output for external plotting
  - Matplotlib scaling plots (--plot)

Usage:
    python benchmark.py                           # full benchmark
    python benchmark.py --quick                   # fast iteration
    python benchmark.py --csv results.csv         # CSV export
    python benchmark.py --plot                    # scaling plots (PNG)
    python benchmark.py --quick --csv --plot      # combine flags
"""

import argparse
import csv
import time
import sys
import os
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'cpp', 'build')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.core.propagator import rk4_step, rk4_batch, propagate_batch_numpy
from engine.core.conjunction import ConjunctionDetector as PyDetector
from engine.core.conjunction import ConjunctionWarning
from engine.core.fuel import FuelTracker as PyFuelTracker
from engine.core.maneuver import ManeuverCalculator as PyManeuverCalc
from engine.constants import MU, RE, INITIAL_FUEL, DRY_MASS
import numpy as np

try:
    import physics_engine as _cpp
    _HAS_CPP = True
    _HAS_CUDA = getattr(_cpp, 'cuda_available', lambda: False)()
    _HAS_BATCH = hasattr(_cpp.Propagator, 'batch_propagate_steps')
except ImportError:
    _cpp = None
    _HAS_CPP = False
    _HAS_CUDA = False
    _HAS_BATCH = False

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _HAS_MPL = True
except ImportError:
    _HAS_MPL = False

ISS_STATE = [-6371.0 + 400.0, 0.0, 0.0, 0.0, 7.66, 0.0]


def gen_states(n: int) -> Tuple[list, list]:
    sats, debs = [], []
    for i in range(n):
        sats.append([-6371+400+i*0.1, i*0.5, 0.0, 0.0, 7.66+i*0.001, 0.0])
        debs.append([-6371+405+i*0.1, i*0.5+1.0, 0.5, 0.1, 7.65+i*0.001, 0.1])
    return sats, debs


@dataclass
class BenchResult:
    name: str
    py_s:   Optional[float] = None
    np_s:   Optional[float] = None
    cpp_s:  Optional[float] = None
    cuda_s: Optional[float] = None
    note:   str = ""

    def speedup(self, ref, val) -> str:
        if ref is None or val is None or val == 0:
            return "N/A"
        return f"{ref/val:.1f}x"

    def row(self) -> str:
        def fmt(v): return f"{v*1000:8.1f} ms" if v is not None else "       N/A"
        return (f"  {self.name:<42} | {fmt(self.py_s)} | {fmt(self.np_s)} |"
                f" {fmt(self.cpp_s)} ({self.speedup(self.py_s, self.cpp_s):>6}) |"
                f" {fmt(self.cuda_s)} ({self.speedup(self.py_s, self.cuda_s):>6})")

    def csv_row(self) -> list:
        return [self.name, self.py_s, self.np_s, self.cpp_s, self.cuda_s]


def _t(fn) -> float:
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


# ── Benchmarks ────────────────────────────────────────────────────────────────

def bench_single_propagation(iters: int) -> BenchResult:
    r = BenchResult(f"Single propagation ({iters:,} iters)")
    def py():
        s = tuple(ISS_STATE)
        for _ in range(iters): s = rk4_step(s, 10.0)
    r.py_s = _t(py)
    arr = np.array([ISS_STATE])
    def np_fn():
        rk4_batch(arr, 10.0, iters)
    r.np_s = _t(np_fn)
    if _HAS_CPP:
        prop = _cpp.Propagator()
        def cpp():
            s = list(ISS_STATE)
            for _ in range(iters): s = list(prop.propagate(s, 10.0))
        r.cpp_s = _t(cpp)
    return r


def bench_batch_propagation(n: int, steps: int) -> BenchResult:
    r = BenchResult(f"Batch propagation ({n:,} sats x {steps:,} steps)")
    sats, _ = gen_states(n)
    dt = 10.0

    def py():
        ss = [tuple(s) for s in sats]
        for _ in range(steps):
            ss = [rk4_step(s, dt) for s in ss]
    r.py_s = _t(py)

    def np_fn():
        propagate_batch_numpy(sats, dt, steps)
    r.np_s = _t(np_fn)

    if _HAS_BATCH:
        prop = _cpp.Propagator()
        def cpp():
            arr = np.array(sats, dtype=np.float64)
            prop.batch_propagate_steps(arr, dt, steps)
        r.cpp_s = _t(cpp)

    if _HAS_CUDA:
        arr_cuda = np.array(sats, dtype=np.float64)
        def cuda_soa():
            _cpp.cuda_propagate_batch_soa(arr_cuda, dt, steps, 0, 1, 2.2, 1.5, False, 0)
        r.cuda_s = _t(cuda_soa)

        def cuda_stream():
            _cpp.cuda_propagate_batch_streamed(arr_cuda, dt, steps, 0, 1, 2.2, 1.5, False, 0)
        t_stream = _t(cuda_stream)
        r.note = f"SoA: {r.cuda_s*1000:.1f}ms | Stream: {t_stream*1000:.1f}ms"
    return r


def bench_conjunction(n: int, lookahead: float = 3600.0, step: float = 60.0) -> BenchResult:
    r = BenchResult(f"Conjunction detection ({n}x{n} pairs, {int(lookahead/3600)}h)")
    sats, debs = gen_states(n)

    def py():
        PyDetector().detect(sats, debs, lookahead_s=lookahead, step_s=step)
    r.py_s = _t(py)
    r.np_s = None

    if _HAS_CPP:
        def cpp():
            _cpp.ConjunctionDetector().detect(sats, debs, lookahead, step)
        r.cpp_s = _t(cpp)

    if _HAS_CUDA and hasattr(_cpp, 'cuda_detect_conjunctions'):
        def cuda():
            _cpp.cuda_detect_conjunctions(sats, debs, lookahead, step)
        r.cuda_s = _t(cuda)
    return r


def bench_fuel(iters: int) -> BenchResult:
    r = BenchResult(f"Fuel calculation ({iters:,} iters)")
    dv = [0.1, 0.2, 0.3]
    def py():
        t = PyFuelTracker(INITIAL_FUEL)
        for _ in range(iters): t.calculate_fuel_cost(dv)
    r.py_s = _t(py)
    r.np_s = None
    if _HAS_CPP:
        def cpp():
            t = _cpp.FuelTracker(INITIAL_FUEL, DRY_MASS)
            for _ in range(iters): t.calculate_fuel_cost(dv)
        r.cpp_s = _t(cpp)
    return r


def bench_maneuver(iters: int) -> BenchResult:
    r = BenchResult(f"Maneuver calculation ({iters:,} iters)")
    if _HAS_CPP:
        w = _cpp.ConjunctionWarning()
        w.sat_id = 0; w.debris_id = 1; w.current_distance = 5.0
        w.time_to_closest_approach = 3600.0; w.severity = "WARNING"
        w.relative_velocity = [0.1, 0.2, 0.3]
    else:
        w = ConjunctionWarning(sat_id=0, debris_id=1, current_distance=5.0,
                               time_to_closest_approach=3600.0, severity="WARNING",
                               relative_velocity=[0.1, 0.2, 0.3])

    def py():
        calc = PyManeuverCalc()
        py_w = w
        if _HAS_CPP:
            py_w = ConjunctionWarning(sat_id=w.sat_id, debris_id=w.debris_id,
                                      current_distance=w.current_distance,
                                      time_to_closest_approach=w.time_to_closest_approach,
                                      severity=w.severity,
                                      relative_velocity=list(w.relative_velocity))
        for _ in range(iters): calc.calculate(ISS_STATE, py_w)
    r.py_s = _t(py)

    if _HAS_CPP:
        calc = _cpp.ManeuverCalculator()
        def cpp():
            for _ in range(iters): calc.calculate(ISS_STATE, w)
        r.cpp_s = _t(cpp)
    return r


# ── Scaling benchmarks ────────────────────────────────────────────────────────

def bench_strong_scaling(sizes: List[int], steps: int = 100) -> List[BenchResult]:
    """Fixed total workload, vary number of satellites."""
    results = []
    for n in sizes:
        r = bench_batch_propagation(n, steps)
        r.name = f"Strong scaling (N={n})"
        results.append(r)
    return results


def bench_weak_scaling(sizes: List[int], steps_per_sat: int = 10) -> List[BenchResult]:
    """Fixed work per satellite: steps ~ n * steps_per_sat."""
    results = []
    for n in sizes:
        steps = n * steps_per_sat
        r = bench_batch_propagation(n, steps)
        r.name = f"Weak scaling (N={n})"
        results.append(r)
    return results


# ── Plotting ──────────────────────────────────────────────────────────────────

def plot_scaling(results: List[BenchResult], label: str, filename: str):
    if not _HAS_MPL:
        print("  [SKIP] matplotlib not installed — install with: pip install matplotlib")
        return

    ns = []
    py_t, np_t, cpp_t, cuda_t = [], [], [], []
    for r in results:
        ns.append(int(r.name.split("N=")[1].split(")")[0]))
        py_t.append(r.py_s or 0)
        np_t.append(r.np_s or 0)
        cpp_t.append(r.cpp_s or 0)
        cuda_t.append(r.cuda_s or 0)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.plot(ns, [t * 1000 for t in py_t], 'o-', label='Python')
    ax1.plot(ns, [t * 1000 for t in np_t], 's-', label='NumPy')
    ax1.plot(ns, [t * 1000 for t in cpp_t], '^-', label='C++')
    if any(cuda_t):
        ax1.plot(ns, [t * 1000 for t in cuda_t], 'v-', label='CUDA')
    ax1.set_xlabel('Number of satellites')
    ax1.set_ylabel('Time (ms)')
    ax1.set_title(f'{label} — Latency')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    if any(cpp_t):
        speedups = [py / max(cpp, 1e-9) for py, cpp in zip(py_t, cpp_t)]
        ax2.plot(ns, speedups, '^-', label='Python/C++')
    if any(cuda_t):
        speedups = [py / max(cuda, 1e-9) for py, cuda in zip(py_t, cuda_t)]
        ax2.plot(ns, speedups, 'v-', label='Python/CUDA')
    if any(np_t):
        speedups = [py / max(np, 1e-9) for py, np in zip(py_t, np_t)]
        ax2.plot(ns, speedups, 's-', label='Python/NumPy')
    ax2.set_xlabel('Number of satellites')
    ax2.set_ylabel('Speedup over Python')
    ax2.set_title(f'{label} — Speedup')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    out = os.path.join(os.path.dirname(__file__), filename)
    plt.savefig(out, dpi=150)
    print(f"  [PLOT] Saved {out}")
    plt.close()


# ── Report ────────────────────────────────────────────────────────────────────

def print_header():
    sep = "─" * 120
    print(f"\n{'Astrosis Performance Benchmark':^120}")
    print(sep)
    backends = []
    backends.append("Python OK")
    backends.append("NumPy OK")
    backends.append(f"C++ {'OK' if _HAS_CPP else 'MISSING'}")
    backends.append(f"CUDA {'OK' if _HAS_CUDA else 'MISSING (no nvcc)'}")
    print(f"  Backends: {' | '.join(backends)}")
    if _HAS_CUDA:
        _cpp.cuda_print_device_info()
    print(sep)
    print(f"  {'Benchmark':<42} | {'Python':>10} | {'NumPy':>10} |"
          f" {'C++ (speedup)':>20} | {'CUDA (speedup)':>20}")
    print(sep)


def print_footer(results: List[BenchResult]):
    sep = "─" * 120
    print(sep)
    batch = next((r for r in results if "Batch" in r.name), None)
    if batch:
        print(f"\n  Key metric — Batch Propagation:")
        if batch.np_s:
            print(f"    NumPy  vs Python: {batch.py_s/max(batch.np_s,1e-9):>8.1f}x")
        if batch.cpp_s:
            print(f"    C++    vs Python: {batch.py_s/max(batch.cpp_s,1e-9):>8.1f}x")
        if batch.cuda_s:
            print(f"    CUDA   vs Python: {batch.py_s/max(batch.cuda_s,1e-9):>8.1f}x")
            if batch.cpp_s:
                print(f"    CUDA   vs C++:    {batch.cpp_s/max(batch.cuda_s,1e-9):>8.1f}x")

    print(f"\n  Satellites/second (Python):  {1/max(batch.py_s,1e-9):.0f}" if batch and batch.py_s else "")
    print(f"  Satellites/second (CUDA):    {1/max(batch.cuda_s,1e-9):.0f}" if batch and batch.cuda_s else "")

    if not _HAS_CPP:
        print("\n  [WARN] C++ module not built — cd cpp && mkdir build && cd build && cmake .. && make")
    if not _HAS_CUDA:
        print("  [WARN] CUDA not available — install CUDA Toolkit, then cmake .. -DUSE_CUDA=ON && make")
    print()


def write_csv(results: List[BenchResult], path: str):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['benchmark', 'python_s', 'numpy_s', 'cpp_s', 'cuda_s'])
        for r in results:
            w.writerow(r.csv_row())
    print(f"  [CSV] Saved {path}")


def main(quick: bool = False, csv_path: Optional[str] = None, do_plot: bool = False):
    if _HAS_CUDA:
        _cpp.cuda_propagate_batch_soa(np.array([[RE+400, 0, 0, 0, 7.6, 0]]), 10.0, 1, 0, 1, 2.2, 1.5, False, 0)

    print_header()
    results = []

    if quick:
        configs = dict(single_iters=5_000, batch_n=200, batch_steps=100,
                       conj_n=50, fuel_iters=10_000, man_iters=1_000)
    else:
        configs = dict(single_iters=50_000, batch_n=1_000, batch_steps=864,
                       conj_n=200, fuel_iters=100_000, man_iters=10_000)

    for fn, args in [
        (bench_single_propagation, (configs['single_iters'],)),
        (bench_batch_propagation,  (configs['batch_n'], configs['batch_steps'])),
        (bench_batch_propagation,  (configs['batch_n']*5, configs['batch_steps'])),
        (bench_conjunction,        (configs['conj_n'],)),
        (bench_conjunction,        (configs['conj_n']*2, 7200.0, 60.0)),
        (bench_fuel,               (configs['fuel_iters'],)),
        (bench_maneuver,           (configs['man_iters'],)),
    ]:
        r = fn(*args)
        results.append(r)
        print(r.row() + (f"  [{r.note}]" if r.note else ""))

    if do_plot:
        print("\n  Running scaling benchmarks...")
        scaling_sizes = [100, 200, 500, 1000, 2000]
        strong = bench_strong_scaling(scaling_sizes)
        for r in strong:
            print(r.row())
        weak = bench_weak_scaling([100, 200, 500, 1000])
        for r in weak:
            print(r.row())
        results += strong + weak
        plot_scaling(strong, "Strong Scaling", "strong_scaling.png")
        plot_scaling(weak, "Weak Scaling", "weak_scaling.png")

    print_footer(results)

    if csv_path:
        write_csv(results, csv_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Astrosis backend benchmark")
    parser.add_argument("--quick", action="store_true", help="Smaller workloads for fast iteration")
    parser.add_argument("--csv", type=str, help="Export results to CSV file")
    parser.add_argument("--plot", action="store_true", help="Generate scaling plots (req. matplotlib)")
    args = parser.parse_args()
    main(quick=args.quick, csv_path=args.csv, do_plot=args.plot)
