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


@dataclass(frozen=True)
class CandidatePair:
    src: int
    dst: int
    distance_km: float
    src_region: str
    dst_region: str
    priority: int


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
      - TRAFFIC_PAIR_MODE: full_mesh | random | long_distance_balanced | satellite_access_far | satellite_pair_stratified
      - TRAFFIC_FLOW_COUNT: for random and long_distance_balanced modes
      - TRAFFIC_SEED
      - TRAFFIC_START_TIME_NS
      - TRAFFIC_OFFERED_LOAD
      - TRAFFIC_CAPACITY_SCOPE: per_ground_station | single_bottleneck
      - TRAFFIC_ACTIVITY_PROFILE: geant | flat
      - TRAFFIC_REFERENCE_UTC_HOUR
      - TRAFFIC_OD_WEIGHT_MODE: source_destination | source_only | distance | distance_source_destination
      - TRAFFIC_RANDOMNESS_SIGMA
      - TRAFFIC_DISTANCE_WEIGHT_POWER
      - TRAFFIC_PREFERRED_REGION_WEIGHT
      - TRAFFIC_TARGET_AVG_FLOW_SIZE_BYTES
      - TRAFFIC_TOTAL_BUDGET_BYTES
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
    pairs = _select_pairs(config, stations, rng)
    total_budget = _traffic_budget_bytes(config)
    activity_by_id = _station_activity_by_id(config, stations)
    pair_weights = _pair_weights(config, pairs, activity_by_id, stations, rng)
    sizes = _allocate_flow_sizes(config, pair_weights, total_budget)

    matrix = [[0 for _ in stations] for _ in stations]
    flows = []
    start_time_ns = getattr(config, "TRAFFIC_START_TIME_NS", 0)

    for flow_id, ((src_local, dst_local), size_byte) in enumerate(zip(pairs, sizes)):
        src_node_id = config.GS_START_NODE_ID + src_local
        dst_node_id = config.GS_START_NODE_ID + dst_local
        matrix[src_local][dst_local] += size_byte
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


def _select_pairs(config, stations: list[GroundStation], rng: random.Random) -> list[tuple[int, int]]:
    mode = getattr(config, "TRAFFIC_PAIR_MODE", "full_mesh")
    local_ids = [station.local_id for station in stations]
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

    if mode == "long_distance_balanced":
        flow_count = getattr(config, "TRAFFIC_FLOW_COUNT", None)
        if flow_count is None:
            raise ValueError("TRAFFIC_FLOW_COUNT is required when TRAFFIC_PAIR_MODE='long_distance_balanced'")
        return _select_long_distance_balanced_pairs(config, stations, flow_count, rng)

    if mode == "satellite_access_far":
        flow_count = getattr(config, "TRAFFIC_FLOW_COUNT", None)
        if flow_count is None:
            raise ValueError("TRAFFIC_FLOW_COUNT is required when TRAFFIC_PAIR_MODE='satellite_access_far'")
        return _select_satellite_access_far_pairs(config, stations, flow_count, rng)

    if mode == "satellite_pair_stratified":
        return _select_satellite_pair_stratified_pairs(config, stations, rng)

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


def _anchor_satellite_id(station: GroundStation) -> int | None:
    prefix = "SatAnchor-"
    if not station.name.startswith(prefix):
        return None
    rest = station.name[len(prefix):]
    try:
        return int(rest.split("-", 1)[0])
    except (IndexError, ValueError):
        return None


def _satellite_grid_distance(config, src_sat: int, dst_sat: int) -> int:
    sats_per_orbit = getattr(config, "NUM_SATS_PER_ORBIT", None)
    num_orbits = getattr(config, "NUM_ORBITS", None)
    if sats_per_orbit is None or num_orbits is None:
        return abs(src_sat - dst_sat)

    src_plane = src_sat // sats_per_orbit
    dst_plane = dst_sat // sats_per_orbit
    src_slot = src_sat % sats_per_orbit
    dst_slot = dst_sat % sats_per_orbit

    plane_delta = abs(src_plane - dst_plane)
    plane_delta = min(plane_delta, num_orbits - plane_delta)
    slot_delta = abs(src_slot - dst_slot)
    slot_delta = min(slot_delta, sats_per_orbit - slot_delta)
    return plane_delta * sats_per_orbit + slot_delta


