"""Pipeline used by the starlink_550_120_satfill_3s experiment.

This project currently keeps one dataset-generation experiment.  The shared
pipeline is intentionally narrow: satellite-anchored ground stations,
stratified satellite-pair traffic, Starlink-120 constellation state generation,
and ns-3 run-directory creation/execution.
"""

import csv
import importlib
import math
import os
import random
import shutil
import subprocess
import sys


def read_ground_stations(path):
    stations = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) != 5:
                raise ValueError(f"Invalid ground station row in {path}: {line}")
            stations.append({
                "local_gs_id": int(parts[0]),
                "name": parts[1],
                "latitude": float(parts[2]),
                "longitude": float(parts[3]),
                "altitude_m": float(parts[4]),
            })
    return stations


def _write_ground_stations_basic(path, stations):
    with open(path, "w", encoding="utf-8") as f:
        for station in stations:
            f.write(
                f"{station['local_gs_id']},{station['name']},"
                f"{station['latitude']},{station['longitude']},{station['altitude_m']}\n"
            )


def _normalize_longitude(longitude):
    return ((longitude + 180.0) % 360.0) - 180.0


def _offset_lat_lon(latitude, longitude, distance_km, bearing_degrees):
    earth_radius_km = 6371.0
    angular_distance = distance_km / earth_radius_km
    bearing = math.radians(bearing_degrees)
    lat1 = math.radians(latitude)
    lon1 = math.radians(longitude)

    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance)
        + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), _normalize_longitude(math.degrees(lon2))


def _generate_satellite_anchored_ground_stations(config):
    count = config.NUM_GROUND_STATIONS
    num_satellites = config.NUM_SATELLITES
    if count < num_satellites or count > 2 * num_satellites:
        raise ValueError(
            "satellite_anchored ground stations require "
            "NUM_SATELLITES <= NUM_GROUND_STATIONS <= 2 * NUM_SATELLITES"
        )

    satgenpy_dir = config.HYPATIA_DIR / "satgenpy"
    if str(satgenpy_dir) not in sys.path:
        sys.path.insert(0, str(satgenpy_dir))
    if str(config.MY_EXPERIMENTS_DIR) not in sys.path:
        sys.path.insert(0, str(config.MY_EXPERIMENTS_DIR))

    import satgen
    from astropy import units as u

    constellation = importlib.import_module(f"shared.constellation.main_{config.SATELLITE_NETWORK}")
    helper = constellation.main_helper
    anchor_time_ns = int(getattr(config, "GROUND_STATION_ANCHOR_TIME_NS", 0))
    jitter_km = float(getattr(config, "GROUND_STATION_ANCHOR_JITTER_KM", 50.0))
    seed = getattr(config, "GROUND_STATION_RANDOM_SEED", getattr(config, "TRAFFIC_SEED", 123456789))
    rng = random.Random(seed)

    config.INPUT_DIR.mkdir(parents=True, exist_ok=True)
    anchor_tles = config.INPUT_DIR / f"{config.SATELLITE_NETWORK}_anchor_tles.txt"
    satgen.generate_tles_from_scratch_manual(
        str(anchor_tles),
        helper.NICE_NAME,
        helper.NUM_ORBS,
        helper.NUM_SATS_PER_ORB,
        helper.PHASE_DIFF,
        helper.INCLINATION_DEGREE,
        helper.ECCENTRICITY,
        helper.ARG_OF_PERIGEE_DEGREE,
        helper.MEAN_MOTION_REV_PER_DAY,
    )
    tle_info = satgen.read_tles(str(anchor_tles))
    epoch = tle_info["epoch"]
    anchor_time = epoch + anchor_time_ns * u.ns

    stations = []
    for sat_id, satellite in enumerate(tle_info["satellites"]):
        shadow = satgen.create_basic_ground_station_for_satellite_shadow(
            satellite,
            str(epoch),
            str(anchor_time),
        )
        stations.append({
            "local_gs_id": len(stations),
            "source_gs_id": len(stations),
            "name": f"SatAnchor-{sat_id:04d}-base",
            "latitude": round(float(shadow["latitude_degrees_str"]), 6),
            "longitude": round(float(shadow["longitude_degrees_str"]), 6),
            "altitude_m": 0.0,
        })

    for extra_idx in range(count - num_satellites):
        sat_id = extra_idx % num_satellites
        base = stations[sat_id]
        latitude, longitude = _offset_lat_lon(
            base["latitude"],
            base["longitude"],
            jitter_km * (0.5 + 0.5 * rng.random()),
            rng.random() * 360.0,
        )
        stations.append({
            "local_gs_id": len(stations),
            "source_gs_id": len(stations),
            "name": f"SatAnchor-{sat_id:04d}-jitter",
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
            "altitude_m": 0.0,
        })

    _write_ground_stations_basic(config.GROUND_STATIONS_FILE, stations)
    return stations


