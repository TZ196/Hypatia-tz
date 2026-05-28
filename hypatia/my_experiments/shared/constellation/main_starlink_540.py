"""
Starlink SpaceX Phase 1 Gen1 — Shell 2

轨道参数来源：FCC 21-48; SAT-MOD-20200417-00037
    最低仰角 25° 来自 FCC SAT-MOD-20181108-00083

高度 540 km, 倾角 53.2°, 72 轨道面 × 22 星/面, 共 1584 颗卫星
"""
import math
import sys
from pathlib import Path

try:
    from .main_helper import MainHelper
except ImportError:
    from main_helper import MainHelper

# WGS72 椭球体半径; 取自 https://geographiclib.sourceforge.io/html/NET/NETGeographicLib_8h_source.html
EARTH_RADIUS = 6378135.0

# ============================================================
# 星座参数
# ============================================================

BASE_NAME = "starlink_540"
NICE_NAME = "Starlink-540"
DEFAULT_GENERATED_DATA_DIR = Path(__file__).resolve().parents[2] / "experiments" / BASE_NAME / "gen_data"

ECCENTRICITY = 0.0000001        # 近圆轨道（pyephem 不允许正圆，取极小值）
ARG_OF_PERIGEE_DEGREE = 0.0      # 近地点辐角
PHASE_DIFF = True                # 启用 Walker 星座相位差

# 轨道参数 [1]
MEAN_MOTION_REV_PER_DAY = 15.10  # 平均运动 (圈/天) — 高度 ~540 km
ALTITUDE_M = 540000              # 轨道高度 (m)

# 最低仰角 25°（Starlink FCC 申请值）
SATELLITE_CONE_RADIUS_M = ALTITUDE_M / math.tan(math.radians(25.0))
MAX_GSL_LENGTH_M = math.sqrt(math.pow(SATELLITE_CONE_RADIUS_M, 2) + math.pow(ALTITUDE_M, 2))

# ISL 不可低于 80 km 高度，避免大气衰减
MAX_ISL_LENGTH_M = 2 * math.sqrt(
    math.pow(EARTH_RADIUS + ALTITUDE_M, 2) - math.pow(EARTH_RADIUS + 80000, 2)
)

NUM_ORBS = 72                    # 轨道面数
NUM_SATS_PER_ORB = 22            # 每面卫星数
INCLINATION_DEGREE = 53.2        # 倾角 (°)

# ============================================================
# 初始化生成器
# ============================================================

main_helper = MainHelper(
    BASE_NAME,
    NICE_NAME,
    ECCENTRICITY,
    ARG_OF_PERIGEE_DEGREE,
    PHASE_DIFF,
    MEAN_MOTION_REV_PER_DAY,
    ALTITUDE_M,
    MAX_GSL_LENGTH_M,
    MAX_ISL_LENGTH_M,
    NUM_ORBS,
    NUM_SATS_PER_ORB,
    INCLINATION_DEGREE,
)


def main():
    """命令行入口: python main_starlink_540.py <时长s> <步长ms> <ISL模式> <地面站> <路由算法> <线程数>"""
    args = sys.argv[1:]
    if len(args) != 6:
        print("必须提供 6 个参数")
        print("用法: python main_starlink_540.py [时长(s)] [步长(ms)] "
              "[isls_plus_grid / isls_none] "
              "[ground_stations_top_100 / ground_stations_paris_moscow_grid] "
              "[algorithm_free_one_only_over_isls / "
              "algorithm_free_one_only_gs_relays / "
              "algorithm_paired_many_only_over_isls] "
              "[线程数]")
        exit(1)
    else:
        main_helper.calculate(
            str(DEFAULT_GENERATED_DATA_DIR),
            int(args[0]),
            int(args[1]),
            args[2],
            args[3],
            args[4],
            int(args[5]),
        )


if __name__ == "__main__":
    main()
