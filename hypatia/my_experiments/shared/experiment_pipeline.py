"""Reusable experiment pipeline for my_experiments.

Each experiment provides its own config module and constellation helper. This
module owns the common workflow so experiments stay isolated without copying
pipeline logic.
"""

import csv
import os
import shutil
import subprocess
from pathlib import Path


def read_ground_stations(path):
    stations = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) != 5:
                raise ValueError(f"Bad ground station row in {path}: {line}")
            stations.append({
                "local_gs_id": int(parts[0]),
                "name": parts[1],
                "latitude": float(parts[2]),
                "longitude": float(parts[3]),
                "altitude_m": float(parts[4]),
            })
    return stations


def define_ground_stations(config):
    config.INPUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(config.DEFAULT_GROUND_STATIONS_SOURCE, config.GROUND_STATIONS_FILE)

    stations = read_ground_stations(config.GROUND_STATIONS_FILE)
    if len(stations) != config.NUM_GROUND_STATIONS:
        raise ValueError(
            f"Expected {config.NUM_GROUND_STATIONS} ground stations, got {len(stations)}"
        )

    with open(config.GROUND_STATIONS_MANIFEST, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["local_gs_id", "name", "latitude", "longitude", "altitude_m"],
        )
        writer.writeheader()
        writer.writerows(stations)

    print(f"Defined {len(stations)} ground stations")
    print(f"Ground station input: {config.GROUND_STATIONS_FILE}")
    print(f"Readable manifest: {config.GROUND_STATIONS_MANIFEST}")


def design_traffic(config):
    from shared.traffic.traffic_plan import (
        describe_traffic_plan,
        generate_traffic_plan,
        station_activity_rows,
        write_od_matrix_csv,
        write_schedule,
        write_station_activity_csv,
    )

    config.INPUT_DIR.mkdir(parents=True, exist_ok=True)

    flows, traffic_matrix = generate_traffic_plan(config)
    write_schedule(config.TRAFFIC_SCHEDULE_FILE, flows)
    write_od_matrix_csv(config.TRAFFIC_MATRIX_FILE, traffic_matrix)
    write_station_activity_csv(config.TRAFFIC_ACTIVITY_FILE, station_activity_rows(config))

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

    print(f"Generated {len(flows)} TCP flows")
    print(f"Total traffic: {summary['total_size_byte']} bytes")
    print(f"Schedule: {config.TRAFFIC_SCHEDULE_FILE}")
    print(f"Traffic matrix: {config.TRAFFIC_MATRIX_FILE}")
    print(f"Station activity: {config.TRAFFIC_ACTIVITY_FILE}")
    print(f"Design summary: {config.TRAFFIC_DESIGN_FILE}")


def generate_satellite_network_state(config, constellation_helper, threads):
    if not config.GROUND_STATIONS_FILE.exists():
        raise FileNotFoundError(
            f"Ground station file is missing: {config.GROUND_STATIONS_FILE}\n"
            "Run the ground-station definition step first."
        )

    constellation_helper.calculate(
        str(config.GEN_DATA_ROOT),
        config.DURATION_S,
        config.TIME_STEP_MS,
        config.ISL_MODE,
        config.GS_SELECTION,
        config.ROUTING_ALGORITHM,
        threads,
        ground_stations_basic_file=config.GROUND_STATIONS_FILE,
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
    satellite_network_dir_rel = os.path.relpath(satellite_network_dir, run_dir)
    routes_dir_rel = os.path.relpath(routes_dir, run_dir)
    tracking = "true" if config.ENABLE_ISL_UTILIZATION_TRACKING else "false"
    flow_id_set = "set(" + ",".join(str(flow_id) for flow_id in flow_ids) + ")"

    lines = [
        f"simulation_end_time_ns={config.DURATION_S * 1000 * 1000 * 1000}",
        "simulation_seed=123456789",
        "",
        f"satellite_network_dir={satellite_network_dir_rel}",
        f"satellite_network_routes_dir={routes_dir_rel}",
        f"dynamic_state_update_interval_ns={config.TIME_STEP_MS * 1000 * 1000}",
        "",
        f"isl_data_rate_megabit_per_s={config.DATA_RATE_MBIT_PER_S}",
        f"gsl_data_rate_megabit_per_s={config.DATA_RATE_MBIT_PER_S}",
        f"isl_max_queue_size_pkts={config.QUEUE_SIZE_PKTS}",
        f"gsl_max_queue_size_pkts={config.QUEUE_SIZE_PKTS}",
        "",
        f"enable_isl_utilization_tracking={tracking}",
        f"isl_utilization_tracking_interval_ns={config.ISL_UTILIZATION_TRACKING_INTERVAL_NS}",
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
        raise FileNotFoundError(
            f"Satellite network state is missing: {config.generated_satellite_network_dir()}\n"
            "Run the satellite-network-state step first."
        )
    if not config.TRAFFIC_SCHEDULE_FILE.exists():
        raise FileNotFoundError(
            f"Traffic schedule is missing: {config.TRAFFIC_SCHEDULE_FILE}\n"
            "Run the traffic-design step first."
        )

    rd = config.run_dir()
    if rd.exists():
        shutil.rmtree(rd)
    rd.mkdir(parents=True)
    (rd / "logs_ns3").mkdir()

    shutil.copyfile(config.TRAFFIC_SCHEDULE_FILE, rd / "schedule.csv")
    _write_ns3_config(config, rd / "config_ns3.properties", _flow_ids_from_schedule(config.TRAFFIC_SCHEDULE_FILE))

    print(f"Generated ns-3 run directory: {rd}")
    print(f"Config: {rd / 'config_ns3.properties'}")
    print(f"Schedule: {rd / 'schedule.csv'}")


def run_ns3(config, build=False):
    rd = config.run_dir().resolve()
    if not (rd / "config_ns3.properties").exists():
        raise FileNotFoundError(
            f"Run directory is not ready: {rd}\n"
            "Run the ns-3-run generation step first."
        )

    ns3_root = config.HYPATIA_DIR / "ns3-sat-sim"
    simulator_dir = ns3_root / "simulator"

    if build:
        subprocess.run(["bash", "build.sh", "--optimized"], cwd=ns3_root, check=True)

    console_log = rd / "logs_ns3" / "console.txt"
    console_log.parent.mkdir(parents=True, exist_ok=True)
    command = ["./waf", "--run", f"main_satnet --run_dir={rd}"]

    with open(console_log, "w", encoding="utf-8") as log_file:
        subprocess.run(command, cwd=simulator_dir, stdout=log_file, stderr=subprocess.STDOUT, check=True)

    print(f"ns-3 simulation finished: {rd}")
    print(f"Console log: {console_log}")


def run_pipeline(config, constellation_helper, threads=4, build=False):
    define_ground_stations(config)
    design_traffic(config)
    generate_satellite_network_state(config, constellation_helper, threads)
    generate_ns3_run(config)
    run_ns3(config, build=build)
