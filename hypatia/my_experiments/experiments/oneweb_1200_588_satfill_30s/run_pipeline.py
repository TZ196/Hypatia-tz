#!/usr/bin/env python3
"""Run the OneWeb-1200 588-satellite satfill experiment pipeline."""

import argparse
import sys

import experiment_config as config

if str(config.MY_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(config.MY_EXPERIMENTS_DIR))

from shared.constellation.main_oneweb_1200_588 import main_helper
from shared.experiment_pipeline import run_pipeline


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threads", type=int, default=4, help="Threads for dynamic-state generation")
    parser.add_argument("--build", action="store_true", help="Build ns-3 before running")
    return parser.parse_args()


def main():
    args = parse_args()
    run_pipeline(config, main_helper, threads=args.threads, build=args.build)


if __name__ == "__main__":
    main()
