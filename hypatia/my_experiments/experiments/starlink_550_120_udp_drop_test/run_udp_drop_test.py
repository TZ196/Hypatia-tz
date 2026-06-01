#!/usr/bin/env python3
"""Run a small UDP stress test for satellite path drop accounting.

The main Starlink satfill experiment uses TCP, whose socket buffering and
congestion control can avoid device-queue overflow even under severe
under-completion. This diagnostic uses open-loop UDP bursts, high GSL
bandwidth, very low ISL bandwidth, and tiny queues so packets enter satellite
paths and then pressure ISL queues.
"""

import argparse
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

import experiment_config as config

if str(config.MY_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(config.MY_EXPERIMENTS_DIR))

from shared.constellation.main_starlink_550_120 import main_helper
from shared.experiment_pipeline import define_ground_stations, generate_satellite_network_state


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--build", action="store_true", help="Build ns-3 before running")
    parser.add_argument("--isl-mbps", type=int, default=5, help="Diagnostic ISL bandwidth")
    parser.add_argument("--gsl-mbps", type=int, default=10_000, help="Diagnostic GSL bandwidth")
    parser.add_argument("--isl-queue-pkts", type=int, default=1, help="Diagnostic ISL queue size")
    parser.add_argument(
        "--gsl-queue-pkts",
        type=int,
        default=100_000,
        help="Diagnostic GSL queue size; keep this large so drops happen on satellite ISLs",
    )
    parser.add_argument(
        "--queue-pkts",
        type=int,
        default=None,
        help="Backward-compatible override for both ISL and GSL queue sizes",
    )
    parser.add_argument("--udp-rate-mbps", type=int, default=5_000, help="Each UDP burst target rate")
    parser.add_argument("--duration-s", type=int, default=3, help="Diagnostic simulation duration")
    return parser.parse_args()


def write_udp_schedule(path: Path, udp_rate_mbps: int, duration_s: int) -> None:
    # Local ground station i is anchored to satellite i for i in [0, 119].
    # These pairs are far apart in satellite index space to encourage multi-hop
    # and cross-plane satellite paths.
    gs_start = config.GS_START_NODE_ID
    pairs = [
        (0, gs_start + 0, gs_start + 60),
        (1, gs_start + 12, gs_start + 72),
        (2, gs_start + 24, gs_start + 84),
        (3, gs_start + 36, gs_start + 96),
    ]
    start_time_ns = 100_000_000
    burst_duration_ns = max(1, duration_s - 1) * 1_000_000_000

    with open(path, "w", encoding="utf-8") as f:
        for burst_id, src, dst in pairs:
            f.write(
                f"{burst_id},{src},{dst},{udp_rate_mbps},"
                f"{start_time_ns},{burst_duration_ns},,udp_drop_probe_{burst_id}\n"
            )


