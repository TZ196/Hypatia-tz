"""Traffic plan generation for ns-3 satellite experiments.

This module intentionally does not create low-rank OD matrices. The traffic
matrix is a simulation demand plan: selected ground stations become nodes,
selected OD pairs become simultaneous TCP flows, and total offered bytes are
bounded by the configured link capacity and simulation duration.
"""

import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path


GEANT_NORMALIZED_ACTIVITY = [
    0.666375187, 0.618642091, 0.590977571, 0.563213085,
    0.541584313, 0.533839914, 0.583266097, 0.667692083,
    0.791995807, 0.888743851, 0.933041611, 0.981479064,
    0.972636759, 0.990605207, 1.000000000, 0.950194854,
    0.942922186, 0.881275688, 0.858416879, 0.834937010,
    0.819007020, 0.810132998, 0.738902802, 0.691278814,
]


@dataclass(frozen=True)
class TrafficFlow:
    flow_id: int
    src_node_id: int
    dst_node_id: int
    size_byte: int
    start_time_ns: int
    src_local_id: int
    dst_local_id: int


@dataclass(frozen=True)
class GroundStation:
    local_id: int
    name: str
    latitude: float
    longitude: float
    altitude_m: float


def read_ground_stations(path: Path) -> list[GroundStation]:
    stations = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            local_id, name, lat, lon, altitude = line.split(",", 4)
            stations.append(
                GroundStation(
                    local_id=int(local_id),
                    name=name,
                    latitude=float(lat),
                    longitude=float(lon),
                    altitude_m=float(altitude),
                )
            )
    return stations


def generate_traffic_plan(config) -> tuple[list[TrafficFlow], list[list[int]]]:
    """Generate simultaneous flows and an OD matrix in bytes.

    Required config fields:
      - GROUND_STATIONS_FILE
      - NUM_GROUND_STATIONS
      - GS_START_NODE_ID
      - DURATION_S
      - DATA_RATE_MBIT_PER_S

    Optional config fields:
      - TRAFFIC_PAIR_MODE: full_mesh | random
      - TRAFFIC_FLOW_COUNT: only for random mode
      - TRAFFIC_SEED
      - TRAFFIC_START_TIME_NS
      - TRAFFIC_OFFERED_LOAD
      - TRAFFIC_CAPACITY_SCOPE: per_ground_station | single_bottleneck
      - TRAFFIC_ACTIVITY_PROFILE: geant | flat
      - TRAFFIC_REFERENCE_UTC_HOUR
      - TRAFFIC_OD_WEIGHT_MODE: source_destination | source_only
      - TRAFFIC_RANDOMNESS_SIGMA
      - TRAFFIC_MIN_FLOW_SIZE_BYTES
      - TRAFFIC_MAX_FLOW_SIZE_BYTES
      - TRAFFIC_REFERENCE_BANDWIDTH_MBIT_PER_S
    """

    stations = read_ground_stations(config.GROUND_STATIONS_FILE)
    if len(stations) != config.NUM_GROUND_STATIONS:
        raise ValueError(
            f"Expected {config.NUM_GROUND_STATIONS} ground stations, got {len(stations)}"
        )

    rng = random.Random(getattr(config, "TRAFFIC_SEED", 123456789))
    pairs = _select_pairs(config, [station.local_id for station in stations], rng)
    total_budget = _traffic_budget_bytes(config)
    activity_by_id = _station_activity_by_id(config, stations)
    pair_weights = _pair_weights(config, pairs, activity_by_id, rng)
    sizes = _allocate_flow_sizes(config, pair_weights, total_budget)

    matrix = [[0 for _ in stations] for _ in stations]
    flows = []
    start_time_ns = getattr(config, "TRAFFIC_START_TIME_NS", 0)

    for flow_id, ((src_local, dst_local), size_byte) in enumerate(zip(pairs, sizes)):
        src_node_id = config.GS_START_NODE_ID + src_local
        dst_node_id = config.GS_START_NODE_ID + dst_local
        matrix[src_local][dst_local] = size_byte
        flows.append(
            TrafficFlow(
                flow_id=flow_id,
                src_node_id=src_node_id,
                dst_node_id=dst_node_id,
                size_byte=size_byte,
                start_time_ns=start_time_ns,
                src_local_id=src_local,
                dst_local_id=dst_local,
            )
        )

    return flows, matrix


def station_activity_rows(config) -> list[dict[str, str]]:
    stations = read_ground_stations(config.GROUND_STATIONS_FILE)
    activity_by_id = _station_activity_by_id(config, stations)
    utc_hour = _reference_utc_hour(config)
    rows = []
    for station in stations:
        offset = _timezone_offset_hours(station.longitude)
        local_hour = (utc_hour + offset) % 24
        rows.append({
            "local_gs_id": str(station.local_id),
            "name": station.name,
            "longitude": str(station.longitude),
            "timezone_offset_hours": str(offset),
            "reference_utc_hour": str(utc_hour),
            "local_hour": str(local_hour),
            "activity": f"{activity_by_id[station.local_id]:.9f}",
        })
    return rows


