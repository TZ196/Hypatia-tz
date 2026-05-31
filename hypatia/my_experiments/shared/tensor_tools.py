"""Reusable tensor builders for experiment outputs."""

import sys
from pathlib import Path

import numpy as np


NS_PER_S = 1_000_000_000


def _logs_dir(config) -> Path:
    return config.run_dir() / "logs_ns3"


def _data_dir(config) -> Path:
    return config.run_dir() / "data"


def _ensure_satgenpy_on_path(config):
    satgenpy_dir = config.HYPATIA_DIR / "satgenpy"
    if not satgenpy_dir.exists():
        raise FileNotFoundError(f"satgenpy directory not found: {satgenpy_dir}")
    if str(satgenpy_dir) not in sys.path:
        sys.path.insert(0, str(satgenpy_dir))


def _read_flow_map(config):
    flow_map = {}
    path = _logs_dir(config) / "tcp_flows.txt"
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        flow_id = int(parts[0])
        src = int(parts[1])
        dst = int(parts[2])
        src_idx = src - config.GS_START_NODE_ID
        dst_idx = dst - config.GS_START_NODE_ID
        if 0 <= src_idx < config.NUM_GROUND_STATIONS and 0 <= dst_idx < config.NUM_GROUND_STATIONS:
            flow_map[flow_id] = (src_idx, dst_idx)
    return flow_map


def _num_slices(config, time_slice_s):
    if time_slice_s <= 0:
        raise ValueError("time_slice_s must be a positive integer")
    num_slices = config.DURATION_S // time_slice_s
    if num_slices * time_slice_s != config.DURATION_S:
        raise ValueError(
            f"DURATION_S ({config.DURATION_S}s) must be divisible by time_slice_s ({time_slice_s}s)"
        )
    return num_slices


def build_traffic_tensor(config, time_slice_s=5, output_name="traffic_tensor.npy"):
    """Build a ground-station traffic tensor from tcp_flow_*_progress.csv."""

    num_slices = _num_slices(config, time_slice_s)
    flow_map = _read_flow_map(config)
    tensor = np.zeros(
        (config.NUM_GROUND_STATIONS, config.NUM_GROUND_STATIONS, num_slices),
        dtype=np.float64,
    )

    processed = 0
    skipped = 0
    for flow_id in sorted(flow_map):
        path = _logs_dir(config) / f"tcp_flow_{flow_id}_progress.csv"
        if not path.exists():
            skipped += 1
            continue

        src_idx, dst_idx = flow_map[flow_id]
        prev_time = None
        prev_bytes = None

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                time_ns = int(parts[1])
                bytes_cum = int(parts[2])

                if prev_time is not None:
                    delta = bytes_cum - prev_bytes
                    if delta > 0:
                        slice_idx = prev_time // (NS_PER_S * time_slice_s)
                        if 0 <= slice_idx < num_slices:
                            tensor[src_idx, dst_idx, slice_idx] += delta

                prev_time = time_ns
                prev_bytes = bytes_cum

        processed += 1

    out_dir = _data_dir(config)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_name
    np.save(out_path, tensor)
    print(f"Saved traffic tensor {tensor.shape} to {out_path}")
    print(f"Processed {processed} flows, skipped {skipped}")
    return out_path


def build_rtt_tensor(config, time_slice_s=5, output_name="rtt_tensor.npy"):
    """Build a weighted-average RTT tensor from tcp_flow_*_rtt.csv."""

    num_slices = _num_slices(config, time_slice_s)
    slice_ns = NS_PER_S * time_slice_s
    flow_map = _read_flow_map(config)

    rtt_weighted = np.zeros(
        (config.NUM_GROUND_STATIONS, config.NUM_GROUND_STATIONS, num_slices),
        dtype=np.float64,
    )
    rtt_weight = np.zeros_like(rtt_weighted)

    processed = 0
    skipped = 0
    for flow_id in sorted(flow_map):
        path = _logs_dir(config) / f"tcp_flow_{flow_id}_rtt.csv"
        if not path.exists():
            skipped += 1
            continue

        src_idx, dst_idx = flow_map[flow_id]
        prev_time = None
        prev_rtt = None

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                time_ns = int(parts[1])
                rtt = int(parts[2])

                if prev_time is not None:
                    _add_weighted_interval(
                        rtt_weighted,
                        rtt_weight,
                        src_idx,
                        dst_idx,
                        prev_time,
                        time_ns,
                        prev_rtt,
                        slice_ns,
                        num_slices,
                    )

                prev_time = time_ns
                prev_rtt = rtt

        processed += 1

    mask = rtt_weight > 0
    tensor = np.zeros_like(rtt_weighted)
    tensor[mask] = rtt_weighted[mask] / rtt_weight[mask]

    out_dir = _data_dir(config)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_name
    np.save(out_path, tensor)
    print(f"Saved RTT tensor {tensor.shape} to {out_path}")
    print(f"Processed {processed} flows, skipped {skipped}")
    return out_path


