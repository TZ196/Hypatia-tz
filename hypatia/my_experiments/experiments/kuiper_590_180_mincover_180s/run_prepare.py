#!/usr/bin/env python3
"""Generate local inputs for the Kuiper-like 180s min-cover experiment."""

import argparse
import sys

import experiment_config as config

if str(config.MY_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(config.MY_EXPERIMENTS_DIR))

from shared.constellation.main_kuiper_590_180 import main_helper
from shared.experiment_pipeline import (
    define_ground_stations,
    design_traffic,
    generate_ns3_run,
    generate_satellite_network_state,
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument(
        "--with-run-dir",
        action="store_true",
        help="Also generate runs/main with ns-3 inputs but do not run ns-3",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    define_ground_stations(config)
    generate_satellite_network_state(config, main_helper, args.threads)
    design_traffic(config)
    if args.with_run_dir:
        generate_ns3_run(config)


if __name__ == "__main__":
    main()
