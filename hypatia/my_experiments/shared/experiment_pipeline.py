"""my_experiments 的可复用实验流水线。

每个实验提供自己的 config 模块和 constellation helper。
本模块负责通用流程，这样不同实验可以相互隔离，而不需要重复复制流水线逻辑。
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
                raise ValueError(f"地面站文件中的行格式错误，文件: {path}，内容: {line}")
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
            f"地面站数量不匹配：期望 {config.NUM_GROUND_STATIONS} 个，实际得到 {len(stations)} 个"
        )

    with open(config.GROUND_STATIONS_MANIFEST, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["local_gs_id", "name", "latitude", "longitude", "altitude_m"],
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

    print(f"已生成 {len(flows)} 条 TCP 流")
    print(f"总流量: {summary['total_size_byte']} 字节")
    print(f"流量调度文件: {config.TRAFFIC_SCHEDULE_FILE}")
    print(f"流量矩阵文件: {config.TRAFFIC_MATRIX_FILE}")
    print(f"地面站活跃度文件: {config.TRAFFIC_ACTIVITY_FILE}")
    print(f"流量设计摘要文件: {config.TRAFFIC_DESIGN_FILE}")


def generate_satellite_network_state(config, constellation_helper, threads):
    if not config.GROUND_STATIONS_FILE.exists():
        raise FileNotFoundError(
            f"地面站文件缺失: {config.GROUND_STATIONS_FILE}\n"
            "请先运行地面站定义步骤。"
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
