import math
import sys
import os
import logging
import numpy as np

from .propagator import rk4_step, propagate_batch_numpy

logger = logging.getLogger(__name__)


def _load_physics():
    _BUILD_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "cpp", "build")
    )
    _ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    for p in [_BUILD_DIR, _ROOT_DIR]:
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import physics_engine as _pe

        return _pe
    except ImportError:
        logger.warning("C++ physics_engine not found — using Python fallback.")
        return None


_physics = _load_physics()

_MOCK_GPU = os.environ.get("ASTROSIS_MOCK_GPU", "").lower() in ("1", "true", "yes")
_HAS_CPP = _physics is not None
_HAS_CUDA = (
    _HAS_CPP and not _MOCK_GPU and getattr(_physics, "cuda_available", lambda: False)()
)
_HAS_BATCH_CPP = _HAS_CPP and hasattr(_physics.Propagator, "batch_propagate_steps")

if _HAS_CUDA:
    logger.info("Backend: CUDA GPU")
elif _HAS_CPP:
    logger.info("Backend: C++ CPU")
else:
    logger.info("Backend: Python / NumPy")


def backend_info() -> dict:
    """Return backend availability and active backend description.

    Returns:
        dict with keys active, cuda, cpp, numpy_batch, python, description.
    """
    cuda = _HAS_CUDA
    cpp = _HAS_CPP
    active = "python"
    desc = "Python RK4 / SciPy"
    if cuda:
        active = "cuda"
        desc = "CUDA GPU (NVIDIA)"
    elif _HAS_BATCH_CPP:
        active = "cpp"
        desc = "C++ multi-threaded (OpenMP)"
    elif cpp:
        active = "cpp"
        desc = "C++ single-threaded"
    return {
        "active": active,
        "cuda": cuda,
        "cpp": cpp,
        "numpy_batch": True,
        "python": True,
        "description": desc,
    }


def propagate(state: list, dt_seconds: float, mjd0: float = 0.0) -> list:
    """
    Propagate a single state vector forward by dt_seconds.

    Uses C++ backend if available, falls back to pure Python RK4.

    Args:
        state: ECI state [x, y, z, vx, vy, vz] in km and km/s.
        dt_seconds: Time step in seconds.
        mjd0: Modified Julian Date at epoch (0 = no lunisolar/SRP).

    Returns:
        Propagated state list of 6 floats.
    """
    if _HAS_CPP:
        try:
            return list(_physics.Propagator().propagate(state, dt_seconds, mjd0))
        except Exception as e:
            logger.warning("C++ propagate failed, falling back: %s", e, exc_info=True)
    return list(rk4_step(tuple(state), dt_seconds, mjd0))


def propagate_with_drag(
    state: list,
    dt_seconds: float,
    area: float = 10.0,
    mass: float = 1000.0,
    cd: float = 2.2,
    cr: float = 1.5,
    mjd0: float = 0.0,
) -> list:
    """
    Propagate a single state with drag and SRP.

    Args:
        state: ECI state [x, y, z, vx, vy, vz] in km and km/s.
        dt_seconds: Time step in seconds.
        area: Cross-sectional area in m².
        mass: Spacecraft mass in kg.
        cd: Drag coefficient.
        cr: Reflectivity coefficient.
        mjd0: Modified Julian Date (0 = no lunisolar).

    Returns:
        Propagated state list of 6 floats.
    """
    if _HAS_CPP:
        try:
            return list(
                _physics.Propagator().propagate_with_drag(
                    state, dt_seconds, area, mass, cd, cr, mjd0
                )
            )
        except Exception as e:
            logger.warning(
                "C++ propagate_with_drag failed, falling back: %s", e, exc_info=True
            )
    return list(rk4_step(tuple(state), dt_seconds, mjd0, 0, area, mass, cd, cr))


def propagate_steps(
    state: list,
    total_seconds: float,
    step_size: float = 10.0,
    area: float = 0.0,
    mass: float = 1.0,
    cd: float = 2.2,
    cr: float = 1.5,
    with_drag: bool = False,
    mjd0: float = 0.0,
) -> list:
    """Propagate a single state over a time interval with sub-stepping.

    Uses C++ backend if available, falls back to pure Python RK4 loop.

    Args:
        state: ECI state [x, y, z, vx, vy, vz] in km and km/s.
        total_seconds: Total propagation time in seconds.
        step_size: Sub-step size in seconds.
        area: Cross-sectional area in m² (0 to skip drag).
        mass: Spacecraft mass in kg.
        cd: Drag coefficient.
        cr: Reflectivity coefficient.
        with_drag: Enable drag and SRP.
        mjd0: Modified Julian Date (0 = no lunisolar).

    Returns:
        Final propagated state list of 6 floats.
    """
    if _HAS_CPP:
        try:
            return list(
                _physics.Propagator().propagate_steps(
                    state, total_seconds, step_size, area, mass, cd, cr, with_drag, mjd0
                )
            )
        except Exception as e:
            logger.warning(
                "C++ propagate_steps failed, falling back: %s", e, exc_info=True
            )
    curr = tuple(state)
    rem = total_seconds
    steps_taken = 0
    elapsed = 0.0
    while rem > 0:
        dt = min(step_size, rem)
        curr = rk4_step(
            curr,
            dt,
            mjd0,
            steps_taken,
            area if with_drag else 0.0,
            mass,
            cd,
            cr,
            elapsed_seconds=elapsed,
        )
        rem -= dt
        steps_taken += 1
        elapsed += dt
    return list(curr)


