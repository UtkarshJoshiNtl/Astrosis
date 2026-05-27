from dataclasses import dataclass
from typing import List
import numpy as np

from .conjunction import ConjunctionWarning
from ..constants import MAX_DV, COOLDOWN_S
from ..core.fuel import FuelTracker

__all__ = ["ManeuverPlan", "ManeuverCalculator"]


@dataclass
class ManeuverPlan:
    evasion_dv_eci: List[float]
    recovery_dv_eci: List[float]
    fuel_cost_kg: float
    burn_timing_offset_s: float


class ManeuverCalculator:
    def calculate(
        self, sat_state: List[float], warning: ConjunctionWarning
    ) -> ManeuverPlan:
        """
        Compute an evasion-recovery maneuver pair for a conjunction.

        Evasion burn is perpendicular to the relative velocity (cross-track)
        to maximize miss distance per unit delta-V. Recovery burn reverses
        the evasion after the conjunction passes.

        Fuel cost sums evasion + recovery — total mass (dry + fuel) is used
        for the Tsiolkovsky calculation (recovery burn accounts for mass lost
        during evasion).

        Args:
            sat_state: Satellite ECI state [x, y, z, vx, vy, vz] at TCA.
            warning: ConjunctionWarning from detction scan.

        Returns:
            ManeuverPlan with delta-V vectors (ECI), fuel cost, and timing.
        """
        r = np.array(sat_state[:3])
        rv = np.array(warning.relative_velocity)
        rv_mag = np.linalg.norm(rv)

        if rv_mag < 1e-9:
            direction = r / np.linalg.norm(r)
        else:
            direction = np.cross(rv, r)
            d_mag = np.linalg.norm(direction)
            if d_mag < 1e-9:
                direction = r
            else:
                direction /= d_mag

        evasion_mag = min(
            MAX_DV, warning.current_distance / warning.time_to_closest_approach * 0.5
        )
        evasion_dv = list(direction * evasion_mag)
        recovery_dv = list(-direction * evasion_mag)

        tracker = FuelTracker()
        evasion_cost = tracker.calculate_fuel_cost(evasion_dv)
        remaining = max(0.0, tracker.fuel_kg - evasion_cost)
        tracker.fuel_kg = remaining
        recovery_cost = tracker.calculate_fuel_cost(recovery_dv)

        return ManeuverPlan(
            evasion_dv_eci=evasion_dv,
            recovery_dv_eci=recovery_dv,
            fuel_cost_kg=evasion_cost + recovery_cost,
            burn_timing_offset_s=max(
                0.0, warning.time_to_closest_approach - COOLDOWN_S
            ),
        )
