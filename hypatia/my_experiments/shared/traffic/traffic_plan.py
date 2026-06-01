"""Traffic plan for the Starlink-120 satellite-fill experiment.

The only supported demand model is satellite-pair stratified traffic over
satellite-anchored ground stations.  Each source access satellite selects a
configured number of destination access satellites; for the current experiment
that means 120 x 120 flows, including self-satellite logical pairs that are
mapped to two different ground stations anchored to the same satellite.
"""

import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path


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
    stations = read_ground_stations(config.GROUND_STATIONS_FILE)
    if len(stations) != config.NUM_GROUND_STATIONS:
        raise ValueError(f"Expected {config.NUM_GROUND_STATIONS} ground stations, got {len(stations)}")

    mode = getattr(config, "TRAFFIC_PAIR_MODE", "satellite_pair_stratified")
    if mode != "satellite_pair_stratified":
        raise ValueError("Only TRAFFIC_PAIR_MODE='satellite_pair_stratified' is supported")

    rng = random.Random(getattr(config, "TRAFFIC_SEED", 123456789))
    pairs = _select_satellite_pair_stratified_pairs(config, stations, rng)
    sizes = _allocate_flow_sizes(config, pairs, stations, rng)

    matrix = [[0 for _ in stations] for _ in stations]
    flows = []
    start_time_ns = getattr(config, "TRAFFIC_START_TIME_NS", 0)

    for flow_id, ((src_local, dst_local), size_byte) in enumerate(zip(pairs, sizes)):
        matrix[src_local][dst_local] += size_byte
        flows.append(
            TrafficFlow(
                flow_id=flow_id,
                src_node_id=config.GS_START_NODE_ID + src_local,
                dst_node_id=config.GS_START_NODE_ID + dst_local,
                size_byte=size_byte,
                start_time_ns=start_time_ns,
                src_local_id=src_local,
                dst_local_id=dst_local,
            )
        )

    return flows, matrix


def station_activity_rows(config) -> list[dict[str, str]]:
    rows = []
    for station in read_ground_stations(config.GROUND_STATIONS_FILE):
        rows.append({
            "local_gs_id": str(station.local_id),
            "name": station.name,
            "longitude": str(station.longitude),
            "timezone_offset_hours": "0",
            "reference_utc_hour": str(getattr(config, "TRAFFIC_REFERENCE_UTC_HOUR", 0)),
            "local_hour": str(getattr(config, "TRAFFIC_REFERENCE_UTC_HOUR", 0)),
            "activity": "1.000000000",
        })
    return rows


def _anchor_satellite_id(station: GroundStation) -> int:
    prefix = "SatAnchor-"
    if not station.name.startswith(prefix):
        raise ValueError(
            "satellite_pair_stratified traffic requires ground stations generated "
            "by GROUND_STATION_SELECTION_MODE='satellite_anchored'"
        )
    try:
        return int(station.name[len(prefix):].split("-", 1)[0])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"Cannot parse anchor satellite from ground station name: {station.name}") from exc


def _stations_by_anchor_satellite(stations: list[GroundStation]) -> dict[int, list[GroundStation]]:
    by_satellite = {}
    for station in stations:
        by_satellite.setdefault(_anchor_satellite_id(station), []).append(station)
    return by_satellite


def _same_orbit_plane(config, src_sat: int, dst_sat: int) -> bool:
    return src_sat // config.NUM_SATS_PER_ORBIT == dst_sat // config.NUM_SATS_PER_ORBIT


def _satellite_grid_distance(config, src_sat: int, dst_sat: int) -> int:
    src_plane = src_sat // config.NUM_SATS_PER_ORBIT
    dst_plane = dst_sat // config.NUM_SATS_PER_ORBIT
    src_slot = src_sat % config.NUM_SATS_PER_ORBIT
    dst_slot = dst_sat % config.NUM_SATS_PER_ORBIT

    plane_delta = min(abs(src_plane - dst_plane), config.NUM_ORBITS - abs(src_plane - dst_plane))
    slot_delta = min(abs(src_slot - dst_slot), config.NUM_SATS_PER_ORBIT - abs(src_slot - dst_slot))
    return plane_delta * config.NUM_SATS_PER_ORBIT + slot_delta


def _allocate_stratum_counts(sample_k: int, weights: dict[str, float]) -> dict[str, int]:
    raw_counts = {name: sample_k * float(weight) for name, weight in weights.items()}
    counts = {name: int(math.floor(value)) for name, value in raw_counts.items()}
    remaining = sample_k - sum(counts.values())
    remainders = sorted(
        weights,
        key=lambda name: (raw_counts[name] - counts[name], raw_counts[name]),
        reverse=True,
    )
    for name in remainders[:remaining]:
        counts[name] += 1
    return counts