def propagate_batch(
    states: list,
    dt_seconds: float,
    steps: int,
    area: float = 0.0,
    mass: float = 1.0,
    cd: float = 2.2,
    cr: float = 1.5,
    with_drag: bool = False,
    mjd0: float = 0.0,
) -> list:
    """
    Propagate multiple state vectors for a fixed number of steps.

    Automatically selects the fastest available backend:
    CUDA (SoA) → C++/OpenMP → NumPy → pure Python.

    Args:
        states: List of ECI state vectors, each [x, y, z, vx, vy, vz].
        dt_seconds: Time step in seconds.
        steps: Number of integration steps.
        area: Cross-sectional area in m² for drag/SRP.
        mass: Spacecraft mass in kg.
        cd: Drag coefficient.
        cr: Reflectivity coefficient.
        with_drag: Enable atmospheric drag and SRP.
        mjd0: Modified Julian Date (0 = no lunisolar).

    Returns:
        List of propagated state vectors.
    """
    arr = np.array(states, dtype=np.float64)

    if _HAS_CUDA:
        try:
            res = _physics.cuda_propagate_batch_soa(
                arr, dt_seconds, steps, area, mass, cd, cr, with_drag, mjd0
            )
            return res.tolist()
        except Exception as e:
            logger.warning(
                "CUDA propagate_batch failed, falling back: %s", e, exc_info=True
            )

    if _HAS_BATCH_CPP:
        try:
            prop = _physics.Propagator()
            if with_drag:
                res = prop.batch_propagate_steps_drag(
                    arr, dt_seconds, steps, area, mass, cd, cr, mjd0
                )
            else:
                res = prop.batch_propagate_steps(arr, dt_seconds, steps, mjd0)
            return res.tolist()
        except Exception as e:
            logger.warning(
                "C++ batch_propagate_steps failed, falling back: %s", e, exc_info=True
            )

    return propagate_batch_numpy(
        states, dt_seconds, steps, area, mass, cd, cr, with_drag, mjd0
    )


def propagate_batch_full_history(
    states: list,
    dt_seconds: float,
    steps: int,
    area: float = 0.0,
    mass: float = 1.0,
    cd: float = 2.2,
    cr: float = 1.5,
    with_drag: bool = False,
    mjd0: float = 0.0,
) -> np.ndarray:
    """Propagate multiple states and return full trajectory history.

    Returns all intermediate states for each object (steps+1 frames).
    CUDA path returns SoA-layout array; C++ and Python paths return
    AoS-layout array (shape [steps+1, n, 6]).

    Args:
        states: List of ECI state vectors.
        dt_seconds: Time step in seconds.
        steps: Number of integration steps.
        area: Cross-sectional area in m².
        mass: Spacecraft mass in kg.
        cd: Drag coefficient.
        cr: Reflectivity coefficient.
        with_drag: Enable drag and SRP.
        mjd0: Modified Julian Date.

    Returns:
        ndarray of shape (steps+1, n, 6).
    """
    arr = np.array(states, dtype=np.float64)

    if _HAS_CUDA:
        try:
            return _physics.cuda_propagate_full_history(
                arr, dt_seconds, steps, area, mass, cd, cr, with_drag, mjd0
            )
        except Exception as e:
            logger.warning(
                "CUDA propagate_full_history failed, falling back: %s", e, exc_info=True
            )

    if _HAS_BATCH_CPP:
        try:
            return _physics.Propagator().batch_propagate_full_history(
                arr, dt_seconds, steps, area, mass, cd, cr, with_drag, mjd0
            )
        except Exception as e:
            logger.warning(
                "C++ batch_propagate_full_history failed, falling back: %s",
                e,
                exc_info=True,
            )

    from .propagator import rk4_batch

    n = len(states)
    history = np.zeros((steps + 1, n, 6))
    history[0] = arr
    curr = arr.copy()
    for s in range(1, steps + 1):
        step_mjd0 = mjd0 + ((s - 1) * dt_seconds) / 86400.0 if mjd0 > 0 else 0.0
        curr = rk4_batch(curr, dt_seconds, 1, area, mass, cd, cr, with_drag, step_mjd0)
        history[s] = curr
    return history


