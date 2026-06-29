"""Generate a human-readable experiment description text for LLM context.

Covers four aspects:
  1. Simulation config (duration, time step, TCP variant, traffic mode, etc.)
  2. Constellation structure (orbital parameters, ISL topology, satellite count)
  3. Routing strategy (algorithm name mapped to a plain-Chinese explanation)
  4. Link capacity (ISL/GSL data rates, queue sizes, bottleneck analysis)

Usage:
    import experiment_config as config
    import sys; sys.path.insert(0, str(config.MY_EXPERIMENTS_DIR))
    from shared.constellation.main_iridium_780_66 import main_helper
    from shared.experiment_desc import write_experiment_description
    write_experiment_description(config, main_helper)
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Mapping tables — translate internal constant strings to natural language
# ---------------------------------------------------------------------------

ROUTING_ALGORITHM_DESCRIPTIONS = {
    "algorithm_free_one_only_over_isls": (
        "自由配对 + 纯ISL路由。每颗卫星配备1个GSL接口，"
        "地面站与当前可视卫星自由配对。"
        "端到端流量完全通过星间链路（ISL）在卫星之间逐跳转发，"
        "不经过地面站弯管中继（GS relay）。"
    ),
    "algorithm_free_one_only_gs_relays": (
        "自由配对 + 纯地面弯管中继。每颗卫星配备1个GSL接口，"
        "地面站与当前可视卫星自由配对。"
        "端到端流量通过地面站之间转发（GS relay），"
        "卫星之间不建立ISL链路，数据经卫星→地面站→卫星的弯管路径传输。"
    ),
    "algorithm_free_gs_one_sat_many_only_over_isls": (
        "自由配对 + 多GSL接口 + 纯ISL路由。每颗卫星配备多个GSL接口"
        "（数量等于地面站总数），任意地面站可连接任意可视卫星。"
        "端到端流量完全通过ISL在卫星之间逐跳转发。"
    ),
    "algorithm_paired_many_only_over_isls": (
        "固定配对 + 多GSL接口 + 纯ISL路由。每颗卫星配备多个GSL接口"
        "（数量等于地面站总数），每个地面站固定配对其最近的卫星。"
        "端到端流量完全通过ISL在卫星之间逐跳转发。"
    ),
}

ISL_MODE_DESCRIPTIONS = {
    "isls_plus_grid": (
        "+Grid网格拓扑。每颗卫星与最多4颗邻居卫星建立ISL链路："
        "同轨道面内前后各1颗（intra-plane），相邻轨道面左右各1颗（inter-plane）。"
        "跨轨道面ISL在高纬度地区可能因超过最大ISL距离而断开。"
    ),
    "isls_none": (
        "无ISL链路。卫星之间不建立星间链路，"
        "所有通信必须经过地面站弯管中继。"
    ),
}

TRAFFIC_PAIR_MODE_DESCRIPTIONS = {
    "satellite_pair_stratified": (
        "分层抽样卫星对。每个源卫星按距离分层（near/mid/far/cross_plane）"
        "选取目标卫星，保证覆盖不同拓扑距离的路径。"
    ),
    "satellite_pair_min_cover": (
        "最小覆盖卫星对。在每个转发状态时间片上贪心选取流集合，"
        "以最少流数覆盖所有出现过的有序卫星路径对。"
    ),
}

TCP_VARIANT_LABELS = {
    "TcpNewReno": "TCP NewReno（基于丢包的拥塞控制，AIMD）",
    "TcpVegas": "TCP Vegas（基于延迟的拥塞控制）",
    "TcpCubic": "TCP Cubic（Linux 默认，高速网络优化）",
    "TcpBbr": "TCP BBR（Google 开发，基于带宽估计）",
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _orbital_period_minutes(mean_motion_rev_per_day: float) -> float:
    """Convert mean motion (revolutions per day) to orbital period in minutes."""
    return 1440.0 / mean_motion_rev_per_day


def _meters_to_km(m: float) -> str:
    """Format metres as kilometres with zero decimal places."""
    return f"{m / 1000:.0f} km"


def _format_bytes(size_bytes: int) -> str:
    """Format a byte count in a human-readable form."""
    if size_bytes >= 1_000_000:
        return f"{size_bytes:,} 字节（{size_bytes / 1_000_000:.0f} MB）"
    if size_bytes >= 1_000:
        return f"{size_bytes:,} 字节（{size_bytes / 1_000:.0f} KB）"
    return f"{size_bytes:,} 字节"


def _get_config_attr(config, name, default=None):
    """Safely read an attribute from config, falling back to default."""
    return getattr(config, name, default)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _describe_simulation_config(config) -> str:
    lines = ["## 一、仿真配置"]

    duration_s = _get_config_attr(config, "DURATION_S")
    time_step_ms = _get_config_attr(config, "TIME_STEP_MS")
    if duration_s is not None:
        lines.append(f"- 仿真时长：{duration_s} 秒")
    if time_step_ms is not None:
        lines.append(
            f"- 时间步长：{time_step_ms} ms"
            f"（每 {time_step_ms} ms 更新一次转发状态和卫星位置）"
        )

    num_sats = _get_config_attr(config, "NUM_SATELLITES")
    num_gs = _get_config_attr(config, "NUM_GROUND_STATIONS")
    gs_mode = _get_config_attr(config, "GROUND_STATION_SELECTION_MODE")
    if num_sats is not None:
        lines.append(f"- 卫星总数：{num_sats} 颗")
    if num_gs is not None:
        gs_detail = ""
        if gs_mode == "satellite_anchored":
            gs_detail = "（卫星锚定模式，每颗卫星锚定地面站）"
        lines.append(f"- 地面站总数：{num_gs} 个{gs_detail}")

    pair_mode = _get_config_attr(config, "TRAFFIC_PAIR_MODE")
    if pair_mode is not None:
        mode_desc = TRAFFIC_PAIR_MODE_DESCRIPTIONS.get(pair_mode, pair_mode)
        lines.append(f"- 流量生成模式：{pair_mode}")
        lines.append(f"  {mode_desc}")

    flow_size = _get_config_attr(config, "TRAFFIC_FLOW_SIZE_BYTES")
    if flow_size is not None:
        lines.append(f"- 每条流数据量：{_format_bytes(flow_size)}")

    tcp = _get_config_attr(config, "TCP_SOCKET_TYPE")
    if tcp is not None:
        tcp_label = TCP_VARIANT_LABELS.get(tcp, tcp)
        lines.append(f"- 传输层协议：{tcp_label}")

    seed = _get_config_attr(config, "TRAFFIC_SEED")
    if seed is not None:
        lines.append(f"- 随机种子：{seed}")

    return "\n".join(lines)


def _describe_constellation(config, main_helper) -> str:
    lines = ["## 二、星座结构"]

    # From constellation helper
    lines.append(f"- 星座名称：{main_helper.NICE_NAME}")
    lines.append(f"- 轨道高度：{_meters_to_km(main_helper.ALTITUDE_M)}")
    lines.append(f"- 轨道面数：{main_helper.NUM_ORBS} 个")
    lines.append(f"- 每面卫星数：{main_helper.NUM_SATS_PER_ORB} 颗")
    total = main_helper.NUM_ORBS * main_helper.NUM_SATS_PER_ORB
    lines.append(f"- 卫星总数：{total} 颗")
    lines.append(f"- 轨道倾角：{main_helper.INCLINATION_DEGREE}°")

    period_min = _orbital_period_minutes(main_helper.MEAN_MOTION_REV_PER_DAY)
    lines.append(
        f"- 轨道周期：约 {period_min:.1f} 分钟"
        f"（{main_helper.MEAN_MOTION_REV_PER_DAY} 圈/天）"
    )

    phase = "是" if main_helper.PHASE_DIFF else "否"
    lines.append(f"- 轨道面间相位差：{phase}（相邻轨道面卫星错开排列）")

    lines.append(f"- 离心率：{main_helper.ECCENTRICITY:.7f}（近圆轨道）")

    # ISL topology from config
    isl_mode = _get_config_attr(config, "ISL_MODE", "isls_plus_grid")
    isl_desc = ISL_MODE_DESCRIPTIONS.get(isl_mode, isl_mode)
    lines.append(f"- ISL 拓扑模式：{isl_mode}")
    lines.append(f"  {isl_desc}")

    lines.append(f"- 最大 ISL 距离：{_meters_to_km(main_helper.MAX_ISL_LENGTH_M)}")
    lines.append(f"- 最大 GSL 距离：{_meters_to_km(main_helper.MAX_GSL_LENGTH_M)}")

    isl_shift = _get_config_attr(config, "ISL_SHIFT")
    if isl_shift is not None:
        lines.append(f"- ISL 偏移（isl_shift）：{isl_shift}")

    return "\n".join(lines)


def _describe_routing(config) -> str:
    lines = ["## 三、路由策略"]

    algo = _get_config_attr(config, "ROUTING_ALGORITHM", "algorithm_free_one_only_over_isls")
    algo_desc = ROUTING_ALGORITHM_DESCRIPTIONS.get(
        algo,
        f"未知路由算法：{algo}",
    )
    lines.append(f"- 路由算法标识：{algo}")
    lines.append(f"- 策略说明：{algo_desc}")

    # GSL interfaces per satellite (depends on algorithm)
    if algo in ("algorithm_free_one_only_over_isls", "algorithm_free_one_only_gs_relays"):
        lines.append("- 每卫星 GSL 接口数：1 个")
    elif algo in ("algorithm_free_gs_one_sat_many_only_over_isls", "algorithm_paired_many_only_over_isls"):
        num_gs = _get_config_attr(config, "NUM_GROUND_STATIONS", "?")
        lines.append(f"- 每卫星 GSL 接口数：{num_gs} 个（等于地面站总数）")

    return "\n".join(lines)


def _describe_link_capacity(config) -> str:
    lines = ["## 四、链路容量"]

    isl_rate = _get_config_attr(config, "ISL_DATA_RATE_MBIT_PER_S")
    gsl_rate = _get_config_attr(config, "GSL_DATA_RATE_MBIT_PER_S")
    queue_pkts = _get_config_attr(config, "QUEUE_SIZE_PKTS")

    if isl_rate is not None:
        lines.append(f"- ISL 星间链路速率：{isl_rate} Mbit/s")
    if gsl_rate is not None:
        lines.append(f"- GSL 星地链路速率：{gsl_rate} Mbit/s")
    if queue_pkts is not None:
        lines.append(f"- 每端口队列容量：{queue_pkts} 包")

    # Bottleneck analysis
    if isl_rate is not None and gsl_rate is not None and isl_rate > 0:
        ratio = isl_rate / gsl_rate
        if ratio >= 2:
            lines.append(
                f"- 瓶颈分析：GSL 链路速率仅为 ISL 的 1/{ratio:.0f}"
                f"（{gsl_rate} vs {isl_rate} Mbit/s），"
                f"是端到端路径的主要瓶颈。"
            )
        else:
            lines.append(
                f"- 瓶颈分析：ISL 与 GSL 速率接近"
                f"（{isl_rate} vs {gsl_rate} Mbit/s），"
                f"无明显单一瓶颈。"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_experiment_description(config, main_helper) -> str:
    """Return a complete Chinese experiment description covering four aspects.

    Args:
        config: An experiment_config module with the standard attributes
                (DURATION_S, TIME_STEP_MS, NUM_SATELLITES, ISL_MODE,
                 ROUTING_ALGORITHM, ISL_DATA_RATE_MBIT_PER_S, etc.).
        main_helper: A MainHelper instance from the constellation module
                     (exposes NICE_NAME, ALTITUDE_M, NUM_ORBS,
                      NUM_SATS_PER_ORB, INCLINATION_DEGREE, etc.).

    Returns:
        A plain-text string suitable for LLM context windows.
    """
    experiment_name = _get_config_attr(config, "EXPERIMENT_NAME", "unknown")

    parts = [
        f"# 实验描述 — {experiment_name}",
        "",
        _describe_simulation_config(config),
        "",
        _describe_constellation(config, main_helper),
        "",
        _describe_routing(config),
        "",
        _describe_link_capacity(config),
        "",
        "---",
        f"*此文档由 `experiment_desc.py` 自动生成，供 LLM 作为外生上下文使用。*",
    ]
    return "\n".join(parts)


def write_experiment_description(config, main_helper, output_path=None) -> Path:
    """Generate and write the experiment description to a file.

    Args:
        config: experiment_config module.
        main_helper: MainHelper instance from constellation module.
        output_path: Optional output path. Defaults to
                     EXPERIMENT_DIR / "experiment_description.txt".

    Returns:
        Path to the written file.
    """
    text = generate_experiment_description(config, main_helper)

    if output_path is None:
        output_path = config.EXPERIMENT_DIR / "experiment_description.md"

    output_path = Path(output_path)
    output_path.write_text(text, encoding="utf-8")
    print(f"Experiment description written to {output_path}")
    return output_path
