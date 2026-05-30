"""my_experiments 的可复用实验流水线。

每个实验提供自己的 config 模块和 constellation helper。
本模块负责通用流程，这样不同实验可以相互隔离，而不需要重复复制流水线逻辑。
"""

import csv
import importlib
import math
import os
import random
import shutil
import subprocess
import sys
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
                raise ValueError(f"地面站文件中的行格式错误，文件: {path}，内容: {line}")
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


def _generate_uniform_global_ground_stations(config):
    count = config.NUM_GROUND_STATIONS
    seed = getattr(config, "GROUND_STATION_RANDOM_SEED", getattr(config, "TRAFFIC_SEED", 123456789))
    rng = random.Random(seed)
    lon_offset = rng.random() * 360.0
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    stations = []

    for idx in range(count):
        z = 1.0 - 2.0 * ((idx + 0.5) / count)
        latitude = math.degrees(math.asin(z))
        longitude = ((math.degrees(idx * golden_angle) + lon_offset + 180.0) % 360.0) - 180.0
        stations.append({
            "local_gs_id": idx,
            "source_gs_id": idx,
            "name": f"UniformGlobal-{idx:03d}",
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
            "altitude_m": 0.0,
        })

    _write_ground_stations_basic(config.GROUND_STATIONS_FILE, stations)
    return stations