def _add_weighted_interval(target, weight, src_idx, dst_idx, start_ns, end_ns, value, slice_ns, num_slices):
    if end_ns <= start_ns or value <= 0:
        return

    slice_start = start_ns // slice_ns
    slice_end = end_ns // slice_ns

    if slice_start == slice_end:
        duration = end_ns - start_ns
        if 0 <= slice_start < num_slices:
            target[src_idx, dst_idx, slice_start] += value * duration
            weight[src_idx, dst_idx, slice_start] += duration
        return

    end_of_first_slice = (slice_start + 1) * slice_ns
    duration = end_of_first_slice - start_ns
    if 0 <= slice_start < num_slices:
        target[src_idx, dst_idx, slice_start] += value * duration
        weight[src_idx, dst_idx, slice_start] += duration

    for slice_idx in range(slice_start + 1, slice_end):
        if 0 <= slice_idx < num_slices:
            target[src_idx, dst_idx, slice_idx] += value * slice_ns
            weight[src_idx, dst_idx, slice_idx] += slice_ns

    start_of_last_slice = slice_end * slice_ns
    duration = end_ns - start_of_last_slice
    if duration > 0 and 0 <= slice_end < num_slices:
        target[src_idx, dst_idx, slice_end] += value * duration
        weight[src_idx, dst_idx, slice_end] += duration


def build_sat_connectivity_tensor(config, bin_ms=1000, output_name=None):
    """Build a satellite ISL connectivity tensor from generated satgenpy data."""

    _ensure_satgenpy_on_path(config)

    from astropy import units as u
    from satgen.distance_tools import distance_m_between_satellites
    from satgen.tles import read_tles

    gen_dir = config.generated_satellite_network_dir()
    isls_path = gen_dir / "isls.txt"
    tles_path = gen_dir / "tles.txt"
    desc_path = gen_dir / "description.txt"

    if output_name is None:
        output_name = f"sat_connectivity_tensor_dynamic_{config.DURATION_S}s_{bin_ms}ms.npz"

    tle_info = read_tles(tles_path)
    satellites = tle_info["satellites"]
    epoch = tle_info["epoch"]
    edges = _read_isls(isls_path)
    max_isl_length_m = _read_max_isl_length(desc_path)

    t_bins = config.DURATION_S * 1000 // bin_ms
    time_ms = np.arange(0, t_bins * bin_ms, bin_ms, dtype=np.int64)
    sat_connectivity = np.zeros((len(satellites), len(satellites), t_bins), dtype=np.uint8)

    for t_idx in range(t_bins):
        time_since_epoch_ns = int(t_idx * bin_ms * 1_000_000)
        time = epoch + time_since_epoch_ns * u.ns
        for a, b in edges:
            if a >= len(satellites) or b >= len(satellites):
                continue
            dist_m = distance_m_between_satellites(satellites[a], satellites[b], str(epoch), str(time))
            if dist_m <= max_isl_length_m:
                sat_connectivity[a, b, t_idx] = 1
                sat_connectivity[b, a, t_idx] = 1

    out_dir = _data_dir(config)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_name
    np.savez_compressed(
        out_path,
        sat_connectivity=sat_connectivity,
        sat_ids=np.arange(len(satellites), dtype=np.int32),
        time_ms=time_ms,
    )
    print(f"Saved satellite connectivity tensor {sat_connectivity.shape} to {out_path}")
    return out_path


