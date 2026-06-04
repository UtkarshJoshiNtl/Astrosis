__version__ = "0.1.0"
__all__ = [
    "propagate",
    "propagate_batch",
    "detect_conjunctions",
    "backend_info",
    "monte_carlo_pc",
    "sun_position_eci",
    "moon_position_eci",
    "gmst_from_datetime",
    "eci_to_ecef",
    "ecef_to_geodetic",
    "geodetic_to_ecef",
    "topocentric_aer",
    "check_eclipse",
    "is_optically_visible",
    "report_passes",
    "tle_ingestor",
    "TLEIngestor",
]

from importlib import import_module

from .constants import (  # noqa: F401
    MU,
    RE,
    J2,
    J3,
    J4,
    OMEGA_EARTH,
    MU_SUN,
    MU_MOON,
    F_WGS84,
    E2_WGS84,
    CRITICAL_DISTANCE,
    WARNING_DISTANCE,
    ADVISORY_DISTANCE,
    RS_SUN,
    AU,
    P_SR,
)

_LAZY_EXPORTS = {
    "rk4_step": (".core", "rk4_step"),
    "rk4_batch": (".core", "rk4_batch"),
    "ConjunctionDetector": (".core", "ConjunctionDetector"),
    "ConjunctionWarning": (".core", "ConjunctionWarning"),
    "propagate": (".core", "propagate"),
    "propagate_batch": (".core", "propagate_batch"),
    "detect_conjunctions": (".core", "detect_conjunctions"),
    "backend_info": (".core", "backend_info"),
    "monte_carlo_pc": (".core", "monte_carlo_pc"),
    "sun_position_eci": (".geo", "sun_position_eci"),
    "moon_position_eci": (".core", "moon_position_eci"),
    "gmst_from_datetime": (".geo", "gmst_from_datetime"),
    "eci_to_ecef": (".geo", "eci_to_ecef"),
    "ecef_to_geodetic": (".geo", "ecef_to_geodetic"),
    "geodetic_to_ecef": (".geo", "geodetic_to_ecef"),
    "topocentric_aer": (".geo", "topocentric_aer"),
    "check_eclipse": (".geo", "check_eclipse"),
    "is_optically_visible": (".geo", "is_optically_visible"),
    "report_passes": (".geo", "report_passes"),
    "tle_ingestor": (".io", "tle_ingestor"),
    "TLEIngestor": (".io", "TLEIngestor"),
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module 'astrosis' has no attribute {name!r}")
    module_name, attr_name = _LAZY_EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
