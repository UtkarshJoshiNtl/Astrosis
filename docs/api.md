# API Reference

All public symbols are accessible via `import astrosis`.

## Constants (`astrosis.constants`)

| Symbol | Value | Unit |
|--------|-------|------|
| `MU` | 398600.4418 | km³/s² |
| `RE` | 6378.137 | km |
| `J2` | 1.08263e-3 | — |
| `J3` | -2.53266e-6 | — |
| `J4` | -1.61990e-6 | — |
| `OMEGA_EARTH` | 7.2921150e-5 | rad/s |
| `MU_SUN` | 132712440018.0 | km³/s² |
| `MU_MOON` | 4902.800066 | km³/s² |
| `CRITICAL_DISTANCE` | 0.1 | km |
| `WARNING_DISTANCE` | 1.0 | km |
| `ADVISORY_DISTANCE` | 5.0 | km |
| `P_SR` | 4.56e-6 | N/m² |
| `AU` | 149597870.7 | km |
| `RS_SUN` | 696340.0 | km |

## Propagation

### `astrosis.rk4_step(state, dt, mjd0=0, area=0, mass=1, cd=2.2, cr=1.5) -> tuple`

Fixed-step RK4 integration (one step). J2–J4 perturbations applied unconditionally.
Lunisolar/SRP gated by `mjd0 > 0`. Atmospheric drag gated by `area > 0` and
altitude < 1000 km.

- `state`: `(x, y, z, vx, vy, vz)` in km and km/s.
- `dt`: Step size in seconds.
- `mjd0`: Modified Julian Date (0 to skip lunisolar/SRP).

### `astrosis.rk4_batch(arr, dt, steps, ...) -> ndarray`

Batch RK4 over multiple states using vectorised NumPy. Same force model as
`rk4_step`. Input shape `(n, 6)`, output shape `(n, 6)`.

### `astrosis.propagate(state, dt_seconds, mjd0=0) -> list`

Single-step propagation with auto-backend (C++ → Python). Returns final
6-element ECI state.

### `astrosis.propagate_batch(states, dt_seconds, steps, ...) -> list`

Batch propagation with auto-backend (CUDA → C++ → NumPy → Python). Returns
list of final 6-element ECI state vectors.

### `astrosis.propagate_with_drag(state, dt_seconds, area=10, mass=1000, cd=2.2, cr=1.5, mjd0=0) -> list`

Single-step propagation including atmospheric drag, SRP, and lunisolar perturbations.

### `astrosis.backend_info() -> dict`

Returns `{active, cuda, cpp, numpy_batch, python, description}`.

## Conjunction Screening

### `astrosis.ConjunctionDetector`

Screens satellite–debris pairs for close approaches. Algorithm:

1. Broad-phase KDTree filter (or O(n²) fallback).
2. Pre-propagate all trajectories.
3. Coarse temporal sweep per candidate pair.
4. Brent refinement of TCA.
5. Chan collision probability for ADVISORY+ pairs.

#### `detector.detect(sat_states, debris_states, lookahead_s=86400, step_s=60, tle_age_days=1.0, mjd0=0) -> list[ConjunctionWarning]`

### `astrosis.detect_conjunctions(sat_states, debris_states, lookahead=86400, step_s=60, mjd0=0) -> list`

Auto-backend wrapper (CUDA → C++ → Python). Returns list of
`ConjunctionWarning` instances.

### `astrosis.ConjunctionWarning`

Dataclass fields: `sat_id`, `debris_id`, `current_distance`, `time_to_closest_approach`,
`severity`, `relative_velocity`, `pc_result`.

`Severity` enum: `NONE`, `ADVISORY`, `WARNING`, `CRITICAL`.

### `astrosis.monte_carlo_pc(sat_samples, deb_samples, dt, steps, threshold_km, mjd0=0) -> float`

Monte Carlo collision probability. Propagates N sample pairs and counts
passes within `threshold_km`. CUDA → Python fallback.

## Ephemeris

### `astrosis.sun_position_eci(dt) -> tuple`

Sun ECI position in km at given UTC datetime. Low-precision VSOP87
(accuracy ~0.01°).

### `astrosis.moon_position_eci(mjd) -> tuple`

Moon ECI position in km at given Modified Julian Date. Low-precision ELP-2000
(accuracy ~0.1°).

## Coordinate Frames

### `astrosis.gmst_from_datetime(dt) -> float`

Greenwich Mean Sidereal Time in radians for a given UTC datetime.

### `astrosis.eci_to_ecef(r_eci, dt) -> ndarray`

ECI → ECEF rotation at given datetime (includes equation of equinoxes).

### `astrosis.ecef_to_geodetic(r_ecef) -> (lat, lon, alt)`

ECEF cartesian → WGS-84 geodetic (Bowring iterative method).

### `astrosis.geodetic_to_ecef(lat, lon, alt) -> ndarray`

WGS-84 geodetic → ECEF cartesian.

### `astrosis.topocentric_aer(r_ecef, lat_rad, lon_rad, alt_km) -> (az, el, range)`

ECEF → topocentric azimuth/elevation/range for a ground station.

## Pass Prediction

### `astrosis.report_passes(norad_id, lat, lon, alt, start_dt, hours, dt_step=60, sat_area=10, sat_mass=1000, sat_cd=2.2, min_elevation_deg=10, ingestor=None) -> dict`

Predict satellite passes. Returns dict with `satellite`, `ground_station`,
`drag_params`, and `passes` (list of pass objects with start/end/max elevation).

Uses SGP4 for initial TLE→ECI conversion, then RK4 for propagation.

## Catalog / Location

### `astrosis.tle_ingestor`

Module-level `TLEIngestor` singleton.

### `astrosis.TLEIngestor(cache_dir)`

Fetches and caches TLE data. Fallback chain:
CelesTrak → Space-Track (if `SPACETRACK_USER`/`SPACETRACK_PASS` set) →
stale cache → bundled `astrosis/data/active.txt`.

#### `ingestor.fetch_tle_data(satellite_id=None, force_refresh=False) -> list[str]`
#### `ingestor.parse_tle_lines(lines) -> list[dict]`
#### `ingestor.get_satellites(satellite_id=None, force_refresh=False) -> list[dict]`

### `astrosis.geo.cities.CITIES`

Dict of ~85 city names → `(lat, lon)`.

### `astrosis.geo.cities.resolve_location(city_or_lat, lon=None) -> (lat, lon, name)`

Resolve a city name or explicit coordinates.

## Visibility

### `astrosis.check_eclipse(r_sat, r_sun) -> str`

Returns `"SUNLIGHT"`, `"UMBRA"`, or `"PENUMBRA"` for a satellite position.

### `astrosis.is_optically_visible(el_rad, r_sat_eci, dt, min_elevation_deg=10) -> bool`

True if above horizon and not in umbra.