def build_sat_path_tensors(config):
    """Build path-level satellite tensors from per-time-step matrix CSV files."""

    base_dir = _logs_dir(config) / "sat_path_flow"
    if not base_dir.exists():
        raise FileNotFoundError(f"Satellite path flow directory not found: {base_dir}")

    metadata = _read_key_value_file(base_dir / "metadata.txt")
    expected_bins = int(metadata["num_time_bins"]) if "num_time_bins" in metadata else None

    metric_specs = [
        ("bytes", "sat_path_bytes_tensor.npy"),
        ("packets", "sat_path_packets_tensor.npy"),
        ("drop_bytes", "sat_path_drop_bytes_tensor.npy"),
        ("drop_packets", "sat_path_drop_packets_tensor.npy"),
        ("one_way_delay_ns", "sat_path_one_way_delay_ns_tensor.npy"),
        ("one_way_delay_weight_bytes", "sat_path_one_way_delay_weight_bytes_tensor.npy"),
        ("rtt_ns", "sat_path_rtt_ns_tensor.npy"),
    ]

    out_dir = _data_dir(config)
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs = []
    for metric, output_name in metric_specs:
        metric_dir = base_dir / metric
        files = sorted(metric_dir.glob("t_*.csv"), key=_time_matrix_index)
        if not files:
            raise FileNotFoundError(f"No matrix CSV files found in {metric_dir}")
        if expected_bins is not None and len(files) != expected_bins:
            raise ValueError(
                f"Expected {expected_bins} {metric} CSV files in {metric_dir}, got {len(files)}"
            )

        matrices = []
        for path in files:
            matrix = np.loadtxt(path, delimiter=",", dtype=np.uint64)
            if matrix.shape != (config.NUM_SATELLITES, config.NUM_SATELLITES):
                raise ValueError(
                    f"Unexpected matrix shape in {path}: {matrix.shape}; "
                    f"expected {(config.NUM_SATELLITES, config.NUM_SATELLITES)}"
                )
            matrices.append(matrix)

        tensor = np.stack(matrices, axis=2)
        out_path = out_dir / output_name
        np.save(out_path, tensor)
        print(f"Saved satellite path {metric} tensor {tensor.shape} to {out_path}")
        outputs.append(out_path)

    return outputs


