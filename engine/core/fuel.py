import math
from ..constants import ISP, G0_KM, DRY_MASS, INITIAL_FUEL

__all__ = ["FuelTracker"]


class FuelTracker:
    """Tracks propellant usage for impulsive maneuvers.

    Uses the Tsiolkovsky rocket equation to compute fuel consumption.
    Raises ValueError on insufficient fuel (mirrors C++ std::runtime_error).

    Args:
        initial_fuel: Initial fuel mass in kg.
        dry_mass: Dry (empty) spacecraft mass in kg.
    """

    def __init__(self, initial_fuel: float = INITIAL_FUEL, dry_mass: float = DRY_MASS):
        self.fuel_kg = initial_fuel
        self.initial_fuel_kg = initial_fuel
        self.dry_mass = dry_mass

    def current_mass(self) -> float:
        """Total spacecraft mass (dry + remaining fuel) in kg."""
        return self.dry_mass + self.fuel_kg

    def fuel_percentage(self) -> float:
        """Percentage of initial fuel remaining (0-100)."""
        return (
            (self.fuel_kg / self.initial_fuel_kg) * 100.0
            if self.initial_fuel_kg > 0
            else 0.0
        )

    def is_critical(self) -> bool:
        """True if fuel below 10% threshold."""
        return self.fuel_percentage() < 10.0

    def is_empty(self) -> bool:
        """True if no fuel remaining."""
        return self.fuel_kg <= 0.0

    def calculate_fuel_cost(self, delta_v: list) -> float:
        """
        Compute fuel mass required for a given delta-V impulse.

        Uses Tsiolkovsky: m_fuel = m0 * (1 - exp(-|dV| / (Isp * g0)))

        Args:
            delta_v: Impulse vector [dVx, dVy, dVz] in km/s.

        Returns:
            Fuel mass consumed in kg.
        """
        dv_mag = math.sqrt(sum(d * d for d in delta_v))
        if dv_mag < 1e-15:
            return 0.0
        m0 = self.current_mass()
        fuel_used = m0 * (1.0 - math.exp(-dv_mag / (ISP * G0_KM)))
        return fuel_used

    def apply_burn(self, delta_v: list) -> None:
        """
        Deduct fuel for a delta-V burn.

        Args:
            delta_v: Impulse vector [dVx, dVy, dVz] in km/s.

        Raises:
            ValueError: If fuel is insufficient for the burn.
        """
        cost = self.calculate_fuel_cost(delta_v)
        if cost > self.fuel_kg:
            raise ValueError(
                f"Insufficient fuel: burn requires {cost:.3f} kg but only "
                f"{self.fuel_kg:.3f} kg remaining"
            )
        self.fuel_kg -= cost