def _generate_uniform_latitude_band_ground_stations(config):
    count = config.NUM_GROUND_STATIONS
    seed = getattr(config, "GROUND_STATION_RANDOM_SEED", getattr(config, "TRAFFIC_SEED", 123456789))
    min_latitude = float(getattr(config, "GROUND_STATION_MIN_LATITUDE", -53.0))
    max_latitude = float(getattr(config, "GROUND_STATION_MAX_LATITUDE", 53.0))
    if min_latitude >= max_latitude:
        raise ValueError("GROUND_STATION_MIN_LATITUDE must be smaller than GROUND_STATION_MAX_LATITUDE")
    if min_latitude < -90.0 or max_latitude > 90.0:
        raise ValueError("Latitude band must stay within [-90, 90] degrees")

    rng = random.Random(seed)
    lon_offset = rng.random() * 360.0
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    z_min = math.sin(math.radians(min_latitude))
    z_max = math.sin(math.radians(max_latitude))
    stations = []

    for idx in range(count):
        z = z_max - (z_max - z_min) * ((idx + 0.5) / count)
        latitude = math.degrees(math.asin(z))
        longitude = ((math.degrees(idx * golden_angle) + lon_offset + 180.0) % 360.0) - 180.0
        stations.append({
            "local_gs_id": idx,
            "source_gs_id": idx,
            "name": f"UniformBand-{idx:04d}",
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
            "altitude_m": 0.0,
        })

    _write_ground_stations_basic(config.GROUND_STATIONS_FILE, stations)
    return stations


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
    rng = random.Random(getattr(config, "GROUND_STATION_RANDOM_SEED", getattr(config, "TRAFFIC_SEED", 123456789)))

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
    satellites = tle_info["satellites"]
    epoch = tle_info["epoch"]
    anchor_time = epoch + anchor_time_ns * u.ns

    stations = []
    for sat_id, satellite in enumerate(satellites):
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

    extra_count = count - num_satellites
    for extra_idx in range(extra_count):
        sat_id = extra_idx % num_satellites
        base = stations[sat_id]
        bearing = rng.random() * 360.0
        distance_km = jitter_km * (0.5 + 0.5 * rng.random())
        latitude, longitude = _offset_lat_lon(
            base["latitude"],
            base["longitude"],
            distance_km,
            bearing,
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


def _select_ground_stations(config):
    selection_mode = getattr(config, "GROUND_STATION_SELECTION_MODE", "copy")

    if selection_mode == "uniform_global":
        return _generate_uniform_global_ground_stations(config)

    if selection_mode == "uniform_latitude_band":
        return _generate_uniform_latitude_band_ground_stations(config)

    if selection_mode == "satellite_anchored":
        return _generate_satellite_anchored_ground_stations(config)

    source_path = config.DEFAULT_GROUND_STATIONS_SOURCE

    if selection_mode == "copy":
        shutil.copyfile(source_path, config.GROUND_STATIONS_FILE)
        stations = read_ground_stations(config.GROUND_STATIONS_FILE)
        for station in stations:
            station["source_gs_id"] = station["local_gs_id"]
        return stations

    if selection_mode != "random_sample":
        raise ValueError(
            "GROUND_STATION_SELECTION_MODE must be 'copy', 'random_sample', "
            "'uniform_global', 'uniform_latitude_band', or 'satellite_anchored'"
        )

    candidates = read_ground_stations(source_path)
    if len(candidates) < config.NUM_GROUND_STATIONS:
        raise ValueError(
            f"候选地面站不足：需要 {config.NUM_GROUND_STATIONS} 个，"
            f"但 {source_path} 只有 {len(candidates)} 个"
        )

    seed = getattr(config, "GROUND_STATION_RANDOM_SEED", getattr(config, "TRAFFIC_SEED", 123456789))
    rng = random.Random(seed)
    selected = rng.sample(candidates, config.NUM_GROUND_STATIONS)
    selected.sort(key=lambda station: station["local_gs_id"])

    stations = []
    for new_id, station in enumerate(selected):
        stations.append({
            "local_gs_id": new_id,
            "source_gs_id": station["local_gs_id"],
            "name": station["name"],
            "latitude": station["latitude"],
            "longitude": station["longitude"],
            "altitude_m": station["altitude_m"],
        })

    _write_ground_stations_basic(config.GROUND_STATIONS_FILE, stations)
    return stations


def define_ground_stations(config):
    config.INPUT_DIR.mkdir(parents=True, exist_ok=True)

    stations = _select_ground_stations(config)
    if len(stations) != config.NUM_GROUND_STATIONS:
        raise ValueError(
            f"地面站数量不匹配：期望 {config.NUM_GROUND_STATIONS} 个，实际得到 {len(stations)} 个"
        )

    with open(config.GROUND_STATIONS_MANIFEST, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["local_gs_id", "source_gs_id", "name", "latitude", "longitude", "altitude_m"],
        )
        writer.writeheader()
        writer.writerows(stations)

    print(f"已定义 {len(stations)} 个地面站")
    print(f"地面站输入文件: {config.GROUND_STATIONS_FILE}")
    print(f"地面站可读清单文件: {config.GROUND_STATIONS_MANIFEST}")


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
    flow_details_file = getattr(config, "TRAFFIC_FLOW_DETAILS_FILE", None)
    if flow_details_file is not None:
        write_flow_pair_details_csv(flow_details_file, config, flows)

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
        if flow_details_file is not None:
            f.write(f"traffic_flow_details={flow_details_file.name}\n")

    print(f"已生成 {len(flows)} 条 TCP 流")
    print(f"总流量: {summary['total_size_byte']} 字节")
    print(f"流量调度文件: {config.TRAFFIC_SCHEDULE_FILE}")
    print(f"流量矩阵文件: {config.TRAFFIC_MATRIX_FILE}")
    print(f"地面站活跃度文件: {config.TRAFFIC_ACTIVITY_FILE}")
    if flow_details_file is not None:
        print(f"流量 OD 明细文件: {flow_details_file}")
    print(f"流量设计摘要文件: {config.TRAFFIC_DESIGN_FILE}")


def generate_satellite_network_state(config, constellation_helper, threads):
    if not config.GROUND_STATIONS_FILE.exists():
        raise FileNotFoundError(
            f"地面站文件缺失: {config.GROUND_STATIONS_FILE}\n"
            "请先运行地面站定义步骤。"
        )

    isl_shift = getattr(config, "ISL_SHIFT", getattr(config, "IRIDIUM_ISL_SHIFT", None))

    constellation_helper.calculate(
        str(config.GEN_DATA_ROOT),
        config.DURATION_S,
        config.TIME_STEP_MS,
        config.ISL_MODE,
        config.GS_SELECTION,
        config.ROUTING_ALGORITHM,
        threads,
        ground_stations_basic_file=config.GROUND_STATIONS_FILE,
        isl_shift=isl_shift,
    )

    print(f"已生成卫星网络状态目录: {config.generated_satellite_network_dir()}")


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
    satellite_path_tracking = "true" if getattr(config, "ENABLE_SATELLITE_PATH_TRACKING", False) else "false"
    satellite_path_interval_ns = getattr(
        config,
        "SATELLITE_PATH_TRACKING_INTERVAL_NS",
        getattr(config, "ISL_UTILIZATION_TRACKING_INTERVAL_NS", 1_000_000_000),
    )
    if getattr(config, "ENABLE_TCP_FLOW_LOGGING", True):
        enabled_flow_ids = getattr(config, "TCP_FLOW_LOGGING_FLOW_IDS", flow_ids)
    else:
        enabled_flow_ids = []
    flow_id_set = "set(" + ",".join(str(flow_id) for flow_id in enabled_flow_ids) + ")"

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
        f"enable_satellite_path_tracking={satellite_path_tracking}",
        f"satellite_path_tracking_interval_ns={satellite_path_interval_ns}",
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
            f"卫星网络状态目录缺失: {config.generated_satellite_network_dir()}\n"
            "请先运行卫星网络状态生成步骤。"
        )
    if not config.TRAFFIC_SCHEDULE_FILE.exists():
        raise FileNotFoundError(
            f"流量调度文件缺失: {config.TRAFFIC_SCHEDULE_FILE}\n"
            "请先运行流量设计步骤。"
        )

    rd = config.run_dir()
    if rd.exists():
        shutil.rmtree(rd)
    rd.mkdir(parents=True)
    (rd / "logs_ns3").mkdir()

    shutil.copyfile(config.TRAFFIC_SCHEDULE_FILE, rd / "schedule.csv")

    # 将 ns-3 运行时需要读取的拓扑文件复制到 runs/main 目录。
    # 这样 main_satnet 使用 --run_dir=runs/main 启动时，可以直接找到这些文件。
    satellite_network_dir = config.generated_satellite_network_dir()
    required_files = [
        "tles.txt",
        "isls.txt",
        "gsl_interfaces_info.txt",
    ]

    for filename in required_files:
        src = satellite_network_dir / filename
        dst = rd / filename
        if src.exists():
            shutil.copyfile(src, dst)
        else:
            raise FileNotFoundError(
                f"ns-3 所需文件缺失: {src}\n"
                f"无法生成完整运行目录: {rd}"
            )

    optional_files = [
        "description.txt",
    ]

    for filename in optional_files:
        src = satellite_network_dir / filename
        dst = rd / filename
        if src.exists():
            shutil.copyfile(src, dst)

    _write_ns3_config(
        config,
        rd / "config_ns3.properties",
        _flow_ids_from_schedule(config.TRAFFIC_SCHEDULE_FILE),
    )

    print(f"已生成 ns-3 运行目录: {rd}")
    print(f"配置文件: {rd / 'config_ns3.properties'}")
    print(f"流量调度文件: {rd / 'schedule.csv'}")
    print(f"已复制卫星 TLE 文件: {rd / 'tles.txt'}")
    print(f"已复制星间链路文件: {rd / 'isls.txt'}")
    print(f"已复制 GSL 接口文件: {rd / 'gsl_interfaces_info.txt'}")


