"""
astrosis/constants.py — All physics and operational constants
=============================================================
Single source of truth for every numerical constant used across the engine.
"""

# ── Orbital Mechanics ────────────────────────────────────────────────────────
MU: float = 398600.4418  # Earth gravitational parameter  [km³/s²]
RE: float = 6378.137  # Earth equatorial radius         [km]
J2: float = 1.08263e-3  # Earth oblateness J2 (EGM96)   [dimensionless]
J3: float = -2.53266e-6  # Earth pear-shape J3 (EGM96)   [dimensionless]
J4: float = -1.61990e-6  # J4 (EGM96)                    [dimensionless]
OMEGA_EARTH: float = 7.2921150e-5  # Earth rotation rate         [rad/s]
MU_SUN: float = 132712440018.0  # Sun gravitational parameter    [km³/s²]
MU_MOON: float = 4902.800066  # Moon gravitational parameter   [km³/s²]


# ── WGS-84 Ellipsoid ─────────────────────────────────────────────────────────
F_WGS84: float = 1.0 / 298.257223563
E2_WGS84: float = 2 * F_WGS84 - F_WGS84**2

# ── Conjunction Thresholds ───────────────────────────────────────────────────
CRITICAL_DISTANCE: float = 0.1  # CRITICAL warning threshold  [km]
WARNING_DISTANCE: float = 1.0  # WARNING threshold            [km]
ADVISORY_DISTANCE: float = 5.0  # ADVISORY threshold           [km]

# ── Sun / Visibility / SRP ───────────────────────────────────────────────────
RS_SUN: float = 696340.0  # Solar radius                     [km]
AU: float = 149597870.7  # Astronomical unit                [km]
P_SR: float = 4.56e-6  # Solar radiation pressure @ 1 AU  [N/m²]
