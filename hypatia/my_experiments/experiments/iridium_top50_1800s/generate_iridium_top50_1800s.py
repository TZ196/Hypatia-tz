"""
生成 Iridium 星座（66卫星）+ 前50个地面站 + 1800秒动态状态数据，
并为这50个地面站生成低秩流量矩阵 + ns-3 配置。

用法:
  # Step 1: 生成星座状态（耗时 ~15-30分钟，取决于线程数）
    python generate_iridium_top50_1800s.py --step 1 --threads 4

  # Step 2: 生成ns-3配置和流量矩阵（快速，<1分钟）
    python generate_iridium_top50_1800s.py --step 2

  # Step 3-4: 编译和运行ns-3仿真（耗时取决于系统，可能1-3小时）
    python generate_iridium_top50_1800s.py --step 3
    python generate_iridium_top50_1800s.py --step 4

  # 全部执行（不推荐，因为太耗时）
    python generate_iridium_top50_1800s.py --all --threads 4
"""

import sys
import os
import argparse
import shutil
import subprocess
from pathlib import Path
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
EXPERIMENTS_DIR = SCRIPT_DIR.parent
MY_EXPERIMENTS_DIR = EXPERIMENTS_DIR.parent
HYPATIA_DIR = MY_EXPERIMENTS_DIR.parent

# 让实验脚本能够导入共享模块
if str(MY_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(MY_EXPERIMENTS_DIR))

from shared.constellation.main_iridium_780 import main_helper
from shared.traffic.matrix_generator import generate_od_matrix

# ============================================================
# 配置
# ============================================================

DURATION_S = 1800         # 仿真时长 1800 秒
TIME_STEP_MS = 1000       # 时间步长 1000ms
ISL_MODE = "isls_plus_grid"
GS_SELECTION = "ground_stations_top_50"
ROUTING_ALGO = "algorithm_free_one_only_over_isls"

# 流量矩阵参数
NUM_GS = 50
GS_START_ID = 66          # Iridium 有 66 颗卫星
MATRIX_RANK = 5
MATRIX_DENSITY = 0.3
MATRIX_SEED = 123456789
FLOW_SIZE_UNIT = 1_000_000_000  # 1 GB
POISSON_LAMBDA = 1.0            # 流到达率 (flows/s)

# ============================================================
# 辅助函数
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Generate Iridium simulation")
    parser.add_argument("--step", type=int, default=None, help="执行特定步骤 (1-4)")
    parser.add_argument("--all", action="store_true", help="执行全部步骤")
    parser.add_argument("--threads", type=int, default=4, help="并行线程数（仅Step 1）")
    parser.add_argument("--detach", action="store_true",
                        help="后台运行Step 4（断线后继续执行）")
    return parser.parse_args()

def print_step(step_num, title):
    print("\n" + "=" * 60)
    print(f"Step {step_num}: {title}")
    print("=" * 60)

def get_gen_dir():
    return str(SCRIPT_DIR / "gen_data" / (
        f"iridium_780_{ISL_MODE}_{GS_SELECTION}_{ROUTING_ALGO}"
    ))

def get_gen_root():
    return str(SCRIPT_DIR / "gen_data")

def get_runs_dir():
    return str(SCRIPT_DIR / "runs")

def get_logs_dir():
    return str(SCRIPT_DIR / "logs")

def generate_poisson_start_times(num_flows: int, duration_s: int, rate: float, seed: int) -> list[int]:
    if rate <= 0:
        raise ValueError("到达率必须 > 0")
    rng = np.random.default_rng(seed)
    inter_arrivals = rng.exponential(1.0 / rate, size=num_flows)
    arrival_times = np.cumsum(inter_arrivals)
    if arrival_times[-1] > duration_s:
        scale = duration_s / arrival_times[-1]
        arrival_times = arrival_times * scale
    return [int(t * 1e9) for t in arrival_times]

