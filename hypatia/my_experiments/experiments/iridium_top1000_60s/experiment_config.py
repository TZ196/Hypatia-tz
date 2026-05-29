"""iridium_top50_60s 实验的配置文件。

这个文件主要负责定义一次实验需要用到的路径、卫星网络参数、
地面站参数、流量生成参数、ns-3 仿真参数等。
"""

from pathlib import Path


# ============================================================
# 1. 实验目录路径配置
# ============================================================

# 当前配置文件所在目录：
# hypatia/my_experiments/experiments/iridium_top50_60s
EXPERIMENT_DIR = Path(__file__).resolve().parent

# 当前实验名称，自动使用目录名：
# iridium_top50_60s
EXPERIMENT_NAME = EXPERIMENT_DIR.name

# experiments 目录：
# hypatia/my_experiments/experiments
EXPERIMENTS_DIR = EXPERIMENT_DIR.parent

# my_experiments 目录：
# hypatia/my_experiments
MY_EXPERIMENTS_DIR = EXPERIMENTS_DIR.parent

# Hypatia 根目录：
# hypatia
HYPATIA_DIR = MY_EXPERIMENTS_DIR.parent


# ============================================================
# 2. 当前实验的输入、输出目录
# ============================================================

# 当前实验的输入目录，用于存放地面站文件、流量调度文件等
INPUT_DIR = EXPERIMENT_DIR / "input"

# 卫星网络状态生成目录
# 包括 tles.txt、isls.txt、转发表 fstate_*.txt 等
GEN_DATA_ROOT = EXPERIMENT_DIR / "gen_data"

# ns-3 运行目录
# 例如 runs/main
RUNS_DIR = EXPERIMENT_DIR / "runs"

# 日志目录，可用于存放实验日志
LOGS_DIR = EXPERIMENT_DIR / "logs"


# ============================================================
# 3. 共享输入数据路径
# ============================================================

# shared/input_data 目录，存放多个实验可共用的输入数据
SHARED_INPUT_DIR = MY_EXPERIMENTS_DIR / "shared" / "input_data"

# 候选地面站文件：当前实验直接使用全球 top1000 城市作为地面站候选/端点
DEFAULT_GROUND_STATIONS_SOURCE = SHARED_INPUT_DIR / "ground_stations_top_1000.basic.txt"

# 地面站选择方式
# copy 表示直接使用 DEFAULT_GROUND_STATIONS_SOURCE 中的 top1000 城市
GROUND_STATION_SELECTION_MODE = "copy"
GROUND_STATION_RANDOM_SEED = 123456789

# 当前实验实际使用的地面站文件
# pipeline 会把 DEFAULT_GROUND_STATIONS_SOURCE 复制到这里
GROUND_STATIONS_FILE = INPUT_DIR / "ground_stations.basic.txt"

# 地面站清单文件，便于阅读和检查地面站信息
GROUND_STATIONS_MANIFEST = INPUT_DIR / "ground_stations_manifest.csv"


# ============================================================
# 4. 流量相关输入/输出文件
# ============================================================

# TCP flow 调度文件
# ns-3 会读取这个文件，按照其中的时间、源、目的、大小启动 TCP 流
TRAFFIC_SCHEDULE_FILE = INPUT_DIR / "schedule.csv"

# 流量设计摘要文件
# 记录本次流量生成的总体参数和统计信息
TRAFFIC_DESIGN_FILE = INPUT_DIR / "traffic_design.txt"

# OD 流量矩阵文件
# 记录地面站到地面站之间的流量大小，单位通常是 byte
TRAFFIC_MATRIX_FILE = INPUT_DIR / "traffic_matrix_bytes.csv"

# 地面站活跃度文件
# 记录每个地面站作为源/目的的活跃程度
TRAFFIC_ACTIVITY_FILE = INPUT_DIR / "station_activity.csv"

# 每条 flow 的源/目的城市、区域和距离，便于检查 5000 条 OD 的地理分布
TRAFFIC_FLOW_DETAILS_FILE = INPUT_DIR / "traffic_flow_details.csv"


# ============================================================
# 5. 卫星网络基础配置
# ============================================================

# 使用的卫星网络名称
# 这里表示 Iridium 780 km 高度星座配置
SATELLITE_NETWORK = "iridium_780"

# 仿真持续时间，单位：秒
DURATION_S = 60

# 动态状态更新时间步长，单位：毫秒
# 1000 表示每 1 秒生成/更新一次转发表和链路状态
TIME_STEP_MS = 1000

# 星间链路模式
# isls_plus_grid 表示使用网格状星间链路
ISL_MODE = "isls_plus_grid"

# 地面站选择模式
# 表示当前实验使用 top1000 城市作为地面站端点
GS_SELECTION = "ground_stations_top1000_dense_5000"

# 路由算法
# algorithm_free_one_only_over_isls 表示只通过星间链路转发，
# 不允许地面站作为中继节点
ROUTING_ALGORITHM = "algorithm_free_one_only_over_isls"


# ============================================================
# 6. 节点数量配置
# ============================================================

# 卫星数量
NUM_SATELLITES = 66

# 地面站数量
NUM_GROUND_STATIONS = 1000

# 地面站节点 ID 的起始编号
# 如果卫星节点编号是 0 ~ 65，
# 那么地面站节点编号就是 66 ~ 115
GS_START_NODE_ID = NUM_SATELLITES


# ============================================================
# 7. 流量生成配置
# ============================================================

