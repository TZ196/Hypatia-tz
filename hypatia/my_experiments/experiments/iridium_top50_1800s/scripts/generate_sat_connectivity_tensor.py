#!/usr/bin/env python3
"""
Generate a dynamic satellite ISL connectivity tensor for 1800s with 1s resolution.

Output: runs/data/sat_connectivity_tensor_dynamic_1800s_1s.npz
Keys:
 - sat_connectivity: uint8 array (N, N, T), 1 if connected else 0
 - sat_ids: int array of satellite ids [0..N-1]
 - time_ms: int array of time bin start in ms

Connectivity is computed by checking ISL distance per time step against max_isl_length_m.
"""
import os
import sys
from pathlib import Path
import numpy as np
from astropy import units as u


SCRIPT_DIR = Path(__file__).resolve().parent
EXPERIMENT_DIR = SCRIPT_DIR.parent
HYPATIA_DIR = EXPERIMENT_DIR.parent.parent.parent
SATGENPY_DIR = HYPATIA_DIR / "satgenpy"

if str(SATGENPY_DIR) not in sys.path:
    sys.path.insert(0, str(SATGENPY_DIR))

from satgen.tles import read_tles
from satgen.distance_tools import distance_m_between_satellites


GEN_DIR = EXPERIMENT_DIR / "gen_data" / "iridium_780_isls_plus_grid_ground_stations_top_50_algorithm_free_one_only_over_isls"
ISLS_PATH = GEN_DIR / "isls.txt"
TLES_PATH = GEN_DIR / "tles.txt"
DESC_PATH = GEN_DIR / "description.txt"
OUT_PATH = EXPERIMENT_DIR / "runs" / "data" / "sat_connectivity_tensor_dynamic_1800s_1s.npz"

DURATION_S = 1800
BIN_MS = 1000


def read_isls(isls_path: str):
    edges = []
    with open(isls_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            a, b = line.split()
            edges.append((int(a), int(b)))
    return edges


def read_description(desc_path: str):
    max_isl = None
    with open(desc_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key == "max_isl_length_m":
                max_isl = float(value)
    if max_isl is None:
        raise ValueError("max_isl_length_m not found in description.txt")
    return max_isl


def main():
    if not os.path.exists(ISLS_PATH):
        raise FileNotFoundError(f"Missing {ISLS_PATH}")
    if not os.path.exists(TLES_PATH):
        raise FileNotFoundError(f"Missing {TLES_PATH}")
    if not os.path.exists(DESC_PATH):
        raise FileNotFoundError(f"Missing {DESC_PATH}")

    tle_info = read_tles(TLES_PATH)
    satellites = tle_info["satellites"]
    epoch = tle_info["epoch"]
    sat_count = len(satellites)
    edges = read_isls(ISLS_PATH)
    max_isl_length_m = read_description(DESC_PATH)

    t_bins = DURATION_S * 1000 // BIN_MS
    time_ms = np.arange(0, t_bins * BIN_MS, BIN_MS, dtype=np.int64)
    sat_connectivity = np.zeros((sat_count, sat_count, t_bins), dtype=np.uint8)

    for t_idx in range(t_bins):
        time_since_epoch_ns = int(t_idx * BIN_MS * 1_000_000)
        time = epoch + time_since_epoch_ns * u.ns
        for a, b in edges:
            if a >= sat_count or b >= sat_count:
                continue
            dist_m = distance_m_between_satellites(
                satellites[a],
                satellites[b],
                str(epoch),
                str(time)
            )
            if dist_m <= max_isl_length_m:
                sat_connectivity[a, b, t_idx] = 1
                sat_connectivity[b, a, t_idx] = 1

    sat_ids = np.arange(sat_count, dtype=np.int32)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    np.savez_compressed(
        str(OUT_PATH),
        sat_connectivity=sat_connectivity,
        sat_ids=sat_ids,
        time_ms=time_ms,
    )
    print(f"Saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