def write_ns3_config(path: Path, rd: Path, args) -> None:
    satellite_network_dir = config.generated_satellite_network_dir().resolve()
    routes_dir = satellite_network_dir / config.dynamic_state_dir_name()
    isl_queue_pkts = args.queue_pkts if args.queue_pkts is not None else args.isl_queue_pkts
    gsl_queue_pkts = args.queue_pkts if args.queue_pkts is not None else args.gsl_queue_pkts

    lines = [
        f"simulation_end_time_ns={args.duration_s * 1_000_000_000}",
        "simulation_seed=123456789",
        "",
        f"satellite_network_dir={os.path.relpath(satellite_network_dir, rd.resolve())}",
        f"satellite_network_routes_dir={os.path.relpath(routes_dir, rd.resolve())}",
        f"dynamic_state_update_interval_ns={config.TIME_STEP_MS * 1_000_000}",
        "",
        f"isl_data_rate_megabit_per_s={args.isl_mbps}",
        f"gsl_data_rate_megabit_per_s={args.gsl_mbps}",
        f"isl_max_queue_size_pkts={isl_queue_pkts}",
        f"gsl_max_queue_size_pkts={gsl_queue_pkts}",
        "",
        "enable_isl_utilization_tracking=true",
        f"isl_utilization_tracking_interval_ns={config.ISL_UTILIZATION_TRACKING_INTERVAL_NS}",
        "enable_satellite_path_tracking=true",
        f"satellite_path_tracking_interval_ns={config.SATELLITE_PATH_TRACKING_INTERVAL_NS}",
        "",
        f"tcp_socket_type={config.TCP_SOCKET_TYPE}",
        "enable_tcp_flow_scheduler=false",
        "",
        "enable_udp_burst_scheduler=true",
        "udp_burst_schedule_filename=\"udp_burst_schedule.csv\"",
        "udp_burst_enable_logging_for_udp_burst_ids=set(0,1,2,3)",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def prepare_run_dir(args) -> Path:
    rd = config.run_dir()
    if rd.exists():
        shutil.rmtree(rd)
    rd.mkdir(parents=True)
    (rd / "logs_ns3").mkdir()

    satellite_network_dir = config.generated_satellite_network_dir()
    for filename in ["tles.txt", "isls.txt", "gsl_interfaces_info.txt"]:
        src = satellite_network_dir / filename
        if not src.exists():
            raise FileNotFoundError(f"Missing ns-3 input file: {src}")
        shutil.copyfile(src, rd / filename)

    description = satellite_network_dir / "description.txt"
    if description.exists():
        shutil.copyfile(description, rd / "description.txt")

    write_udp_schedule(rd / "udp_burst_schedule.csv", args.udp_rate_mbps, args.duration_s)
    write_ns3_config(rd / "config_ns3.properties", rd, args)
    return rd


def run_ns3(rd: Path, build: bool) -> None:
    ns3_root = config.HYPATIA_DIR / "ns3-sat-sim"
    simulator_dir = ns3_root / "simulator"

    if build:
        subprocess.run(["bash", "build.sh", "--optimized"], cwd=ns3_root, check=True)

    console_log = rd / "logs_ns3" / "console.txt"
    with open(console_log, "w", encoding="utf-8") as log_file:
        subprocess.run(
            ["./waf", "--run", f"main_satnet --run_dir={rd.resolve()}"],
            cwd=simulator_dir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=True,
        )


def sum_matrix_dir(metric_dir: Path) -> int:
    total = 0
    if not metric_dir.exists():
        return total
    for path in sorted(metric_dir.glob("t_*.csv")):
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                total += sum(int(value) for value in row if value)
    return total


def read_metadata(path: Path) -> dict[str, str]:
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


def read_ns3_config(path: Path) -> dict[str, str]:
    values = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip('"')
    return values


def sum_udp_csv(path: Path, packets_column: int) -> int:
    if not path.exists():
        return 0
    total = 0
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) > packets_column:
                total += int(row[packets_column])
    return total


def summarize(rd: Path) -> None:
    base_dir = rd / "logs_ns3" / "sat_path_flow"
    ns3_config = read_ns3_config(rd / "config_ns3.properties")
    metadata = read_metadata(base_dir / "metadata.txt")
    drop_bytes = sum_matrix_dir(base_dir / "drop_bytes")
    bytes_total = sum_matrix_dir(base_dir / "bytes")
    udp_sent_packets = sum_udp_csv(rd / "logs_ns3" / "udp_bursts_outgoing.csv", 8)
    udp_received_packets = sum_udp_csv(rd / "logs_ns3" / "udp_bursts_incoming.csv", 8)

    print("=== UDP drop diagnostic summary ===")
    print(f"run_dir={rd}")
    for key in [
        "isl_data_rate_megabit_per_s",
        "gsl_data_rate_megabit_per_s",
        "isl_max_queue_size_pkts",
        "gsl_max_queue_size_pkts",
    ]:
        print(f"{key}={ns3_config.get(key, 'MISSING')}")
    print(f"udp_sent_packets={udp_sent_packets}")
    print(f"udp_received_packets={udp_received_packets}")
    print(f"udp_unreceived_packets={udp_sent_packets - udp_received_packets}")
    print(f"path_bytes={bytes_total}")
    print(f"path_drop_bytes={drop_bytes}")
    print(f"drop_accounting_worked={drop_bytes > 0}")
    for key in [
        "satellite_drop_events",
        "satellite_drop_events_without_path_tag",
        "satellite_drop_events_without_open_path",
        "satellite_drop_events_recorded",
        "satellite_drop_events_recorded_with_next_hop",
        "satellite_drop_events_next_hop_not_satellite",
        "unfinished_path_events_at_finish",
        "unfinished_path_events_recorded",
        "unfinished_path_bytes_at_finish",
        "open_packet_paths_at_finish",
        "open_packet_paths_after_finish_accounting",
    ]:
        if key in metadata:
            print(f"{key}={metadata[key]}")
    print(f"metadata={base_dir / 'metadata.txt'}")
    print(f"console={rd / 'logs_ns3' / 'console.txt'}")


def main():
    args = parse_args()
    define_ground_stations(config)
    generate_satellite_network_state(config, main_helper, args.threads)
    rd = prepare_run_dir(args)
    run_ns3(rd, args.build)
    summarize(rd)


if __name__ == "__main__":
    main()