def _cpp_warnings_to_py(warnings: list) -> list:
    """Convert C++ ConjunctionWarning objects (with C++ Severity enum) to
    Python ConjunctionWarning dataclass instances (with StrEnum Severity)."""
    from .conjunction import (
        ConjunctionWarning as PyWarning,
        Severity as PySeverity,
        PcResult,
    )

    _CPP_TO_PY = {
        _physics.Severity.NONE: PySeverity.NONE,
        _physics.Severity.ADVISORY: PySeverity.ADVISORY,
        _physics.Severity.WARNING: PySeverity.WARNING,
        _physics.Severity.CRITICAL: PySeverity.CRITICAL,
    }
    result = []
    for w in warnings:
        pw = PyWarning(
            sat_id=w.sat_id,
            debris_id=w.debris_id,
            current_distance=w.current_distance,
            time_to_closest_approach=w.time_to_closest_approach,
            severity=_CPP_TO_PY.get(w.severity, PySeverity.NONE),
            relative_velocity=list(w.relative_velocity),
            pc_result=PcResult(pc=w.pc, sigma_pos_km=w.pc_sigma_km),
        )
        result.append(pw)
    return result


def detect_conjunctions(
    sat_states: list,
    debris_states: list,
    lookahead: float = 86400.0,
    step_s: float = 60.0,
    mjd0: float = 0.0,
) -> list:
    """
    Screen all satellite-debris pairs for conjunctions within lookahead window.

    CUDA path uses 2-phase algorithm: pre-propagate all objects once,
    then scan pairs with coalesced SoA reads (O((ns+nd)*nsteps) pre-prop +
    O(ns*nd*nsteps) distance-only scan — ~250x faster for 500x500).

    Falls back through C++ → pure Python.

    Args:
        sat_states: List of satellite ECI state vectors.
        debris_states: List of debris ECI state vectors.
        lookahead: Lookahead window in seconds.
        step_s: Time step for temporal sweep in seconds.
        mjd0: Modified Julian Date at epoch.

    Returns:
        List of ConjunctionWarning dataclass instances.
    """
    if _HAS_CUDA:
        try:
            s_arr = np.array(sat_states, dtype=np.float64)
            d_arr = np.array(debris_states, dtype=np.float64)
            return _cpp_warnings_to_py(
                _physics.cuda_detect_conjunctions(s_arr, d_arr, lookahead, step_s, mjd0)
            )
        except Exception as e:
            logger.warning(
                "CUDA detect_conjunctions failed, falling back: %s", e, exc_info=True
            )

    if _HAS_CPP:
        try:
            s_arr = np.array(sat_states, dtype=np.float64)
            d_arr = np.array(debris_states, dtype=np.float64)
            return _cpp_warnings_to_py(
                _physics.ConjunctionDetector().detect(s_arr, d_arr, lookahead, step_s)
            )
        except Exception as e:
            logger.warning(
                "C++ detect_conjunctions failed, falling back: %s", e, exc_info=True
            )

    from .conjunction import ConjunctionDetector as PyConjunctionDetector

    detector = PyConjunctionDetector()
    return detector.detect(
        sat_states, debris_states, lookahead_s=lookahead, step_s=step_s, mjd0=mjd0
    )


def _monte_carlo_pc_python(
    sat_samples: np.ndarray,
    deb_samples: np.ndarray,
    dt: float,
    steps: int,
    threshold_km: float,
    mjd0: float = 0.0,
) -> float:
    n = sat_samples.shape[0]
    collisions = 0
    for i in range(n):
        s = tuple(sat_samples[i])
        d = tuple(deb_samples[i])
        min_dist = math.inf
        for step in range(steps + 1):
            dx = s[0] - d[0]
            dy = s[1] - d[1]
            dz = s[2] - d[2]
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist < min_dist:
                min_dist = dist
            if step < steps:
                s = rk4_step(s, dt, mjd0, step)
                d = rk4_step(d, dt, mjd0, step)
        if min_dist < threshold_km:
            collisions += 1
    return collisions / n if n > 0 else 0.0


def monte_carlo_pc(
    sat_samples: list,
    deb_samples: list,
    dt: float,
    steps: int,
    threshold_km: float,
    mjd0: float = 0.0,
) -> float:
    """
    Monte Carlo collision probability estimation.

    Propagates N sample pairs forward and counts those that pass
    within threshold_km. Uses CUDA if available, falls back to Python.

    Args:
        sat_samples: List of N satellite ECI state vectors.
        deb_samples: List of N debris ECI state vectors.
        dt: Propagation step in seconds.
        steps: Number of integration steps.
        threshold_km: Collision sphere radius in km.
        mjd0: Modified Julian Date at epoch.

    Returns:
        Estimated collision probability Pc ∈ [0, 1].
    """
    sat_arr = np.array(sat_samples, dtype=np.float64)
    deb_arr = np.array(deb_samples, dtype=np.float64)

    if _HAS_CUDA:
        try:
            return float(
                _physics.cuda_monte_carlo_pc(
                    sat_arr, deb_arr, dt, steps, threshold_km, mjd0
                )
            )
        except Exception as e:
            logger.warning(
                "CUDA monte_carlo_pc failed, falling back: %s", e, exc_info=True
            )

    return _monte_carlo_pc_python(sat_arr, deb_arr, dt, steps, threshold_km, mjd0)
