"""OneWeb Phase 1 / Eutelsat OneWeb near-polar shell.

Parameters supplied for the OneWeb Phase 1 constellation:
12 orbital planes x 49 satellites per plane = 588 satellites, 1200 km
altitude, 87.9 degree inclination, and 13.18 rev/day mean motion.
"""

import math
import sys
from pathlib import Path

try:
    from .main_helper import MainHelper
except ImportError:
    from main_helper import MainHelper


EARTH_RADIUS = 6378135.0

BASE_NAME = "oneweb_1200_588"
NICE_NAME = "OneWeb-1200-588"
DEFAULT_GENERATED_DATA_DIR = Path(__file__).resolve().parents[2] / "experiments" / BASE_NAME / "gen_data"

ECCENTRICITY = 0.0000001
ARG_OF_PERIGEE_DEGREE = 0.0
PHASE_DIFF = True

MEAN_MOTION_REV_PER_DAY = 13.18
ALTITUDE_M = 1200000

# Broad enough for satellite-shadow anchored stations over a 30 s diagnostic run.
SATELLITE_CONE_RADIUS_M = 1500000
MAX_GSL_LENGTH_M = math.sqrt(math.pow(SATELLITE_CONE_RADIUS_M, 2) + math.pow(ALTITUDE_M, 2))

MAX_ISL_LENGTH_M = 2 * math.sqrt(
    math.pow(EARTH_RADIUS + ALTITUDE_M, 2) - math.pow(EARTH_RADIUS + 80000, 2)
)

NUM_ORBS = 12
NUM_SATS_PER_ORB = 49
INCLINATION_DEGREE = 87.9

main_helper = MainHelper(
    BASE_NAME,
    NICE_NAME,
    ECCENTRICITY,
    ARG_OF_PERIGEE_DEGREE,
    PHASE_DIFF,
    MEAN_MOTION_REV_PER_DAY,
    ALTITUDE_M,
    MAX_GSL_LENGTH_M,
    MAX_ISL_LENGTH_M,
    NUM_ORBS,
    NUM_SATS_PER_ORB,
    INCLINATION_DEGREE,
)


def main():
    args = sys.argv[1:]
    if len(args) != 6:
        print("Usage: python main_oneweb_1200_588.py [duration_s] [time_step_ms] "
              "[isls_plus_grid / isls_none] [ground_stations] "
              "[routing_algorithm] [threads]")
        exit(1)

    main_helper.calculate(
        str(DEFAULT_GENERATED_DATA_DIR),
        int(args[0]),
        int(args[1]),
        args[2],
        args[3],
        args[4],
        int(args[5]),
    )


if __name__ == "__main__":
    main()