# ============================================================
# Step 1: 生成星座状态 (~15-30分钟)
# ============================================================

def step_1_generate_constellation(num_threads):
    print_step(1, "生成 Iridium 星座动态状态数据")
    print(f"  地面站: 前 {NUM_GS} 个 (IDs {GS_START_ID}-{GS_START_ID+NUM_GS-1})")
    print(f"  时长: {DURATION_S}s, 步长: {TIME_STEP_MS}ms")
    print(f"  线程数: {num_threads}")
    print(f"  预计耗时: 15-30 分钟")
    print(f"\n⏳ 正在生成星座状态...")

    main_helper.calculate(
        get_gen_root(),
        DURATION_S,
        TIME_STEP_MS,
        ISL_MODE,
        GS_SELECTION,
        ROUTING_ALGO,
        num_threads,
    )

    # 输出生成结果摘要
    gen_dir = get_gen_dir()
    print("\n✓ 生成的文件:")
    for f in sorted(os.listdir(gen_dir)):
        fpath = os.path.join(gen_dir, f)
        if os.path.isfile(fpath):
            size_mb = os.path.getsize(fpath) / (1024 * 1024)
            print(f"  {f:45s} {size_mb:8.2f} MB")
        elif os.path.isdir(fpath):
            file_count = len(os.listdir(fpath))
            print(f"  {f:45s} ({file_count} files)")

    # 统计地面站数量
    gs_path = os.path.join(gen_dir, "ground_stations.txt")
    with open(gs_path) as f:
        gs_count = sum(1 for _ in f)
    print(f"\n✓ 地面站数量: {gs_count}")
    print("✓ Step 1 完成！")

# ============================================================
# Step 2: 生成流量矩阵和 ns-3 配置 (~1分钟)
# ============================================================