# 流量对模式
# long_distance_balanced 表示从 top1000 城市中构造远距离、跨洲、跨半球的有向 OD flow
TRAFFIC_PAIR_MODE = "long_distance_balanced"
TRAFFIC_FLOW_COUNT = 5000
TRAFFIC_MIN_DISTANCE_KM = 6000
TRAFFIC_MAX_FLOWS_PER_CITY_ROLE = 5
TRAFFIC_PREFERRED_REGION_PAIRS = [
    ("Asia", "South America"),
    ("Asia", "Africa"),
    ("North America", "Oceania"),
    ("Europe", "Oceania"),
    ("Africa", "North America"),
    ("South America", "Europe"),
]

# 流量生成随机种子
# 固定种子可以保证每次生成的流量一致，方便复现实验
TRAFFIC_SEED = 123456789

# TCP flow 开始时间，单位：纳秒
# 0 表示从仿真开始时就可以启动流量
TRAFFIC_START_TIME_NS = 0

# 地面站活跃度分布配置
# flat 表示不再按时区活跃度偏置，使 5000 条验证流更均匀
TRAFFIC_ACTIVITY_PROFILE = "flat"

# 参考 UTC 小时
# 用于选择某个时间段的流量活跃度模式
TRAFFIC_REFERENCE_UTC_HOUR = 0

# OD 权重模式
# distance 表示按源/目的城市的大圆距离分配预算，距离越远的 flow 越大
TRAFFIC_OD_WEIGHT_MODE = "distance"
TRAFFIC_DISTANCE_WEIGHT_POWER = 1.0
TRAFFIC_PREFERRED_REGION_WEIGHT = 1.3

# 流量随机扰动强度
# 给 flow 大小加入可复现扰动，避免所有 flow 大小完全相同
TRAFFIC_RANDOMNESS_SIGMA = 0.35

# 容量约束范围
# single_bottleneck 表示用一个参考瓶颈容量控制总流量，避免 5000 条流过大
TRAFFIC_CAPACITY_SCOPE = "single_bottleneck"

# 业务负载比例
# 作为默认预算公式的备用参数；本实验优先使用 TRAFFIC_TARGET_AVG_FLOW_SIZE_BYTES
TRAFFIC_OFFERED_LOAD = 1.2

# 目标平均每条 flow 大小。
# 目的是让大量 flow 在 60s 内持续存在，从而提升路径矩阵覆盖密度。
TRAFFIC_TARGET_AVG_FLOW_SIZE_BYTES = 10_000_000

# 单条 TCP flow 的最小大小，单位：字节
TRAFFIC_MIN_FLOW_SIZE_BYTES = 2_000_000

# 单条 TCP flow 的最大大小，单位：字节
# None 表示不额外限制最大 flow 大小
TRAFFIC_MAX_FLOW_SIZE_BYTES = 30_000_000

# 参考带宽，单位：Mbit/s
# 流量生成时会以这个带宽作为容量参考
TRAFFIC_REFERENCE_BANDWIDTH_MBIT_PER_S = 100

# 本实验只需要卫星路径流量矩阵，不需要生成 tcp_flow_<id>_progress/rtt/cwnd 明细文件
ENABLE_TCP_FLOW_LOGGING = False


# ============================================================
# 8. ns-3 链路与 TCP 配置
# ============================================================

# ISL 和 GSL 的链路数据率，单位：Mbit/s
DATA_RATE_MBIT_PER_S = 100

# 链路队列大小，单位：包
QUEUE_SIZE_PKTS = 100

# ns-3 中使用的 TCP 拥塞控制算法
TCP_SOCKET_TYPE = "TcpNewReno"


# ============================================================
# 9. ISL 利用率统计配置
# ============================================================

# 是否启用星间链路利用率统计
ENABLE_ISL_UTILIZATION_TRACKING = True

# ISL 利用率统计间隔，单位：纳秒
# 1_000_000_000 ns = 1 秒
ISL_UTILIZATION_TRACKING_INTERVAL_NS = 1_000_000_000


# ============================================================
# 10. 卫星路径流量矩阵统计配置
# ============================================================

# 是否启用路径经过关系统计：
# 一条路径 A -> B -> C 会累加 A->B、A->C、B->C。
ENABLE_SATELLITE_PATH_TRACKING = True

# 路径流量矩阵统计时间片，单位：纳秒
# 1_000_000_000 ns = 1 秒；可以改成 10_000_000_000 表示 10 秒。
SATELLITE_PATH_TRACKING_INTERVAL_NS = 1_000_000_000


# ============================================================
# 11. 辅助函数
# ============================================================

def satellite_network_name() -> str:
    """生成当前实验的卫星网络名称。

    这个名称会用于 gen_data 目录下的子目录命名。
    例如：
    iridium_780_isls_plus_grid_ground_stations_experiment_top_50_algorithm_free_one_only_over_isls
    """
    return f"{SATELLITE_NETWORK}_{ISL_MODE}_{GS_SELECTION}_{ROUTING_ALGORITHM}"


def dynamic_state_dir_name() -> str:
    """生成动态状态目录名称。

    例如：
    dynamic_state_1000ms_for_60s

    其中：
    - 1000ms 表示每 1000 毫秒更新一次动态状态；
    - 60s 表示仿真总时长为 60 秒。
    """
    return f"dynamic_state_{TIME_STEP_MS}ms_for_{DURATION_S}s"


def generated_satellite_network_dir() -> Path:
    """返回当前实验生成的卫星网络状态目录。

    该目录中通常包含：
    - tles.txt
    - isls.txt
    - gsl_interfaces_info.txt
    - dynamic_state_1000ms_for_60s/
    """
    return GEN_DATA_ROOT / satellite_network_name()


def run_dir() -> Path:
    """返回 ns-3 的运行目录。

    当前固定返回：
    runs/main

    ns-3 仿真时会从这个目录读取：
    - config_ns3.properties
    - schedule.csv
    - tles.txt
    - isls.txt
    - gsl_interfaces_info.txt
    """
    return RUNS_DIR / "main"