def _same_orbit_plane(config, src_sat: int, dst_sat: int) -> bool:
    sats_per_orbit = getattr(config, "NUM_SATS_PER_ORBIT", None)
    if sats_per_orbit is None:
        return False
    return src_sat // sats_per_orbit == dst_sat // sats_per_orbit


def _stations_by_anchor_satellite(stations: list[GroundStation]) -> dict[int, list[GroundStation]]:
    by_satellite = {}
    for station in stations:
        access_sat = _anchor_satellite_id(station)
        if access_sat is None:
            raise ValueError(
                "Satellite-access traffic modes require ground station names "
                "generated by GROUND_STATION_SELECTION_MODE='satellite_anchored'"
            )
        by_satellite.setdefault(access_sat, []).append(station)
    return by_satellite


def _sample_without_replacement(pool, count, rng):
    if count <= 0 or not pool:
        return []
    if len(pool) <= count:
        result = list(pool)
        rng.shuffle(result)
        return result
    return rng.sample(pool, count)


def _allocate_stratum_counts(sample_k, stratum_weights):
    names = list(stratum_weights)
    raw_counts = {name: sample_k * float(stratum_weights[name]) for name in names}
    counts = {name: int(math.floor(raw_counts[name])) for name in names}
    remaining = sample_k - sum(counts.values())
    remainders = sorted(
        names,
        key=lambda name: (raw_counts[name] - counts[name], raw_counts[name]),
        reverse=True,
    )
    for name in remainders[:remaining]:
        counts[name] += 1
    return counts


def _stratified_destination_satellites(config, src_sat, sample_k, rng):
    num_satellites = config.NUM_SATELLITES
    include_self = bool(getattr(config, "TRAFFIC_INCLUDE_SELF_SAT_DEST", False))
    allow_repeats = bool(getattr(config, "TRAFFIC_ALLOW_REPEATED_DEST_SAT", False))
    near_threshold = int(getattr(config, "TRAFFIC_NEAR_SAT_DISTANCE_MAX", 2))
    mid_threshold = int(getattr(config, "TRAFFIC_MID_SAT_DISTANCE_MAX", 5))
    weights = getattr(
        config,
        "TRAFFIC_SATELLITE_DISTANCE_STRATA_WEIGHTS",
        {
            "near": 0.20,
            "mid": 0.30,
            "far": 0.30,
            "cross_plane": 0.20,
        },
    )
    counts = _allocate_stratum_counts(sample_k, weights)

    strata = {name: [] for name in weights}
    for dst_sat in range(num_satellites):
        if dst_sat == src_sat and not include_self:
            continue
        grid_distance = _satellite_grid_distance(config, src_sat, dst_sat)
        same_plane = _same_orbit_plane(config, src_sat, dst_sat)
        if not same_plane:
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
        pool = [sat_id for sat_id in strata[name] if sat_id not in selected_set]
        for dst_sat in _sample_without_replacement(pool, counts[name], rng):
            selected.append(dst_sat)
            selected_set.add(dst_sat)

    if len(selected) < min(sample_k, len(selected_set) + len([
        sat_id for sat_id in range(num_satellites) if (include_self or sat_id != src_sat) and sat_id not in selected_set
    ])):
        fallback = [
            sat_id
            for sat_id in range(num_satellites)
            if (include_self or sat_id != src_sat) and sat_id not in selected_set
        ]
        fallback.sort(key=lambda dst_sat: (_satellite_grid_distance(config, src_sat, dst_sat), rng.random()))
        for dst_sat in fallback:
            if len(selected) >= sample_k:
                break
            selected.append(dst_sat)
            selected_set.add(dst_sat)

    if allow_repeats and len(selected) < sample_k:
        repeated_pool = [sat_id for sat_id in range(num_satellites) if include_self or sat_id != src_sat]
        repeated_pool.sort(key=lambda dst_sat: (_satellite_grid_distance(config, src_sat, dst_sat), rng.random()))
        while len(selected) < sample_k:
            extra_candidates = []
            for name in weights:
                if name == "cross_plane":
                    pool = [sat_id for sat_id in repeated_pool if not _same_orbit_plane(config, src_sat, sat_id)]
                elif name == "near":
                    pool = [sat_id for sat_id in repeated_pool if _satellite_grid_distance(config, src_sat, sat_id) <= near_threshold]
                elif name == "mid":
                    pool = [
                        sat_id for sat_id in repeated_pool
                        if near_threshold < _satellite_grid_distance(config, src_sat, sat_id) <= mid_threshold
                    ]
                else:
                    pool = [sat_id for sat_id in repeated_pool if _satellite_grid_distance(config, src_sat, sat_id) > mid_threshold]
                if pool:
                    extra_candidates.append(rng.choice(pool))

            if not extra_candidates:
                extra_candidates = repeated_pool

            for dst_sat in extra_candidates:
                if len(selected) >= sample_k:
                    break
                selected.append(dst_sat)

    return selected[:sample_k]


