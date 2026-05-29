#!/usr/bin/env python3
"""Inspect whether satellite path-flow matrices contain expanded path pairs."""

import csv
import sys
from collections import defaultdict

import numpy as np

import experiment_config as config

if str(config.MY_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(config.MY_EXPERIMENTS_DIR))

from shared import tensor_tools


def _read_schedule():
    with open(config.run_dir() / "schedule.csv", "r", encoding="utf-8") as f:
        row = next(csv.reader(f))
    return {
        "flow_id": int(row[0]),
        "src_node": int(row[1]),
        "dst_node": int(row[2]),
        "size_bytes": int(row[3]),
        "start_time_ns": int(row[4]),
    }


def _read_metadata():
    path = config.run_dir() / "logs_ns3" / "sat_path_flow" / "metadata.txt"
    if not path.exists():
        return {}
    metadata = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line:
                key, value = line.split("=", 1)
                metadata[key] = value
    return metadata


def _sum_observed_bytes():
    bytes_dir = config.run_dir() / "logs_ns3" / "sat_path_flow" / "bytes"
    files = sorted(bytes_dir.glob("t_*.csv"))
    if not files:
        raise FileNotFoundError(f"No satellite path byte matrices found in {bytes_dir}")

    total = np.zeros((config.NUM_SATELLITES, config.NUM_SATELLITES), dtype=np.uint64)
    per_slice_nonzero = []
    for path in files:
        matrix = np.loadtxt(path, delimiter=",", dtype=np.uint64)
        total += matrix
        per_slice_nonzero.append((path.name, int(np.count_nonzero(matrix)), int(matrix.sum())))
    return total, per_slice_nonzero


def _expanded_pairs(path):
    if len(path) == 1:
        sat = path[0]
        return [(sat, sat)]

    pairs = []
    for to_pos in range(1, len(path)):
        for from_pos in range(to_pos):
            pairs.append((path[from_pos], path[to_pos]))
    return pairs


def _expected_paths(schedule):
    dynamic_state_dir = config.generated_satellite_network_dir() / config.dynamic_state_dir_name()
    available = tensor_tools._available_fstate_times(dynamic_state_dir)
    if not available:
        raise FileNotFoundError(f"No fstate files found in {dynamic_state_dir}")

    cache = {}
    paths_by_tuple = defaultdict(list)
    for fstate_time in available:
        fstate = tensor_tools._read_cumulative_fstate(dynamic_state_dir, available, fstate_time, cache)
        result = tensor_tools._satellite_path_for_flow(
            fstate,
            schedule["src_node"],
            schedule["dst_node"],
            config.NUM_SATELLITES,
        )
        path = tuple(result["path"])
        paths_by_tuple[(result["status"], path)].append(fstate_time)
    return paths_by_tuple


def main():
    schedule = _read_schedule()
    metadata = _read_metadata()
    total, per_slice_nonzero = _sum_observed_bytes()
    nonzero = np.argwhere(total > 0)

    print("=== Validation flow ===")
    print(
        f"flow_id={schedule['flow_id']} "
        f"src_node={schedule['src_node']} dst_node={schedule['dst_node']} "
        f"size_bytes={schedule['size_bytes']}"
    )
    print("ground_stations=0:New-York-Newark -> 1:Sydney")

    print("\n=== Monitor metadata ===")
    for key in [
        "tracking_point",
        "semantics",
        "satellite_receive_events",
        "single_satellite_path_observations",
        "transit_pair_observations",
        "non_adjacent_pair_observations",
        "open_packet_paths_at_finish",
        "path_length_histogram",
    ]:
        if key in metadata:
            print(f"{key}={metadata[key]}")

    print("\n=== Observed matrix summary ===")
    print(f"nonzero_cells={len(nonzero)}")
    print(f"total_observed_matrix_bytes={int(total.sum())}")
    print("per_slice_nonzero_cells_and_bytes:")
    for name, count, byte_sum in per_slice_nonzero:
        if count > 0 or byte_sum > 0:
            print(f"  {name}: nonzero={count}, bytes={byte_sum}")

    print("\nObserved nonzero satellite pairs, summed over all slices:")
    for from_sat, to_sat in nonzero:
        print(f"  {from_sat}->{to_sat}: {int(total[from_sat, to_sat])}")

    print("\n=== Fstate path expansion reference ===")
    paths_by_tuple = _expected_paths(schedule)
    expected_union = set()
    for (status, path), times in sorted(paths_by_tuple.items(), key=lambda item: item[1][0]):
        pairs = _expanded_pairs(list(path)) if status == "ok" else []
        expected_union.update(pairs)
        time_desc = f"{times[0]}..{times[-1]}" if len(times) > 1 else str(times[0])
        print(f"fstate_times_ns={time_desc} status={status} path={list(path)}")
        print(f"  expanded_pairs={pairs}")

    observed_pairs = {(int(i), int(j)) for i, j in nonzero}
    print("\n=== Pair coverage check ===")
    print(f"expected_union_pairs={sorted(expected_union)}")
    print(f"observed_pairs={sorted(observed_pairs)}")
    print(f"missing_expected_pairs={sorted(expected_union - observed_pairs)}")
    print(f"extra_observed_pairs={sorted(observed_pairs - expected_union)}")


if __name__ == "__main__":
    main()
