from importlib import import_module

from .cities import CITIES, resolve_location  # noqa: F401
from .frames import (  # noqa: F401
    gmst_from_datetime, eci_to_ecef, ecef_to_geodetic,
    geodetic_to_ecef, topocentric_aer, julian_date,
    equation_of_equinoxes, teme_to_eci,
)
from .visibility import sun_position_eci, check_eclipse, is_optically_visible  # noqa: F401

_LAZY_GEO = {
    "report_passes": (".analysis", "report_passes"),
}


def __getattr__(name: str):
    if name not in _LAZY_GEO:
        raise AttributeError(f"module 'engine.geo' has no attribute {name!r}")
    module_name, attr_name = _LAZY_GEO[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