def _select_satellite_pair_stratified_pairs(
    config,
    stations: list[GroundStation],
    rng: random.Random,
) -> list[tuple[int, int]]:
    num_satellites = config.NUM_SATELLITES
    sample_k = int(getattr(config, "TRAFFIC_SATELLITE_PAIR_SAMPLE_K", 100))
    include_self = bool(getattr(config, "TRAFFIC_INCLUDE_SELF_SAT_DEST", False))
    allow_repeats = bool(getattr(config, "TRAFFIC_ALLOW_REPEATED_DEST_SAT", False))
    max_k = num_satellites if include_self else (num_satellites - 1)
    if sample_k < 1 or (sample_k > max_k and not allow_repeats):
        raise ValueError(
            f"TRAFFIC_SATELLITE_PAIR_SAMPLE_K must be in [1, {max_k}] unless "
            f"TRAFFIC_ALLOW_REPEATED_DEST_SAT=True, got {sample_k}"
        )

    stations_by_satellite = _stations_by_anchor_satellite(stations)
    missing = [sat_id for sat_id in range(num_satellites) if sat_id not in stations_by_satellite]
    if missing:
        raise ValueError(f"Missing anchored ground stations for satellites: {missing[:20]}")

    min_distance_km = getattr(config, "TRAFFIC_MIN_DISTANCE_KM", 0)
    pairs = []
    for src_sat in range(num_satellites):
        sampled_dst_sats = _stratified_destination_satellites(config, src_sat, sample_k, rng)
        src_stations = stations_by_satellite[src_sat]

        for sample_idx, dst_sat in enumerate(sampled_dst_sats):
            dst_stations = stations_by_satellite[dst_sat]
            pair_candidates = []
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
                        pair_candidates.append((
                            -distance_km,
                            rng.random(),
                            src_station.local_id,
                            dst_station.local_id,
                        ))

            if pair_candidates:
                pair_candidates.sort()
                _neg_distance, _tie, src_local, dst_local = pair_candidates[0]
            else:
                fallback_pair = None
                for src_station in src_stations:
                    for dst_station in dst_stations:
                        if src_station.local_id != dst_station.local_id:
                            fallback_pair = (src_station.local_id, dst_station.local_id)
                            break
                    if fallback_pair is not None:
                        break

                if fallback_pair is None:
                    raise ValueError(
                        f"Could not find a non-self ground-station pair for "
                        f"src_sat={src_sat}, dst_sat={dst_sat}"
                    )

                src_local, dst_local = fallback_pair

            pairs.append((src_local, dst_local))

    configured_flow_count = getattr(config, "TRAFFIC_FLOW_COUNT", None)
    expected_flow_count = num_satellites * sample_k
    if configured_flow_count is not None and configured_flow_count != expected_flow_count:
        raise ValueError(
            f"TRAFFIC_FLOW_COUNT must equal NUM_SATELLITES * TRAFFIC_SATELLITE_PAIR_SAMPLE_K "
            f"({expected_flow_count}) for satellite_pair_stratified mode, got {configured_flow_count}"
        )

    return pairs