def define_ground_stations(config):
    mode = getattr(config, "GROUND_STATION_SELECTION_MODE", "satellite_anchored")
    if mode != "satellite_anchored":
        raise ValueError("Only GROUND_STATION_SELECTION_MODE='satellite_anchored' is supported")

    config.INPUT_DIR.mkdir(parents=True, exist_ok=True)
    stations = _generate_satellite_anchored_ground_stations(config)
    if len(stations) != config.NUM_GROUND_STATIONS:
        raise ValueError(
            f"Ground station count mismatch: expected {config.NUM_GROUND_STATIONS}, got {len(stations)}"
        )

    with open(config.GROUND_STATIONS_MANIFEST, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["local_gs_id", "source_gs_id", "name", "latitude", "longitude", "altitude_m"],
        )
        writer.writeheader()
        writer.writerows(stations)

    print(f"Defined {len(stations)} satellite-anchored ground stations")
    print(f"Ground station file: {config.GROUND_STATIONS_FILE}")
    print(f"Ground station manifest: {config.GROUND_STATIONS_MANIFEST}")


def design_traffic(config):
    from shared.traffic.traffic_plan import (
        describe_traffic_plan,
        generate_traffic_plan,
        station_activity_rows,
        write_flow_pair_details_csv,
        write_od_matrix_csv,
        write_schedule,
        write_station_activity_csv,
    )

    config.INPUT_DIR.mkdir(parents=True, exist_ok=True)
    flows, traffic_matrix = generate_traffic_plan(config)
    write_schedule(config.TRAFFIC_SCHEDULE_FILE, flows)
    write_od_matrix_csv(config.TRAFFIC_MATRIX_FILE, traffic_matrix)
    write_station_activity_csv(config.TRAFFIC_ACTIVITY_FILE, station_activity_rows(config))
    if getattr(config, "TRAFFIC_FLOW_DETAILS_FILE", None) is not None:
        write_flow_pair_details_csv(config.TRAFFIC_FLOW_DETAILS_FILE, config, flows)

    summary = describe_traffic_plan(config, flows)
    with open(config.TRAFFIC_DESIGN_FILE, "w", encoding="utf-8") as f:
        f.write("Traffic design\n")
        f.write(f"ground_stations={config.NUM_GROUND_STATIONS}\n")
        f.write(
            "ground_station_node_ids="
            f"{config.GS_START_NODE_ID}.."
            f"{config.GS_START_NODE_ID + config.NUM_GROUND_STATIONS - 1}\n"
        )
        f.write(f"seed={config.TRAFFIC_SEED}\n")
        for key, value in summary.items():
            f.write(f"{key}={value}\n")
        f.write(f"schedule={config.TRAFFIC_SCHEDULE_FILE.name}\n")
        f.write(f"traffic_matrix={config.TRAFFIC_MATRIX_FILE.name}\n")
        f.write(f"station_activity={config.TRAFFIC_ACTIVITY_FILE.name}\n")
        if getattr(config, "TRAFFIC_FLOW_DETAILS_FILE", None) is not None:
            f.write(f"traffic_flow_details={config.TRAFFIC_FLOW_DETAILS_FILE.name}\n")

    print(f"Generated {len(flows)} TCP flows")
    print(f"Total traffic: {summary['total_size_byte']} bytes")
    print(f"Schedule: {config.TRAFFIC_SCHEDULE_FILE}")
    print(f"Traffic matrix: {config.TRAFFIC_MATRIX_FILE}")
    print(f"Traffic design summary: {config.TRAFFIC_DESIGN_FILE}")


def generate_satellite_network_state(config, constellation_helper, threads):
    if not config.GROUND_STATIONS_FILE.exists():
        raise FileNotFoundError(f"Missing ground station file: {config.GROUND_STATIONS_FILE}")

    constellation_helper.calculate(
        str(config.GEN_DATA_ROOT),
        config.DURATION_S,
        config.TIME_STEP_MS,
        config.ISL_MODE,
        config.GS_SELECTION,
        config.ROUTING_ALGORITHM,
        threads,
        ground_stations_basic_file=config.GROUND_STATIONS_FILE,
        isl_shift=getattr(config, "ISL_SHIFT", 0),
    )
    print(f"Generated satellite network state: {config.generated_satellite_network_dir()}")