def _select_pairs(config, local_ids: list[int], rng: random.Random) -> list[tuple[int, int]]:
    mode = getattr(config, "TRAFFIC_PAIR_MODE", "full_mesh")
    pairs = [(src, dst) for src in local_ids for dst in local_ids if src != dst]

    if mode == "full_mesh":
        return pairs

    if mode == "random":
        flow_count = getattr(config, "TRAFFIC_FLOW_COUNT", None)
        if flow_count is None:
            raise ValueError("TRAFFIC_FLOW_COUNT is required when TRAFFIC_PAIR_MODE='random'")
        if flow_count < 1 or flow_count > len(pairs):
            raise ValueError(f"TRAFFIC_FLOW_COUNT must be in [1, {len(pairs)}], got {flow_count}")
        rng.shuffle(pairs)
        return sorted(pairs[:flow_count])

    explicit_pairs = getattr(config, "TRAFFIC_PAIRS", None)
    if mode == "explicit" and explicit_pairs is not None:
        valid_ids = set(local_ids)
        result = []
        for src, dst in explicit_pairs:
            if src == dst:
                raise ValueError("Explicit traffic pairs cannot use the same source and destination")
            if src not in valid_ids or dst not in valid_ids:
                raise ValueError(f"Explicit traffic pair {(src, dst)} is outside selected ground stations")
            result.append((src, dst))
        return result

    raise ValueError(f"Unknown TRAFFIC_PAIR_MODE: {mode}")


def _traffic_budget_bytes(config) -> int:
    reference_mbps = getattr(config, "TRAFFIC_REFERENCE_BANDWIDTH_MBIT_PER_S", None)
    if reference_mbps is None:
        reference_mbps = config.DATA_RATE_MBIT_PER_S

    offered_load = getattr(config, "TRAFFIC_OFFERED_LOAD", 0.2)
    if offered_load <= 0:
        raise ValueError("TRAFFIC_OFFERED_LOAD must be > 0")

    scope = getattr(config, "TRAFFIC_CAPACITY_SCOPE", "per_ground_station")
    if scope == "single_bottleneck":
        multiplier = 1
    elif scope == "per_ground_station":
        multiplier = config.NUM_GROUND_STATIONS
    else:
        raise ValueError("TRAFFIC_CAPACITY_SCOPE must be 'per_ground_station' or 'single_bottleneck'")

    bytes_per_mbit = 1_000_000 / 8
    budget = reference_mbps * config.DURATION_S * bytes_per_mbit * offered_load * multiplier
    return max(1, int(budget))


def _station_activity_by_id(config, stations: list[GroundStation]) -> dict[int, float]:
    profile = getattr(config, "TRAFFIC_ACTIVITY_PROFILE", "geant")
    utc_hour = _reference_utc_hour(config)
    activities = {}

    for station in stations:
        local_hour = (utc_hour + _timezone_offset_hours(station.longitude)) % 24
        if profile == "flat":
            activity = 1.0
        elif profile == "geant":
            activity = GEANT_NORMALIZED_ACTIVITY[local_hour]
        else:
            raise ValueError("TRAFFIC_ACTIVITY_PROFILE must be 'geant' or 'flat'")
        activities[station.local_id] = activity

    return activities


