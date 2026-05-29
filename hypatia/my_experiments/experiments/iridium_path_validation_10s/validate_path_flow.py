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
    flows = []
    with open(config.run_dir() / "schedule.csv", "r", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row:
                continue
            flows.append({
                "flow_id": int(row[0]),
                "src_node": int(row[1]),
                "dst_node": int(row[2]),
                "size_bytes": int(row[3]),
                "start_time_ns": int(row[4]),
            })
    return flows


def _read_ground_station_names():
    names = {}
    path = config.GROUND_STATIONS_MANIFEST
    if not path.exists():
        return names
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            names[int(row["local_gs_id"])] = row["name"]
    return names


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


def _expected_paths(src_node, dst_node):
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
            src_node,
            dst_node,
            config.NUM_SATELLITES,
        )
        path = tuple(result["path"])
        paths_by_tuple[(result["status"], path)].append(fstate_time)
    return paths_by_tuple


def _describe_flow(flow, names):
    src_local = flow["src_node"] - config.GS_START_NODE_ID
    dst_local = flow["dst_node"] - config.GS_START_NODE_ID
    src_name = names.get(src_local, f"gs{src_local}")
    dst_name = names.get(dst_local, f"gs{dst_local}")
    return f"{src_local}:{src_name} -> {dst_local}:{dst_name}"


def _print_path_reference(title, paths_by_tuple):
    expected_union = set()
    print(f"\n=== {title} ===")
    for (status, path), times in sorted(paths_by_tuple.items(), key=lambda item: item[1][0]):
        pairs = _expanded_pairs(list(path)) if status == "ok" else []
        expected_union.update(pairs)
        time_desc = f"{times[0]}..{times[-1]}" if len(times) > 1 else str(times[0])
        print(f"fstate_times_ns={time_desc} status={status} path={list(path)}")
        print(f"  expanded_pairs={pairs}")
    return expected_union


def main():
    flows = _read_schedule()
    names = _read_ground_station_names()
    metadata = _read_metadata()
    total, per_slice_nonzero = _sum_observed_bytes()
    nonzero = np.argwhere(total > 0)

    print("=== Validation flows ===")
    print(f"flow_count={len(flows)}")
    print(f"total_scheduled_bytes={sum(flow['size_bytes'] for flow in flows)}")
    for flow in flows:
        print(
            f"flow_id={flow['flow_id']} "
            f"src_node={flow['src_node']} dst_node={flow['dst_node']} "
            f"size_bytes={flow['size_bytes']} "
            f"{_describe_flow(flow, names)}"
        )

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

    forward_expected_union = set()
    reverse_expected_union = set()
    for flow in flows:
        print(f"\n--- Flow {flow['flow_id']} {_describe_flow(flow, names)} ---")
        forward_paths = _expected_paths(flow["src_node"], flow["dst_node"])
        reverse_paths = _expected_paths(flow["dst_node"], flow["src_node"])
        forward_expected_union.update(
            _print_path_reference("Fstate forward data path expansion reference", forward_paths)
        )
        reverse_expected_union.update(
            _print_path_reference("Fstate reverse TCP ACK/control path expansion reference", reverse_paths)
        )

    observed_pairs = {(int(i), int(j)) for i, j in nonzero}
    all_expected_pairs = forward_expected_union | reverse_expected_union
    print("\n=== Pair coverage check ===")
    print(f"forward_expected_pairs={sorted(forward_expected_union)}")
    print(f"reverse_expected_pairs={sorted(reverse_expected_union)}")
    print(f"observed_pairs={sorted(observed_pairs)}")
    print(f"missing_forward_pairs={sorted(forward_expected_union - observed_pairs)}")
    print(f"missing_reverse_pairs={sorted(reverse_expected_union - observed_pairs)}")
    print(f"unexpected_observed_pairs={sorted(observed_pairs - all_expected_pairs)}")


if __name__ == "__main__":
    main()