def _select_satellite_access_far_pairs(
    config,
    stations: list[GroundStation],
    flow_count: int,
    rng: random.Random,
) -> list[tuple[int, int]]:
    if flow_count < 1:
        raise ValueError("TRAFFIC_FLOW_COUNT must be positive")

    min_distance_km = getattr(config, "TRAFFIC_MIN_DISTANCE_KM", 6000)
    max_per_city_role = getattr(config, "TRAFFIC_MAX_FLOWS_PER_CITY_ROLE", None)
    station_by_id = {station.local_id: station for station in stations}
    access_sat_by_id = {}
    for station in stations:
        access_sat = _anchor_satellite_id(station)
        if access_sat is None:
            raise ValueError(
                "TRAFFIC_PAIR_MODE='satellite_access_far' requires ground station "
                "names generated by GROUND_STATION_SELECTION_MODE='satellite_anchored'"
            )
        access_sat_by_id[station.local_id] = access_sat

    candidates = []
    for src in stations:
        src_sat = access_sat_by_id[src.local_id]
        for dst in stations:
            if src.local_id == dst.local_id:
                continue
            dst_sat = access_sat_by_id[dst.local_id]
            if src_sat == dst_sat:
                continue

            distance_km = _great_circle_distance_km(
                src.latitude,
                src.longitude,
                dst.latitude,
                dst.longitude,
            )
            if distance_km < min_distance_km:
                continue

            sat_distance = _satellite_grid_distance(config, src_sat, dst_sat)
            candidates.append((
                -sat_distance,
                -distance_km,
                rng.random(),
                src.local_id,
                dst.local_id,
            ))

    if len(candidates) < flow_count:
        raise ValueError(
            f"Not enough satellite-access-far OD pairs: need {flow_count}, "
            f"got {len(candidates)} with min distance {min_distance_km} km"
        )

    candidates.sort()
    if max_per_city_role is None:
        max_per_city_role = max(1, math.ceil(flow_count / len(stations) * 2.0))

    selected = []
    used = set()
    source_count = {station.local_id: 0 for station in stations}
    dest_count = {station.local_id: 0 for station in stations}
    access_source_count = {sat_id: 0 for sat_id in set(access_sat_by_id.values())}
    access_dest_count = {sat_id: 0 for sat_id in set(access_sat_by_id.values())}
    current_cap = max_per_city_role

    while len(selected) < flow_count:
        added_this_round = 0
        for _neg_sat_distance, _neg_distance_km, _tie, src_id, dst_id in candidates:
            if len(selected) >= flow_count:
                break
            pair = (src_id, dst_id)
            if pair in used:
                continue
            if source_count[src_id] >= current_cap or dest_count[dst_id] >= current_cap:
                continue

            src_sat = access_sat_by_id[src_id]
            dst_sat = access_sat_by_id[dst_id]
            sat_role_cap = max(1, math.ceil(current_cap * len(stations) / max(1, len(access_source_count))))
            if access_source_count[src_sat] >= sat_role_cap or access_dest_count[dst_sat] >= sat_role_cap:
                continue

            selected.append(pair)
            used.add(pair)
            source_count[src_id] += 1
            dest_count[dst_id] += 1
            access_source_count[src_sat] += 1
            access_dest_count[dst_sat] += 1
            added_this_round += 1

        if added_this_round == 0:
            current_cap += 1

    return selected


