import numpy as np
from datetime import datetime
from ..constants import RE, RS_SUN
from ..core.ephemeris import sun_position_eci as _sun_eci_mjd
from .frames import julian_date

__all__ = ["sun_position_eci", "check_eclipse", "is_optically_visible"]


def sun_position_eci(dt: datetime) -> np.ndarray:
    mjd = julian_date(dt) - 2400000.5
    return np.array(_sun_eci_mjd(mjd))


def check_eclipse(r_sat: np.ndarray, r_sun: np.ndarray) -> str:
    sat_mag = np.linalg.norm(r_sat)
    sun_mag = np.linalg.norm(r_sun)
    sun_hat = r_sun / sun_mag
    sat_proj = np.dot(r_sat, sun_hat)

    if sat_proj > 0:
        return "SUNLIGHT"

    perp = np.sqrt(max(sat_mag**2 - sat_proj**2, 0.0))
    sin_pen = (RS_SUN + RE) / sun_mag
    sin_umb = (RS_SUN - RE) / sun_mag
    axis_dist = abs(sat_proj)
    pen_radius = RE + axis_dist * sin_pen
    umb_radius = RE - axis_dist * sin_umb

    if perp < umb_radius:
        return "UMBRA"
    elif perp < pen_radius:
        return "PENUMBRA"
    return "SUNLIGHT"


def is_optically_visible(
    el_rad: float, r_sat_eci: np.ndarray, dt: datetime, min_elevation_deg: float = 10.0
) -> bool:
    if np.degrees(el_rad) < min_elevation_deg:
        return False
    return check_eclipse(r_sat_eci, sun_position_eci(dt)) != "UMBRA"
