import math

from ..constants import AU

__all__ = ["sun_position_eci", "moon_position_eci"]


def sun_position_eci(mjd: float) -> tuple:
    """
    Low-precision solar position in ECI.

    Accuracy ~0.01° (adequate for lunisolar perturbations and eclipse checks).
    Based on Montenbruck & Gill (2000) analytical model.

    Args:
        mjd: Modified Julian Date.

    Returns:
        Tuple (x, y, z) in km.
    """
    d = mjd - 51544.5
    g = 357.529 + 0.98560028 * d
    g_rad = math.radians(g)
    q = 280.459 + 0.98564736 * d
    L = q + 1.915 * math.sin(g_rad) + 0.020 * math.sin(2 * g_rad)
    R_au = 1.00014 - 0.01671 * math.cos(g_rad) - 0.00014 * math.cos(2 * g_rad)
    R_km = R_au * AU
    e = math.radians(23.439 - 0.00000036 * d)
    L_rad = math.radians(L)
    return (
        R_km * math.cos(L_rad),
        R_km * math.cos(e) * math.sin(L_rad),
        R_km * math.sin(e) * math.sin(L_rad),
    )


def moon_position_eci(mjd: float) -> tuple:
    """
    Low-precision lunar position in ECI.

    Accuracy ~0.1° (adequate for lunisolar perturbations).
    Based on Montenbruck & Gill (2000) analytical model.

    Args:
        mjd: Modified Julian Date.

    Returns:
        Tuple (x, y, z) in km.
    """
    d = mjd - 51544.5
    L = 218.316 + 13.176396 * d
    M = 134.963 + 13.064993 * d
    F = 93.272 + 13.229350 * d
    L_rad, M_rad, F_rad = math.radians(L), math.radians(M), math.radians(F)
    l_ecl = L_rad + math.radians(6.289 * math.sin(M_rad))
    b_ecl = math.radians(5.128 * math.sin(F_rad))
    dist = 385001.0 - 20905.0 * math.cos(M_rad)
    e = math.radians(23.439 - 0.00000036 * d)
    x_ecl = dist * math.cos(b_ecl) * math.cos(l_ecl)
    y_ecl = dist * math.cos(b_ecl) * math.sin(l_ecl)
    z_ecl = dist * math.sin(b_ecl)
    return (
        x_ecl,
        y_ecl * math.cos(e) - z_ecl * math.sin(e),
        y_ecl * math.sin(e) + z_ecl * math.cos(e),
    )
