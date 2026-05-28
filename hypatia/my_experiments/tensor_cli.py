#!/usr/bin/env python3
"""Build tensors for any my_experiments experiment config."""

import argparse
import importlib.util
import sys
from pathlib import Path


MY_EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(MY_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(MY_EXPERIMENTS_DIR))

from shared import tensor_tools


def load_config(experiment_name):
    config_path = MY_EXPERIMENTS_DIR / "experiments" / experiment_name / "experiment_config.py"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing experiment config: {config_path}")

    spec = importlib.util.spec_from_file_location(f"{experiment_name}_config", config_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment", help="Experiment directory name under experiments/")
    parser.add_argument(
        "kind",
        choices=["traffic", "rtt", "sat-connectivity", "verify-sat-connectivity"],
    )
    parser.add_argument("--time-slice-s", type=int, default=5)
    parser.add_argument("--bin-ms", type=int, default=1000)
    parser.add_argument("--path", type=Path, default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config(args.experiment)

    if args.kind == "traffic":
        tensor_tools.build_traffic_tensor(config, time_slice_s=args.time_slice_s)
    elif args.kind == "rtt":
        tensor_tools.build_rtt_tensor(config, time_slice_s=args.time_slice_s)
    elif args.kind == "sat-connectivity":
        tensor_tools.build_sat_connectivity_tensor(config, bin_ms=args.bin_ms)
    elif args.kind == "verify-sat-connectivity":
        if args.path is None:
            raise ValueError("--path is required for verify-sat-connectivity")
        tensor_tools.verify_sat_connectivity_tensor(args.path)


if __name__ == "__main__":
    main()