def step_2_generate_config():
    print_step(2, "生成流量矩阵和 ns-3 配置")

    gen_dir = get_gen_dir()
    if not os.path.exists(gen_dir):
        print(f"✗ 错误: 星座目录不存在: {gen_dir}")
        print("   请先运行: python generate_iridium_top50_1800s.py --step 1")
        sys.exit(1)

    # ============================================================
    # Step 2a: 生成流量矩阵
    # ============================================================

    print(f"\n[2a] 生成低秩流量矩阵...")
    print(f"  地面站数: {NUM_GS}, 秩: {MATRIX_RANK}, 密度: {MATRIX_DENSITY}")
    print(f"  起始 ID: {GS_START_ID}, 种子: {MATRIX_SEED}")

    local_pairs, base_sizes, T_clean = generate_od_matrix(
        n=NUM_GS,
        rank=MATRIX_RANK,
        density=MATRIX_DENSITY,
        seed=MATRIX_SEED,
    )

    # 映射到实际节点 ID 并放缩
    list_from_to = []
    list_flow_sizes = []
    for (local_from, local_to), base_size in zip(local_pairs, base_sizes):
        actual_from = local_from + GS_START_ID
        actual_to = local_to + GS_START_ID
        flow_size = base_size * FLOW_SIZE_UNIT
        list_from_to.append((actual_from, actual_to))
        list_flow_sizes.append(flow_size)
    # 计算流数量并生成泊松到达时间（ns）
    num_flows = len(list_from_to)
    list_start_times = generate_poisson_start_times(
        num_flows,
        DURATION_S,
        POISSON_LAMBDA,
        MATRIX_SEED,
    )
    print(f"  ✓ 生成了 {num_flows} 条流")

    # 保存 schedule.csv
    schedule_path = os.path.join(gen_dir, "schedule.csv")
    try:
        import networkload
        networkload.write_schedule(
            schedule_path,
            num_flows,
            list_from_to,
            list_flow_sizes,
            list_start_times,
        )
        print(f"  ✓ 流量矩阵已写入: {schedule_path}")
    except ImportError:
        # 如果 networkload 未安装，手动写入（无表头，7列）
        with open(schedule_path, "w") as f:
            for idx, ((frm, to), sz, st) in enumerate(zip(list_from_to, list_flow_sizes, list_start_times)):
                f.write(f"{idx},{frm},{to},{sz},{st},,\n")
        print(f"  ✓ 流量矩阵已写入 (手动CSV, 7列): {schedule_path}")

    # 保存 ground truth 矩阵
    gt_path = os.path.join(gen_dir, "traffic_matrix_ground_truth.npy")
    np.save(gt_path, T_clean)
    print(f"  ✓ Ground truth 矩阵已保存: {gt_path}")

    # ============================================================
    # Step 2b: 生成 ns-3 运行配置
    # ============================================================

    print(f"\n[2b] 生成 ns-3 运行配置...")

    # 创建runs目录
    runs_dir = get_runs_dir()
    if os.path.exists(runs_dir):
        shutil.rmtree(runs_dir)
    os.makedirs(runs_dir, exist_ok=True)

    # 构建星座配置名
    satellite_network = f"iridium_780_{ISL_MODE}_{GS_SELECTION}_{ROUTING_ALGO}"
    dynamic_state_dir = f"dynamic_state_{TIME_STEP_MS}ms_for_{int(DURATION_S)}s"

    # ns-3 配置参数
    NS3_CONFIG = {
        "SIMULATION-END-TIME-NS": str(int(DURATION_S * 1e9)),
        # The template already prepends a gen_data path; keep values relative.
        "SATELLITE-NETWORK": satellite_network,
        "DYNAMIC-STATE": dynamic_state_dir,
        "DYNAMIC-STATE-UPDATE-INTERVAL-NS": str(int(TIME_STEP_MS * 1e6)),
        "ISL-DATA-RATE-MEGABIT-PER-S": "100",
        "GSL-DATA-RATE-MEGABIT-PER-S": "100",
        "ISL-MAX-QUEUE-SIZE-PKTS": "100",
        "GSL-MAX-QUEUE-SIZE-PKTS": "100",
        "ENABLE-ISL-UTILIZATION-TRACKING": "true",
        "ISL-UTILIZATION-TRACKING-INTERVAL-NS-COMPLETE": "isl_utilization_tracking_interval_ns=1000000000",
        # NOTE: scratch/main_satnet/main_satnet.cc prepends "ns3::" itself.
        # This ns3-sat-sim tree does not include TcpCubic; use an available variant.
        "TCP-SOCKET-TYPE": "TcpBic",
    }

    # 复制并生成 config_ns3.properties
    # 尝试多个可能的模板位置（兼容不同目录布局）
    candidate_templates = [
        str(MY_EXPERIMENTS_DIR / "templates" / "template_tcp_a_b_config_ns3.properties"),
        str(HYPATIA_DIR / "integration_tests" / "test_manila_dalian_over_kuiper" / "templates" / "template_tcp_a_b_config_ns3.properties"),
        str(HYPATIA_DIR / "paper" / "ns3_experiments" / "a_b" / "templates" / "template_tcp_a_b_config_ns3.properties"),
    ]
    template_config = None
    for c in candidate_templates:
        if os.path.exists(c):
            template_config = c
            break
    if template_config is None:
        print("✗ 错误: 找不到模板文件 template_tcp_a_b_config_ns3.properties")
        print("   尝试的路径:")
        for c in candidate_templates:
            print(f"     - {c}")
        sys.exit(1)
    config_path = os.path.join(runs_dir, "config_ns3.properties")

    with open(template_config, "r") as f:
        config_content = f.read()

    for key, value in NS3_CONFIG.items():
        if key == "TCP-SOCKET-TYPE" and value.startswith("ns3::"):
            value = value[len("ns3::"):]
        config_content = config_content.replace(f"[{key}]", value)

    # Our run_dir is runs/, so gen_data is one level up (../gen_data).
    config_content = config_content.replace("../../gen_data/", "../gen_data/")

    flow_id_set = "set(" + ",".join(str(i) for i in range(num_flows)) + ")"
    if "tcp_flow_enable_logging_for_tcp_flow_ids" in config_content:
        lines = []
        for line in config_content.splitlines():
            if line.startswith("tcp_flow_enable_logging_for_tcp_flow_ids"):
                lines.append(f"tcp_flow_enable_logging_for_tcp_flow_ids={flow_id_set}")
            else:
                lines.append(line)
        config_content = "\n".join(lines) + "\n"
    else:
        config_content = config_content.rstrip() + f"\ntcp_flow_enable_logging_for_tcp_flow_ids={flow_id_set}\n"

    with open(config_path, "w") as f:
        f.write(config_content)

    print(f"  ✓ 配置文件已生成: {config_path}")

    # 生成 schedule.csv（复制）
    schedule_dest = os.path.join(runs_dir, "schedule.csv")
    shutil.copy(schedule_path, schedule_dest)
    print(f"  ✓ 流量计划已复制: {schedule_dest}")

    # 创建符号链接指向satgenpy输出
    gen_data_abs = os.path.abspath(gen_dir)
    links_needed = {
        "tles.txt": os.path.join(gen_data_abs, "tles.txt"),
        "ground_stations.txt": os.path.join(gen_data_abs, "ground_stations.txt"),
        "isls.txt": os.path.join(gen_data_abs, "isls.txt"),
        "gsl_interfaces_info.txt": os.path.join(gen_data_abs, "gsl_interfaces_info.txt"),
        "description.txt": os.path.join(gen_data_abs, "description.txt"),
        dynamic_state_dir: os.path.join(gen_data_abs, dynamic_state_dir),
    }

    for link_name, target_path in links_needed.items():
        link_path = os.path.join(runs_dir, link_name)
        if os.path.exists(link_path) or os.path.islink(link_path):
            os.remove(link_path)
        try:
            os.symlink(target_path, link_path)
            print(f"  ✓ 符号链接: {link_name}")
        except Exception as e:
            print(f"  ✗ 链接失败: {link_name} ({e})")
            sys.exit(1)

    print("\n✓ Step 2 完成！")