def run_ns3(config, build=False):
    rd = config.run_dir().resolve()
    if not (rd / "config_ns3.properties").exists():
        raise FileNotFoundError(
            f"ns-3 运行目录尚未准备好: {rd}\n"
            "请先运行 ns-3 运行目录生成步骤。"
        )

    ns3_root = config.HYPATIA_DIR / "ns3-sat-sim"
    simulator_dir = ns3_root / "simulator"

    if build:
        print("正在编译 ns-3 仿真程序...")
        subprocess.run(["bash", "build.sh", "--optimized"], cwd=ns3_root, check=True)
        print("ns-3 仿真程序编译完成")

    console_log = rd / "logs_ns3" / "console.txt"
    console_log.parent.mkdir(parents=True, exist_ok=True)
    command = ["./waf", "--run", f"main_satnet --run_dir={rd}"]

    print("正在运行 ns-3 仿真...")
    print(f"运行目录: {rd}")
    print(f"控制台日志将写入: {console_log}")

    with open(console_log, "w", encoding="utf-8") as log_file:
        subprocess.run(
            command,
            cwd=simulator_dir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=True,
        )

    print(f"ns-3 仿真完成: {rd}")
    print(f"控制台日志: {console_log}")


def run_pipeline(config, constellation_helper, threads=4, build=False):
    define_ground_stations(config)
    design_traffic(config)
    generate_satellite_network_state(config, constellation_helper, threads)
    generate_ns3_run(config)
    run_ns3(config, build=build)
