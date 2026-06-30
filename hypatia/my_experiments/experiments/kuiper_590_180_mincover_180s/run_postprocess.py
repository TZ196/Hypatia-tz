#!/usr/bin/env python3
"""Build tensor outputs from a completed ns-3 run."""

import sys

import experiment_config as config

if str(config.MY_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(config.MY_EXPERIMENTS_DIR))

from shared.experiment_pipeline import postprocess_tensors


if __name__ == "__main__":
    postprocess_tensors(config)