# ============================================================
# Step 3: 编译 ns-3 (~5-10分钟)
# ============================================================

def step_3_build_ns3():
    print_step(3, "编译 ns-3 仿真器")

    ns3_root = str(HYPATIA_DIR / "ns3-sat-sim")
    ns3_sim_dir = os.path.join(ns3_root, "simulator")

    # ns-3.31 (waf) does not provide a top-level './ns3' runner in build/.
    # Treat the presence of the compiled main_satnet binary as “built”.
    candidate_bins = [
        os.path.join(ns3_sim_dir, "build", profile, "scratch", "main_satnet", "main_satnet")
        for profile in ("optimized", "debug_all", "debug_minimal", "optimized_with_tests")
    ]
    if any(os.path.exists(p) for p in candidate_bins):
        print("✓ ns-3 已编译（检测到 main_satnet 产物），跳过编译步骤")
        return

    print("⏳ 正在编译 ns-3（--optimized）...")
    result = subprocess.run(["./build.sh", "--optimized"], cwd=ns3_root)

    if result.returncode != 0:
        print("✗ ns-3 编译失败")
        sys.exit(1)

    print("✓ ns-3 编译完成！")

# ============================================================
# Step 4: 运行 ns-3 仿真 (~1-3小时)
# ============================================================

def step_4_run_ns3(detach: bool):
    print_step(4, "运行 ns-3 仿真")

    runs_dir = get_runs_dir()
    if not os.path.exists(runs_dir):
        print("✗ 错误: runs 目录不存在")
        print("   请先运行: python generate_iridium_top50_1800s.py --step 2")
        sys.exit(1)

    ns3_sim_dir = str(HYPATIA_DIR / "ns3-sat-sim" / "simulator")
    runs_abs = os.path.abspath(runs_dir)

    print(f"⏳ 运行仿真: {runs_abs}")
    print(f"   预计耗时: 1-3 小时")
    print(f"   日志位置: {runs_abs}/data/")

    run_cmd = ["./waf", "--run-no-build", f"main_satnet --run_dir={runs_abs}"]
    if detach:
        os.makedirs(get_logs_dir(), exist_ok=True)
        log_path = os.path.join(get_logs_dir(), "step4.nohup.log")
        with open(log_path, "a") as log_file:
            proc = subprocess.Popen(
                run_cmd,
                cwd=ns3_sim_dir,
                stdout=log_file,
                stderr=log_file,
                preexec_fn=os.setsid,
            )
        print(f"✓ 已后台启动 (PID: {proc.pid})")
        print(f"✓ 日志输出: {log_path}")
        return

    result = subprocess.run(
        run_cmd,
        cwd=ns3_sim_dir,
        timeout=14400  # 4小时超时
    )

    if result.returncode != 0:
        print(f"✗ 仿真失败 (返回码: {result.returncode})")
        sys.exit(1)

    print("✓ 仿真完成！")

    # ============================================================
    # Step 5: 输出数据汇总
    # ============================================================

    print_step(5, "仿真输出数据汇总")

    output_dir = os.path.join(runs_abs, "data")
    if os.path.exists(output_dir):
        print(f"\n📊 仿真输出数据:")
        total_size = 0
        for filename in sorted(os.listdir(output_dir)):
            filepath = os.path.join(output_dir, filename)
            if os.path.isfile(filepath):
                size = os.path.getsize(filepath)
                total_size += size
                size_mb = size / (1024 * 1024)
                print(f"  {filename:40s} {size_mb:10.2f} MB")
        print(f"\n  总大小: {total_size / (1024 * 1024):.2f} MB")
    else:
        print(f"⚠ 输出目录不存在: {output_dir}")

    # ISL 利用率数据
    isl_util_dir = os.path.join(runs_abs, "isl_utilization_data")
    if os.path.exists(isl_util_dir):
        print(f"\n🔗 ISL 利用率数据:")
        for filename in sorted(os.listdir(isl_util_dir)):
            filepath = os.path.join(isl_util_dir, filename)
            if os.path.isfile(filepath):
                size = os.path.getsize(filepath)
                print(f"  {filename:40s} {size:15,} bytes")

    print("\n" + "=" * 60)
    print("✓ 全部任务完成！")
    print("=" * 60)

# ============================================================
# Main
# ============================================================

def main():
    args = parse_args()

    if args.all:
        print("🚀 开始全流程（这将耗时 1-4小时）")
        step_1_generate_constellation(args.threads)
        step_2_generate_config()
        step_3_build_ns3()
        step_4_run_ns3(args.detach)
    elif args.step == 1:
        step_1_generate_constellation(args.threads)
    elif args.step == 2:
        step_2_generate_config()
    elif args.step == 3:
        step_3_build_ns3()
    elif args.step == 4:
        step_4_run_ns3(args.detach)
    else:
        print("使用说明:")
        print("  python generate_iridium_top50_1800s.py --step 1 --threads 4  # 生成星座（15-30分钟）")
        print("  python generate_iridium_top50_1800s.py --step 2              # 生成配置（1分钟）")
        print("  python generate_iridium_top50_1800s.py --step 3              # 编译ns-3（5-10分钟）")
        print("  python generate_iridium_top50_1800s.py --step 4              # 运行仿真（1-3小时）")
        print("  python generate_iridium_top50_1800s.py --step 4 --detach      # 断线后继续运行")
        print("  python generate_iridium_top50_1800s.py --all --threads 4    # 全部执行")

if __name__ == "__main__":
    main()
