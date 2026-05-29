"""Reduced Starlink 550 km shell for medium-size experiments.

This keeps Starlink-like altitude/inclination while reducing the shell to
18 orbital planes x 18 satellites per plane = 324 satellites.
"""

import math
import sys
from pathlib import Path

try:
    from .main_helper import MainHelper
except ImportError:
    from main_helper import MainHelper


EARTH_RADIUS = 6378135.0

BASE_NAME = "starlink_550_324"
NICE_NAME = "Starlink-550-324"
DEFAULT_GENERATED_DATA_DIR = Path(__file__).resolve().parents[2] / "experiments" / BASE_NAME / "gen_data"

ECCENTRICITY = 0.0000001
ARG_OF_PERIGEE_DEGREE = 0.0
PHASE_DIFF = True

MEAN_MOTION_REV_PER_DAY = 15.19
ALTITUDE_M = 550000

SATELLITE_CONE_RADIUS_M = 940700
MAX_GSL_LENGTH_M = math.sqrt(math.pow(SATELLITE_CONE_RADIUS_M, 2) + math.pow(ALTITUDE_M, 2))

MAX_ISL_LENGTH_M = 2 * math.sqrt(
    math.pow(EARTH_RADIUS + ALTITUDE_M, 2) - math.pow(EARTH_RADIUS + 80000, 2)
)

NUM_ORBS = 18
NUM_SATS_PER_ORB = 18
INCLINATION_DEGREE = 53.0

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
        print("Usage: python main_starlink_550_324.py [duration_s] [time_step_ms] "
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
