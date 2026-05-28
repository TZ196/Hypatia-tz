"""
Telesat Lightspeed Final Constellation — 极轨壳

轨道参数来源：FCC SAT-MPL-20200526-00053; Table A.2-1; ISED/ITU: CANSAT-LEO
    https://fcc.report/IBFS/SAT-MPL-20200526-00053/2378318.pdf

高度 1015 km, 倾角 98.98°, 27 轨道面 × 13 星/面, 共 351 颗卫星
RAAN 间隔 = 180°/27 ≈ 6.67°, 最低仰角 10°
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

BASE_NAME = "telesat_1015"
NICE_NAME = "Telesat-1015"
DEFAULT_GENERATED_DATA_DIR = Path(__file__).resolve().parents[2] / "experiments" / BASE_NAME / "gen_data"

ECCENTRICITY = 0.0000001        # 近圆轨道（pyephem 不允许正圆，取极小值）
ARG_OF_PERIGEE_DEGREE = 0.0      # 近地点辐角
PHASE_DIFF = True                # 启用 Walker 星座相位差

# 轨道参数 [1]
MEAN_MOTION_REV_PER_DAY = 13.66  # 平均运动 (圈/天) — 高度 ~1015 km
ALTITUDE_M = 1015000             # 轨道高度 (m)

# 最低仰角 10°（Telesat FCC 申请值）
SATELLITE_CONE_RADIUS_M = ALTITUDE_M / math.tan(math.radians(10.0))
MAX_GSL_LENGTH_M = math.sqrt(math.pow(SATELLITE_CONE_RADIUS_M, 2) + math.pow(ALTITUDE_M, 2))

# ISL 不可低于 80 km 高度，避免大气衰减
MAX_ISL_LENGTH_M = 2 * math.sqrt(
    math.pow(EARTH_RADIUS + ALTITUDE_M, 2) - math.pow(EARTH_RADIUS + 80000, 2)
)

NUM_ORBS = 27                    # 轨道面数
NUM_SATS_PER_ORB = 13            # 每面卫星数
INCLINATION_DEGREE = 98.98       # 倾角 (°) — 极轨

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
    """命令行入口: python main_telesat_1015.py <时长s> <步长ms> <ISL模式> <地面站> <路由算法> <线程数>"""
    args = sys.argv[1:]
    if len(args) != 6:
        print("必须提供 6 个参数")
        print("用法: python main_telesat_1015.py [时长(s)] [步长(ms)] "
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
