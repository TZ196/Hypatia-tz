#!/usr/bin/env python3
"""Run the full diagnostic experiment and print cross-plane checks."""

import argparse
import sys

import experiment_config as config

if str(config.MY_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(config.MY_EXPERIMENTS_DIR))

from shared.constellation.main_iridium_780 import main_helper
from shared.experiment_pipeline import run_pipeline

import diagnose_cross_plane
import sweep_isl_shift


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--build", action="store_true", help="Build ns-3 before running")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    best_shift = sweep_isl_shift.main()
    if getattr(config, "AUTO_SELECT_ISL_SHIFT", False):
        config.ISL_SHIFT = best_shift
        config.IRIDIUM_ISL_SHIFT = best_shift
        print(f"\nUsing auto-selected ISL_SHIFT={best_shift} for this run")
    run_pipeline(config, main_helper, threads=args.threads, build=args.build)
    diagnose_cross_plane.main()
