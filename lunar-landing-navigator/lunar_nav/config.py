"""Mission constraints, scoring weights and physical constants.

Everything that a mission planner might want to tune lives here, so the
rest of the pipeline stays free of magic numbers.
"""
from dataclasses import dataclass, field

# --- Physical constants -----------------------------------------------------
MOON_RADIUS_M = 1_737_400.0
SYNODIC_MONTH_D = 29.530589      # sun goes once around the polar sky
DRACONIC_YEAR_D = 346.62         # period of the sun's +/-1.54 deg "seasons"
ANOMALISTIC_MONTH_D = 27.554550  # period of Earth's longitude libration
DRACONIC_MONTH_D = 27.212221     # period of Earth's latitude libration

SUN_MAX_DECLINATION_DEG = 1.54   # lunar axial tilt relative to the ecliptic
SUN_ANGULAR_DIAMETER_DEG = 0.53
EARTH_LAT_LIBRATION_DEG = 6.7
EARTH_LON_LIBRATION_DEG = 7.9
EARTH_ANGULAR_DIAMETER_DEG = 1.9


@dataclass
class MissionConstraints:
    """Hard and soft requirements for a landing site (Artemis-like)."""

    max_slope_deg: float = 10.0          # above this -> red / unsafe
    preferred_slope_deg: float = 8.0     # above this -> at best yellow
    mission_duration_d: float = 6.5      # surface stay
    min_illumination: float = 0.30       # mission-mean sunlit fraction
    min_earth_visibility: float = 0.30   # mission-mean Earth-in-view fraction
    psr_ideal_distance_m: float = 2_000  # walking distance to a cold trap
    psr_max_distance_m: float = 15_000   # beyond this -> no science bonus
    psr_illum_threshold: float = 0.005   # annual mean below this -> PSR
    max_rock_abundance: float = 0.6      # normalised hazard (0..1) cut-off
    region_size_m: float = 15_000        # NASA candidate regions ~15x15 km
    landing_ellipse_radius_m: float = 300
    n_final_regions: int = 9             # NASA went 13 -> 9
    edge_margin_m: float = 3_000         # horizon beyond raster edge is unknown


@dataclass
class ScoringWeights:
    slope: float = 0.30
    illumination: float = 0.25
    earth_visibility: float = 0.15
    psr_proximity: float = 0.15
    hazard: float = 0.15

    def normalised(self) -> dict:
        d = {k: float(v) for k, v in self.__dict__.items()}
        total = sum(d.values())
        return {k: v / total for k, v in d.items()}


@dataclass
class Config:
    constraints: MissionConstraints = field(default_factory=MissionConstraints)
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    n_azimuths: int = 32                 # horizon resolution
    horizon_max_distance_m: float = 40_000
    mission_start_day: float | None = None  # None -> southern-summer peak
    annual_samples: int = 700
    mission_step_h: float = 3.0