def build_sat_path_flow_from_routes(config, time_slice_s=1, output_name="sat_path_bytes_from_routes_tensor.npy"):
    """Build satellite path-flow matrices from TCP progress and satgenpy forwarding state.

    For each TCP flow byte delta, this uses the forwarding state active at the
    delta start time to recover the satellite path. The same byte delta is then
    attributed once to every earlier-satellite -> later-satellite pair on that
    path. For A->B->C, a byte delta contributes to A->B, A->C, and B->C.
    """

    num_slices = _num_slices(config, time_slice_s)
    slice_ns = NS_PER_S * time_slice_s
    dynamic_state_dir = config.generated_satellite_network_dir() / config.dynamic_state_dir_name()
    if not dynamic_state_dir.exists():
        raise FileNotFoundError(f"Dynamic state directory not found: {dynamic_state_dir}")

    available_fstates = _available_fstate_times(dynamic_state_dir)
    if not available_fstates:
        raise FileNotFoundError(f"No fstate_*.txt files found in {dynamic_state_dir}")

    flow_endpoints = _read_flow_endpoints(config)
    tensor = np.zeros(
        (config.NUM_SATELLITES, config.NUM_SATELLITES, num_slices),
        dtype=np.uint64,
    )

    fstate_cache = {}
    path_cache = {}
    processed = 0
    skipped = 0
    deltas = 0
    routed_deltas = 0
    single_sat_deltas = 0
    unrouted_deltas = 0
    invalid_next_hop_deltas = 0
    missing_route_deltas = 0
    loop_deltas = 0
    max_hop_deltas = 0
    expanded_pair_updates = 0
    expanded_non_adjacent_updates = 0
    path_length_histogram = {}

    for flow_id in sorted(flow_endpoints):
        progress_path = _logs_dir(config) / f"tcp_flow_{flow_id}_progress.csv"
        if not progress_path.exists():
            skipped += 1
            continue

        src_node, dst_node = flow_endpoints[flow_id]
        prev_time = None
        prev_bytes = None

        with open(progress_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                time_ns = int(parts[1])
                bytes_cum = int(parts[2])

                if prev_time is not None:
                    delta = bytes_cum - prev_bytes
                    if delta > 0:
                        deltas += 1
                        slice_idx = prev_time // slice_ns
                        if 0 <= slice_idx < num_slices:
                            fstate_time = _select_fstate_time(
                                prev_time,
                                available_fstates,
                                getattr(config, "TIME_STEP_MS", time_slice_s * 1000),
                            )
                            route_key = (fstate_time, src_node, dst_node)
                            route_result = path_cache.get(route_key)
                            if route_result is None:
                                fstate = fstate_cache.get(fstate_time)
                                if fstate is None:
                                    fstate = _read_cumulative_fstate(
                                        dynamic_state_dir,
                                        available_fstates,
                                        fstate_time,
                                        fstate_cache,
                                    )
                                    fstate_cache[fstate_time] = fstate
                                route_result = _satellite_path_for_flow(
                                    fstate,
                                    src_node,
                                    dst_node,
                                    config.NUM_SATELLITES,
                                )
                                path_cache[route_key] = route_result

                            status = route_result["status"]
                            path = route_result["path"]
                            path_length_histogram[len(path)] = path_length_histogram.get(len(path), 0) + 1

                            if status == "ok" and len(path) >= 1:
                                routed_deltas += 1
                                if len(path) == 1:
                                    single_sat_deltas += 1
                                pair_updates, non_adjacent_updates = _add_path_delta(
                                    tensor,
                                    path,
                                    int(delta),
                                    int(slice_idx),
                                )
                                expanded_pair_updates += pair_updates
                                expanded_non_adjacent_updates += non_adjacent_updates
                            else:
                                unrouted_deltas += 1
                                if status == "missing_route":
                                    missing_route_deltas += 1
                                elif status == "invalid_next_hop":
                                    invalid_next_hop_deltas += 1
                                elif status == "loop":
                                    loop_deltas += 1
                                elif status == "max_hops_exceeded":
                                    max_hop_deltas += 1

                prev_time = time_ns
                prev_bytes = bytes_cum

        processed += 1

    out_dir = _data_dir(config)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_name
    np.save(out_path, tensor)

    csv_dir = _logs_dir(config) / "sat_path_flow_from_routes" / "bytes"
    csv_dir.mkdir(parents=True, exist_ok=True)
    for slice_idx in range(num_slices):
        csv_path = csv_dir / f"t_{slice_idx:06d}.csv"
        np.savetxt(csv_path, tensor[:, :, slice_idx], delimiter=",", fmt="%d")

    metadata_path = csv_dir.parent / "metadata.txt"
    with open(metadata_path, "w", encoding="utf-8") as f:
        f.write(f"num_satellites={config.NUM_SATELLITES}\n")
        f.write(f"num_time_bins={num_slices}\n")
        f.write(f"interval_ns={slice_ns}\n")
        f.write("layout=matrix[from_sat][to_sat]\n")
        f.write("source=tcp_progress_plus_fstate_routes\n")
        f.write("semantics=flow_delta_expanded_to_all_earlier_later_satellite_pairs\n")
        f.write(f"processed_flows={processed}\n")
        f.write(f"skipped_flows={skipped}\n")
        f.write(f"positive_deltas={deltas}\n")
        f.write(f"routed_deltas={routed_deltas}\n")
        f.write(f"single_sat_deltas={single_sat_deltas}\n")
        f.write(f"unrouted_deltas={unrouted_deltas}\n")
        f.write(f"missing_route_deltas={missing_route_deltas}\n")
        f.write(f"invalid_next_hop_deltas={invalid_next_hop_deltas}\n")
        f.write(f"loop_deltas={loop_deltas}\n")
        f.write(f"max_hop_exceeded_deltas={max_hop_deltas}\n")
        f.write(f"expanded_pair_updates={expanded_pair_updates}\n")
        f.write(f"expanded_non_adjacent_updates={expanded_non_adjacent_updates}\n")
        f.write(f"path_length_histogram={_format_histogram(path_length_histogram)}\n")
        f.write(f"available_fstate_files={len(available_fstates)}\n")

    print(f"Saved route-derived satellite path tensor {tensor.shape} to {out_path}")
    print(f"Saved per-slice CSV matrices to {csv_dir}")
    print(f"Metadata: {metadata_path}")
    print(f"Processed {processed} flows, skipped {skipped}")
    print(f"Positive deltas {deltas}, routed {routed_deltas}, single-sat {single_sat_deltas}, unrouted {unrouted_deltas}")
    return out_path


def verify_sat_connectivity_tensor(path):
    data = np.load(path)
    conn = data["sat_connectivity"]
    print("sat_connectivity shape:", conn.shape)
    print("sat_connectivity dtype:", conn.dtype)
    print("time_ms len:", len(data["time_ms"]))
    print("sat_ids len:", len(data["sat_ids"]))


def _time_matrix_index(path):
    stem = path.stem
    if not stem.startswith("t_"):
        return stem
    return int(stem.split("_", 1)[1])


def _read_key_value_file(path):
    values = {}
    if not path.exists():
        return values
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value
    return values


def _read_flow_endpoints(config):
    flow_map = {}
    path = _logs_dir(config) / "tcp_flows.txt"
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        flow_id = int(parts[0])
        src = int(parts[1])
        dst = int(parts[2])
        flow_map[flow_id] = (src, dst)
    return flow_map


def _available_fstate_times(dynamic_state_dir):
    times = []
    for path in dynamic_state_dir.glob("fstate_*.txt"):
        stem = path.stem
        try:
            times.append(int(stem.split("_", 1)[1]))
        except (IndexError, ValueError):
            continue
    return sorted(times)


def _select_fstate_time(time_ns, available_fstates, time_step_ms):
    step_ns = int(time_step_ms) * 1_000_000
    candidate = int(time_ns // step_ns) * step_ns if step_ns > 0 else int(time_ns)
    if candidate in available_fstates:
        return candidate

    # Fall back to the latest available forwarding state at or before time_ns.
    # This mirrors how a discrete dynamic state is held constant until updated.
    left = 0
    right = len(available_fstates)
    while left < right:
        mid = (left + right) // 2
        if available_fstates[mid] <= time_ns:
            left = mid + 1
        else:
            right = mid
    idx = max(0, left - 1)
    return available_fstates[idx]


def _read_fstate(path):
    forwarding = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            current, dest, next_hop, _own_if, _next_if = line.split(",", 4)
            forwarding[(int(current), int(dest))] = int(next_hop)
    return forwarding


def _read_cumulative_fstate(dynamic_state_dir, available_fstates, target_time, cache):
    # fstate_0 is complete, later fstate files only contain entries which changed
    # relative to the previous state. Reconstruct the full forwarding state.
    if target_time in cache:
        return cache[target_time]

    prior_cached_times = [time for time in cache if time <= target_time]
    if prior_cached_times:
        start_time = max(prior_cached_times)
        forwarding = dict(cache[start_time])
        times_to_apply = [time for time in available_fstates if start_time < time <= target_time]
    else:
        forwarding = {}
        times_to_apply = [time for time in available_fstates if time <= target_time]

    for time in times_to_apply:
        updates = _read_fstate(dynamic_state_dir / f"fstate_{time}.txt")
        forwarding.update(updates)
        cache[time] = dict(forwarding)

    if target_time not in cache:
        cache[target_time] = dict(forwarding)
    return cache[target_time]


def _satellite_path_for_flow(fstate, src_node, dst_node, num_satellites):
    current = src_node
    path = []
    visited = set()
    max_hops = max(4 * num_satellites, 16)

    for _ in range(max_hops):
        if current == dst_node:
            return {"status": "ok", "path": path}
        state_key = (current, dst_node)
        if state_key not in fstate:
            return {"status": "missing_route", "path": path}

        next_node = fstate[state_key]
        if next_node < 0:
            return {"status": "invalid_next_hop", "path": path}
        if next_node < num_satellites and next_node not in path:
            path.append(next_node)

        loop_key = (current, next_node)
        if loop_key in visited or next_node == current:
            return {"status": "loop", "path": path}
        visited.add(loop_key)
        current = next_node

    return {"status": "max_hops_exceeded", "path": path}


def _add_path_delta(tensor, path, delta, slice_idx):
    pair_updates = 0
    non_adjacent_updates = 0
    if len(path) == 1:
        sat = path[0]
        tensor[sat, sat, slice_idx] += delta
        return 1, 0

    for to_pos in range(1, len(path)):
        to_sat = path[to_pos]
        for from_pos in range(to_pos):
            from_sat = path[from_pos]
            if from_sat == to_sat:
                continue
            tensor[from_sat, to_sat, slice_idx] += delta
            pair_updates += 1
            if to_pos - from_pos > 1:
                non_adjacent_updates += 1
    return pair_updates, non_adjacent_updates


def _format_histogram(histogram):
    return ",".join(f"{key}:{histogram[key]}" for key in sorted(histogram))


def _read_isls(path):
    edges = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                a, b = line.split()
                edges.append((int(a), int(b)))
    return edges


def _read_max_isl_length(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("max_isl_length_m="):
                return float(line.split("=", 1)[1])
    raise ValueError(f"max_isl_length_m not found in {path}")