def _sample_unique(pool: list[int], count: int, selected: set[int], rng: random.Random) -> list[int]:
    candidates = [sat_id for sat_id in pool if sat_id not in selected]
    if len(candidates) <= count:
        rng.shuffle(candidates)
        return candidates
    return rng.sample(candidates, count)


def _stratified_destination_satellites(config, src_sat: int, rng: random.Random) -> list[int]:
    sample_k = int(config.TRAFFIC_SATELLITE_PAIR_SAMPLE_K)
    include_self = bool(getattr(config, "TRAFFIC_INCLUDE_SELF_SAT_DEST", False))
    allow_repeats = bool(getattr(config, "TRAFFIC_ALLOW_REPEATED_DEST_SAT", False))
    max_unique = config.NUM_SATELLITES if include_self else config.NUM_SATELLITES - 1
    if sample_k < 1 or (sample_k > max_unique and not allow_repeats):
        raise ValueError(
            f"TRAFFIC_SATELLITE_PAIR_SAMPLE_K must be in [1, {max_unique}] "
            "unless TRAFFIC_ALLOW_REPEATED_DEST_SAT=True"
        )
    if sample_k == max_unique and not allow_repeats:
        return [
            sat_id
            for sat_id in range(config.NUM_SATELLITES)
            if include_self or sat_id != src_sat
        ]

    near_threshold = int(getattr(config, "TRAFFIC_NEAR_SAT_DISTANCE_MAX", 2))
    mid_threshold = int(getattr(config, "TRAFFIC_MID_SAT_DISTANCE_MAX", 5))
    weights = getattr(config, "TRAFFIC_SATELLITE_DISTANCE_STRATA_WEIGHTS", {
        "near": 0.20,
        "mid": 0.30,
        "far": 0.30,
        "cross_plane": 0.20,
    })
    counts = _allocate_stratum_counts(sample_k, weights)

    strata = {name: [] for name in weights}
    for dst_sat in range(config.NUM_SATELLITES):
        if dst_sat == src_sat and not include_self:
            continue
        grid_distance = _satellite_grid_distance(config, src_sat, dst_sat)
        if not _same_orbit_plane(config, src_sat, dst_sat):
            strata["cross_plane"].append(dst_sat)
        if grid_distance <= near_threshold:
            strata["near"].append(dst_sat)
        elif grid_distance <= mid_threshold:
            strata["mid"].append(dst_sat)
        else:
            strata["far"].append(dst_sat)

    selected = []
    selected_set = set()
    for name in weights:
        for dst_sat in _sample_unique(strata[name], counts[name], selected_set, rng):
            selected.append(dst_sat)
            selected_set.add(dst_sat)

    fallback = [
        sat_id
        for sat_id in range(config.NUM_SATELLITES)
        if (include_self or sat_id != src_sat) and sat_id not in selected_set
    ]
    fallback.sort(key=lambda dst_sat: (_same_orbit_plane(config, src_sat, dst_sat), _satellite_grid_distance(config, src_sat, dst_sat), rng.random()))
    for dst_sat in fallback:
        if len(selected) >= sample_k:
            break
        selected.append(dst_sat)
        selected_set.add(dst_sat)

    if allow_repeats and len(selected) < sample_k:
        repeat_pool = [sat_id for sat_id in range(config.NUM_SATELLITES) if include_self or sat_id != src_sat]
        while len(selected) < sample_k:
            selected.append(rng.choice(repeat_pool))

    return selected[:sample_k]


def _select_ground_station_pair(
    config,
    src_sat: int,
    dst_sat: int,
    src_stations: list[GroundStation],
    dst_stations: list[GroundStation],
    rng: random.Random,
) -> tuple[int, int]:
    min_distance_km = getattr(config, "TRAFFIC_MIN_DISTANCE_KM", 0)
    candidates = []
    for src_station in src_stations:
        for dst_station in dst_stations:
            if src_station.local_id == dst_station.local_id:
                continue
            distance_km = _great_circle_distance_km(
                src_station.latitude,
                src_station.longitude,
                dst_station.latitude,
                dst_station.longitude,
            )
            if src_sat == dst_sat or distance_km >= min_distance_km:
                candidates.append((-distance_km, rng.random(), src_station.local_id, dst_station.local_id))

    if not candidates:
        raise ValueError(f"No non-self ground-station pair for src_sat={src_sat}, dst_sat={dst_sat}")

    candidates.sort()
    _neg_distance, _tie, src_local, dst_local = candidates[0]
    return src_local, dst_local


