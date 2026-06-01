#!/usr/bin/env python3
"""Build satellite path tensors from sat_path_flow CSV matrices."""

import sys

import experiment_config as config

if str(config.MY_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(config.MY_EXPERIMENTS_DIR))

from shared.tensor_tools import build_sat_path_tensors


def main():
    outputs = build_sat_path_tensors(config)
    print("Generated tensors:")
    for path in outputs:
        print(f"  {path}")


if __name__ == "__main__":
    main()