def _flow_ids_from_schedule(schedule_path):
    flow_ids = []
    with open(schedule_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                flow_ids.append(int(line.split(",", 1)[0]))
    return flow_ids


def _write_ns3_config(config, config_path, flow_ids):
    run_dir = config.run_dir().resolve()
    satellite_network_dir = config.generated_satellite_network_dir().resolve()
    routes_dir = satellite_network_dir / config.dynamic_state_dir_name()
    tracking = "true" if config.ENABLE_ISL_UTILIZATION_TRACKING else "false"
    path_tracking = "true" if getattr(config, "ENABLE_SATELLITE_PATH_TRACKING", False) else "false"
    path_tracking_interval_ns = getattr(
        config,
        "SATELLITE_PATH_TRACKING_INTERVAL_NS",
        getattr(config, "ISL_UTILIZATION_TRACKING_INTERVAL_NS", 1_000_000_000),
    )
    enabled_flow_ids = flow_ids if getattr(config, "ENABLE_TCP_FLOW_LOGGING", True) else []
    flow_id_set = "set(" + ",".join(str(flow_id) for flow_id in enabled_flow_ids) + ")"

    isl_data_rate_mbit_per_s = getattr(config, "ISL_DATA_RATE_MBIT_PER_S", config.DATA_RATE_MBIT_PER_S)
    gsl_data_rate_mbit_per_s = getattr(config, "GSL_DATA_RATE_MBIT_PER_S", config.DATA_RATE_MBIT_PER_S)

    lines = [
        f"simulation_end_time_ns={config.DURATION_S * 1000 * 1000 * 1000}",
        "simulation_seed=123456789",
        "",
        f"satellite_network_dir={os.path.relpath(satellite_network_dir, run_dir)}",
        f"satellite_network_routes_dir={os.path.relpath(routes_dir, run_dir)}",
        f"dynamic_state_update_interval_ns={config.TIME_STEP_MS * 1000 * 1000}",
        "",
        f"isl_data_rate_megabit_per_s={isl_data_rate_mbit_per_s}",
        f"gsl_data_rate_megabit_per_s={gsl_data_rate_mbit_per_s}",
        f"isl_max_queue_size_pkts={config.QUEUE_SIZE_PKTS}",
        f"gsl_max_queue_size_pkts={config.QUEUE_SIZE_PKTS}",
        "",
        f"enable_isl_utilization_tracking={tracking}",
        f"isl_utilization_tracking_interval_ns={config.ISL_UTILIZATION_TRACKING_INTERVAL_NS}",
        f"enable_satellite_path_tracking={path_tracking}",
        f"satellite_path_tracking_interval_ns={path_tracking_interval_ns}",
        "",
        f"tcp_socket_type={config.TCP_SOCKET_TYPE}",
        "",
        "enable_tcp_flow_scheduler=true",
        "tcp_flow_schedule_filename=\"schedule.csv\"",
        f"tcp_flow_enable_logging_for_tcp_flow_ids={flow_id_set}",
        "",
    ]
    config_path.write_text("\n".join(lines), encoding="utf-8")


def generate_ns3_run(config):
    if not config.generated_satellite_network_dir().exists():
        raise FileNotFoundError(f"Missing satellite network state: {config.generated_satellite_network_dir()}")
    if not config.TRAFFIC_SCHEDULE_FILE.exists():
        raise FileNotFoundError(f"Missing traffic schedule: {config.TRAFFIC_SCHEDULE_FILE}")

    rd = config.run_dir()
    if rd.exists():
        shutil.rmtree(rd)
    rd.mkdir(parents=True)
    (rd / "logs_ns3").mkdir()

    shutil.copyfile(config.TRAFFIC_SCHEDULE_FILE, rd / "schedule.csv")

    satellite_network_dir = config.generated_satellite_network_dir()
    for filename in ["tles.txt", "isls.txt", "gsl_interfaces_info.txt"]:
        src = satellite_network_dir / filename
        if not src.exists():
            raise FileNotFoundError(f"Missing ns-3 input file: {src}")
        shutil.copyfile(src, rd / filename)

    description = satellite_network_dir / "description.txt"
    if description.exists():
        shutil.copyfile(description, rd / "description.txt")

    _write_ns3_config(config, rd / "config_ns3.properties", _flow_ids_from_schedule(config.TRAFFIC_SCHEDULE_FILE))

    print(f"Generated ns-3 run directory: {rd}")
    print(f"ns-3 config: {rd / 'config_ns3.properties'}")


def run_ns3(config, build=False):
    rd = config.run_dir().resolve()
    if not (rd / "config_ns3.properties").exists():
        raise FileNotFoundError(f"ns-3 run directory is not ready: {rd}")

    ns3_root = config.HYPATIA_DIR / "ns3-sat-sim"
    simulator_dir = ns3_root / "simulator"

    if build:
        print("Building ns-3 simulator...")
        subprocess.run(["bash", "build.sh", "--optimized"], cwd=ns3_root, check=True)

    console_log = rd / "logs_ns3" / "console.txt"
    console_log.parent.mkdir(parents=True, exist_ok=True)
    command = ["./waf", "--run", f"main_satnet --run_dir={rd}"]

    print("Running ns-3 simulation...")
    print(f"Run directory: {rd}")
    print(f"Console log: {console_log}")
    with open(console_log, "w", encoding="utf-8") as log_file:
        subprocess.run(
            command,
            cwd=simulator_dir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=True,
        )

    print(f"ns-3 simulation completed: {rd}")


def run_pipeline(config, constellation_helper, threads=4, build=False):
    define_ground_stations(config)
    design_traffic(config)
    generate_satellite_network_state(config, constellation_helper, threads)
    generate_ns3_run(config)
    run_ns3(config, build=build)