def _select_long_distance_balanced_pairs(
    config,
    stations: list[GroundStation],
    flow_count: int,
    rng: random.Random,
) -> list[tuple[int, int]]:
    if flow_count < 1:
        raise ValueError("TRAFFIC_FLOW_COUNT must be positive")
    if len(stations) < 2:
        raise ValueError("At least two ground stations are required")

    min_distance_km = getattr(config, "TRAFFIC_MIN_DISTANCE_KM", 6000)
    max_per_city_role = getattr(config, "TRAFFIC_MAX_FLOWS_PER_CITY_ROLE", None)
    preferred_region_pairs = set(getattr(config, "TRAFFIC_PREFERRED_REGION_PAIRS", _default_region_pairs()))
    candidates = []

    for src in stations:
        src_region = _region_for_station(src)
        for dst in stations:
            if src.local_id == dst.local_id:
                continue
            dst_region = _region_for_station(dst)
            if src_region == dst_region:
                continue
            distance_km = _great_circle_distance_km(src.latitude, src.longitude, dst.latitude, dst.longitude)
            if distance_km < min_distance_km:
                continue
            priority = 0 if (src_region, dst_region) in preferred_region_pairs else 1
            candidates.append(
                CandidatePair(
                    src=src.local_id,
                    dst=dst.local_id,
                    distance_km=distance_km,
                    src_region=src_region,
                    dst_region=dst_region,
                    priority=priority,
                )
            )

    if len(candidates) < flow_count:
        raise ValueError(
            f"Not enough long-distance candidate OD pairs: need {flow_count}, "
            f"got {len(candidates)} with min distance {min_distance_km} km"
        )

    rng.shuffle(candidates)
    candidates.sort(key=lambda pair: (pair.priority, -pair.distance_km))

    if max_per_city_role is None:
        max_per_city_role = max(1, math.ceil(flow_count / len(stations) * 1.5))

    selected = []
    used = set()
    source_count = {station.local_id: 0 for station in stations}
    dest_count = {station.local_id: 0 for station in stations}
    current_cap = max_per_city_role

    while len(selected) < flow_count:
        added_this_round = 0
        for pair in candidates:
            if len(selected) >= flow_count:
                break
            if (pair.src, pair.dst) in used:
                continue
            if source_count[pair.src] >= current_cap or dest_count[pair.dst] >= current_cap:
                continue

            selected.append((pair.src, pair.dst))
            used.add((pair.src, pair.dst))
            source_count[pair.src] += 1
            dest_count[pair.dst] += 1
            added_this_round += 1

        if added_this_round == 0:
            # Relax the per-city cap only if the target count cannot be reached.
            current_cap += 1

    # Keep output deterministic and readable by flow ID while preserving selected pairs.
    return selected


def _default_region_pairs():
    return [
        ("Asia", "South America"),
        ("Asia", "Africa"),
        ("North America", "Oceania"),
        ("Europe", "Oceania"),
        ("Africa", "North America"),
        ("South America", "Europe"),
    ]


def _region_for_station(station: GroundStation) -> str:
    lat = station.latitude
    lon = station.longitude

    if lon >= -170 and lon <= -30 and lat >= -60 and lat <= 15:
        return "South America"
    if lon >= -170 and lon <= -30 and lat > 15:
        return "North America"
    if lon >= 110 and lon <= 180 and lat <= 0:
        return "Oceania"
    if lon >= 110 and lon <= 180 and lat > 0:
        return "Asia"
    if lon >= -30 and lon <= 60 and lat >= 35:
        return "Europe"
    if lon >= -20 and lon <= 55 and lat < 35 and lat >= -40:
        return "Africa"
    if lon > 55 and lon < 110:
        return "Asia"
    if lon < -170 or lon > 180:
        return "Oceania"
    return "Other"


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