def _select_satellite_pair_stratified_pairs(
    config,
    stations: list[GroundStation],
    rng: random.Random,
) -> list[tuple[int, int]]:
    stations_by_satellite = _stations_by_anchor_satellite(stations)
    missing = [sat_id for sat_id in range(config.NUM_SATELLITES) if sat_id not in stations_by_satellite]
    if missing:
        raise ValueError(f"Missing anchored ground stations for satellites: {missing[:20]}")

    pairs = []
    for src_sat in range(config.NUM_SATELLITES):
        src_stations = stations_by_satellite[src_sat]
        for dst_sat in _stratified_destination_satellites(config, src_sat, rng):
            pairs.append(
                _select_ground_station_pair(
                    config,
                    src_sat,
                    dst_sat,
                    src_stations,
                    stations_by_satellite[dst_sat],
                    rng,
                )
            )

    expected_flow_count = config.NUM_SATELLITES * int(config.TRAFFIC_SATELLITE_PAIR_SAMPLE_K)
    if getattr(config, "TRAFFIC_FLOW_COUNT", expected_flow_count) != expected_flow_count:
        raise ValueError(
            "TRAFFIC_FLOW_COUNT must equal NUM_SATELLITES * TRAFFIC_SATELLITE_PAIR_SAMPLE_K "
            f"({expected_flow_count})"
        )
    return pairs


def _allocate_flow_sizes(
    config,
    pairs: list[tuple[int, int]],
    stations: list[GroundStation],
    rng: random.Random,
) -> list[int]:
    flow_size = int(getattr(
        config,
        "TRAFFIC_FLOW_SIZE_BYTES",
        getattr(config, "TRAFFIC_TARGET_AVG_FLOW_SIZE_BYTES", 15_000_000),
    ))
    if flow_size <= 0:
        raise ValueError("TRAFFIC_FLOW_SIZE_BYTES must be positive")
    return [flow_size for _pair in pairs]


def _great_circle_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    return 2.0 * earth_radius_km * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


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
        csv.writer(f).writerows(matrix)


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


def write_flow_pair_details_csv(path: Path, config, flows: list[TrafficFlow]) -> None:
    stations = read_ground_stations(config.GROUND_STATIONS_FILE)
    station_by_id = {station.local_id: station for station in stations}
    fieldnames = [
        "flow_id",
        "src_local_id",
        "src_name",
        "src_anchor_sat",
        "src_latitude",
        "src_longitude",
        "dst_local_id",
        "dst_name",
        "dst_anchor_sat",
        "dst_latitude",
        "dst_longitude",
        "distance_km",
        "size_byte",
        "start_time_ns",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for flow in flows:
            src = station_by_id[flow.src_local_id]
            dst = station_by_id[flow.dst_local_id]
            writer.writerow({
                "flow_id": flow.flow_id,
                "src_local_id": flow.src_local_id,
                "src_name": src.name,
                "src_anchor_sat": _anchor_satellite_id(src),
                "src_latitude": src.latitude,
                "src_longitude": src.longitude,
                "dst_local_id": flow.dst_local_id,
                "dst_name": dst.name,
                "dst_anchor_sat": _anchor_satellite_id(dst),
                "dst_latitude": dst.latitude,
                "dst_longitude": dst.longitude,
                "distance_km": f"{_great_circle_distance_km(src.latitude, src.longitude, dst.latitude, dst.longitude):.3f}",
                "size_byte": flow.size_byte,
                "start_time_ns": flow.start_time_ns,
            })


def describe_traffic_plan(config, flows: list[TrafficFlow]) -> dict[str, str]:
    total_bytes = sum(flow.size_byte for flow in flows)
    avg_bytes = total_bytes / len(flows) if flows else 0
    return {
        "pair_mode": "satellite_pair_stratified",
        "flow_count": str(len(flows)),
        "satellite_pair_sample_k": str(config.TRAFFIC_SATELLITE_PAIR_SAMPLE_K),
        "include_self_sat_destination": str(bool(getattr(config, "TRAFFIC_INCLUDE_SELF_SAT_DEST", False))),
        "min_distance_km": str(getattr(config, "TRAFFIC_MIN_DISTANCE_KM", "")),
        "total_size_byte": str(total_bytes),
        "min_flow_size_byte": str(min((flow.size_byte for flow in flows), default=0)),
        "avg_flow_size_byte": str(math.floor(avg_bytes)),
        "max_flow_size_byte": str(max((flow.size_byte for flow in flows), default=0)),
        "all_flows_start_time_ns": str(getattr(config, "TRAFFIC_START_TIME_NS", 0)),
    }
