# orbital mechanics params
MU: float = 398600.4418       # Earth GP [km3/s2]
RE: float = 6378.137           # Earth radius [km]
J2: float = 1.08263e-3
J3: float = -2.53266e-6
J4: float = -1.61990e-6
OMEGA_EARTH: float = 7.2921150e-5  # rad/s
MU_SUN: float = 132712440018.0     # [km3/s2]
MU_MOON: float = 4902.800066       # [km3/s2]

# WGS-84
F_WGS84: float = 1.0 / 298.257223563
E2_WGS84: float = 2 * F_WGS84 - F_WGS84**2

# conjunction thresholds [km]
CRITICAL_DISTANCE: float = 0.1
WARNING_DISTANCE: float = 1.0
ADVISORY_DISTANCE: float = 5.0

# sun / SRP
RS_SUN: float = 696340.0       # [km]
AU: float = 149597870.7        # [km]
P_SR: float = 4.56e-6           # N/m2 at 1 AU