def _reference_utc_hour(config) -> int:
    explicit_hour = getattr(config, "TRAFFIC_REFERENCE_UTC_HOUR", None)
    if explicit_hour is not None:
        if explicit_hour < 0 or explicit_hour > 23:
            raise ValueError("TRAFFIC_REFERENCE_UTC_HOUR must be in [0, 23]")
        return explicit_hour

    start_time_ns = getattr(config, "TRAFFIC_START_TIME_NS", 0)
    return int((start_time_ns // 1_000_000_000 // 3600) % 24)


def _timezone_offset_hours(longitude: float) -> int:
    # Approximate civil time zones from longitude; sufficient for traffic weighting.
    return max(-12, min(14, round(longitude / 15.0)))


def _pair_weights(
    config,
    pairs: list[tuple[int, int]],
    activity_by_id: dict[int, float],
    rng: random.Random,
) -> list[float]:
    mode = getattr(config, "TRAFFIC_OD_WEIGHT_MODE", "source_destination")
    sigma = getattr(config, "TRAFFIC_RANDOMNESS_SIGMA", 0.15)
    if sigma < 0:
        raise ValueError("TRAFFIC_RANDOMNESS_SIGMA must be >= 0")

    weights = []
    for src, dst in pairs:
        src_activity = activity_by_id[src]
        dst_activity = activity_by_id[dst]
        if mode == "source_destination":
            base = src_activity * dst_activity
        elif mode == "source_only":
            base = src_activity
        else:
            raise ValueError("TRAFFIC_OD_WEIGHT_MODE must be 'source_destination' or 'source_only'")

        noise = rng.lognormvariate(0.0, sigma) if sigma > 0 else 1.0
        weights.append(max(1e-12, base * noise))

    return weights


def _allocate_flow_sizes(config, weights: list[float], total_budget: int) -> list[int]:
    if not weights:
        return []

    weight_sum = sum(weights)
    min_size = getattr(config, "TRAFFIC_MIN_FLOW_SIZE_BYTES", 1)
    max_size = getattr(config, "TRAFFIC_MAX_FLOW_SIZE_BYTES", None)

    raw_sizes = [max(min_size, int(round(total_budget * weight / weight_sum))) for weight in weights]
    if max_size is not None:
        raw_sizes = [min(max_size, size) for size in raw_sizes]

    return _rebalance_sizes(raw_sizes, total_budget, min_size, max_size)


def _rebalance_sizes(sizes: list[int], target_total: int, min_size: int, max_size: int | None) -> list[int]:
    if not sizes:
        return sizes

    current = sum(sizes)
    if current == target_total:
        return sizes

    # Keep the total close to the budget after integer rounding and optional caps.
    direction = 1 if current < target_total else -1
    remaining = abs(target_total - current)
    idx = 0
    guard = 0
    while remaining > 0 and guard < len(sizes) * 4:
        can_adjust = (
            (direction > 0 and (max_size is None or sizes[idx] < max_size))
            or (direction < 0 and sizes[idx] > min_size)
        )
        if can_adjust:
            step = remaining
            if direction > 0 and max_size is not None:
                step = min(step, max_size - sizes[idx])
            if direction < 0:
                step = min(step, sizes[idx] - min_size)
            sizes[idx] += direction * step
            remaining -= step
        idx = (idx + 1) % len(sizes)
        guard += 1
    return sizes


def write_schedule(path: Path, flows: list[TrafficFlow]) -> None:
    try:
        import networkload
    except ImportError:
        with open(path, "w", encoding="utf-8") as f:
            for flow in flows:
                f.write(
                    f"{flow.flow_id},{flow.src_node_id},{flow.dst_node_id},"
                    f"{flow.size_byte},{flow.start_time_ns},,\n"
                )
        return

    networkload.write_schedule(
        str(path),
        len(flows),
        [(flow.src_node_id, flow.dst_node_id) for flow in flows],
        [flow.size_byte for flow in flows],
        [flow.start_time_ns for flow in flows],
    )


def write_od_matrix_csv(path: Path, matrix: list[list[int]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(matrix)


def write_station_activity_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "local_gs_id",
        "name",
        "longitude",
        "timezone_offset_hours",
        "reference_utc_hour",
        "local_hour",
        "activity",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def describe_traffic_plan(config, flows: list[TrafficFlow]) -> dict[str, str]:
    total_bytes = sum(flow.size_byte for flow in flows)
    avg_bytes = total_bytes / len(flows) if flows else 0
    max_bytes = max((flow.size_byte for flow in flows), default=0)
    min_bytes = min((flow.size_byte for flow in flows), default=0)
    reference_mbps = getattr(config, "TRAFFIC_REFERENCE_BANDWIDTH_MBIT_PER_S", config.DATA_RATE_MBIT_PER_S)
    ideal_single_link_bytes = reference_mbps * config.DURATION_S * (1_000_000 / 8)

    return {
        "pair_mode": getattr(config, "TRAFFIC_PAIR_MODE", "full_mesh"),
        "activity_profile": getattr(config, "TRAFFIC_ACTIVITY_PROFILE", "geant"),
        "reference_utc_hour": str(_reference_utc_hour(config)),
        "od_weight_mode": getattr(config, "TRAFFIC_OD_WEIGHT_MODE", "source_destination"),
        "randomness_sigma": str(getattr(config, "TRAFFIC_RANDOMNESS_SIGMA", 0.15)),
        "capacity_scope": getattr(config, "TRAFFIC_CAPACITY_SCOPE", "per_ground_station"),
        "offered_load": str(getattr(config, "TRAFFIC_OFFERED_LOAD", 0.2)),
        "flow_count": str(len(flows)),
        "total_size_byte": str(total_bytes),
        "min_flow_size_byte": str(min_bytes),
        "avg_flow_size_byte": str(math.floor(avg_bytes)),
        "max_flow_size_byte": str(max_bytes),
        "ideal_single_link_capacity_byte": str(math.floor(ideal_single_link_bytes)),
        "all_flows_start_time_ns": str(getattr(config, "TRAFFIC_START_TIME_NS", 0)),
    }