def _traffic_budget_bytes(config) -> int:
    explicit_budget = getattr(config, "TRAFFIC_TOTAL_BUDGET_BYTES", None)
    if explicit_budget is not None:
        if explicit_budget <= 0:
            raise ValueError("TRAFFIC_TOTAL_BUDGET_BYTES must be > 0")
        return int(explicit_budget)

    target_avg = getattr(config, "TRAFFIC_TARGET_AVG_FLOW_SIZE_BYTES", None)
    flow_count = getattr(config, "TRAFFIC_FLOW_COUNT", None)
    if target_avg is not None:
        if target_avg <= 0:
            raise ValueError("TRAFFIC_TARGET_AVG_FLOW_SIZE_BYTES must be > 0")
        if flow_count is None:
            raise ValueError("TRAFFIC_FLOW_COUNT is required when using TRAFFIC_TARGET_AVG_FLOW_SIZE_BYTES")
        return int(target_avg * flow_count)

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
    stations: list[GroundStation],
    rng: random.Random,
) -> list[float]:
    mode = getattr(config, "TRAFFIC_OD_WEIGHT_MODE", "source_destination")
    sigma = getattr(config, "TRAFFIC_RANDOMNESS_SIGMA", 0.15)
    if sigma < 0:
        raise ValueError("TRAFFIC_RANDOMNESS_SIGMA must be >= 0")

    station_by_id = {station.local_id: station for station in stations}
    preferred_region_pairs = set(getattr(config, "TRAFFIC_PREFERRED_REGION_PAIRS", _default_region_pairs()))
    distance_power = getattr(config, "TRAFFIC_DISTANCE_WEIGHT_POWER", 1.0)
    preferred_region_weight = getattr(config, "TRAFFIC_PREFERRED_REGION_WEIGHT", 1.0)

    weights = []
    for src, dst in pairs:
        src_activity = activity_by_id[src]
        dst_activity = activity_by_id[dst]
        if mode == "source_destination":
            base = src_activity * dst_activity
        elif mode == "source_only":
            base = src_activity
        elif mode in {"distance", "distance_source_destination"}:
            src_station = station_by_id[src]
            dst_station = station_by_id[dst]
            distance_km = _great_circle_distance_km(
                src_station.latitude,
                src_station.longitude,
                dst_station.latitude,
                dst_station.longitude,
            )
            distance_weight = max(distance_km / 1000.0, 1.0) ** distance_power
            region_weight = preferred_region_weight if (
                _region_for_station(src_station),
                _region_for_station(dst_station),
            ) in preferred_region_pairs else 1.0
            base = distance_weight * region_weight
            if mode == "distance_source_destination":
                base *= src_activity * dst_activity
        else:
            raise ValueError(
                "TRAFFIC_OD_WEIGHT_MODE must be 'source_destination', 'source_only', "
                "'distance', or 'distance_source_destination'"
            )

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


def write_flow_pair_details_csv(path: Path, config, flows: list[TrafficFlow]) -> None:
    stations = read_ground_stations(config.GROUND_STATIONS_FILE)
    station_by_id = {station.local_id: station for station in stations}
    fieldnames = [
        "flow_id",
        "src_local_id",
        "src_name",
        "src_region",
        "src_latitude",
        "src_longitude",
        "dst_local_id",
        "dst_name",
        "dst_region",
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
                "src_region": _region_for_station(src),
                "src_latitude": src.latitude,
                "src_longitude": src.longitude,
                "dst_local_id": flow.dst_local_id,
                "dst_name": dst.name,
                "dst_region": _region_for_station(dst),
                "dst_latitude": dst.latitude,
                "dst_longitude": dst.longitude,
                "distance_km": f"{_great_circle_distance_km(src.latitude, src.longitude, dst.latitude, dst.longitude):.3f}",
                "size_byte": flow.size_byte,
                "start_time_ns": flow.start_time_ns,
            })


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
        "target_avg_flow_size_byte": str(getattr(config, "TRAFFIC_TARGET_AVG_FLOW_SIZE_BYTES", "")),
        "total_budget_byte_override": str(getattr(config, "TRAFFIC_TOTAL_BUDGET_BYTES", "")),
        "flow_count": str(len(flows)),
        "min_distance_km": str(getattr(config, "TRAFFIC_MIN_DISTANCE_KM", "")),
        "max_flows_per_city_role": str(getattr(config, "TRAFFIC_MAX_FLOWS_PER_CITY_ROLE", "")),
        "total_size_byte": str(total_bytes),
        "min_flow_size_byte": str(min_bytes),
        "avg_flow_size_byte": str(math.floor(avg_bytes)),
        "max_flow_size_byte": str(max_bytes),
        "ideal_single_link_capacity_byte": str(math.floor(ideal_single_link_bytes)),
        "all_flows_start_time_ns": str(getattr(config, "TRAFFIC_START_TIME_NS", 0)),
    }
