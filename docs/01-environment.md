# 1. 环境信息与激活

## 系统环境

| 项目 | 详情 |
|------|------|
| 项目根目录 | `/home/xuke/tz-Hypatia/hypatia/` |
| Python 虚拟环境 | `hypatia/venv/` (Python 3.10.12) |
| 编译器 | gcc-9 / g++-9 (系统默认即 9.5.0) |
| GPU | RTX 4090, CUDA 12.1/12.8 (Hypatia 不依赖) |

## 激活环境

做任何事前先执行：

```bash
cd /home/xuke/tz-Hypatia/hypatia
conda deactivate 2>/dev/null
unset CONDA_PREFIX VIRTUAL_ENV
export PATH="/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin"
source venv/bin/activate
export CC=gcc-9 CXX=g++-9
```

## 目录总览

```
hypatia/
├── satgenpy/                    # Python：星座生成库
│   └── satgen/
│       ├── tles/                #   TLE 轨道参数生成/读取
│       ├── ground_stations/     #   地面站定义/坐标转换
│       ├── isls/                #   星间链路拓扑生成
│       ├── interfaces/          #   GSL 接口定义
│       ├── description/         #   星座描述（最大距离等）
│       ├── dynamic_state/       #   动态路由状态（4 种算法）
│       ├── distance_tools/      #   距离计算/坐标转换
│       └── post_analysis/       #   后分析（RTT/路径/利用率）
│
├── ns3-sat-sim/                 # ns-3 包级仿真
│   ├── build.sh                 #   编译入口
│   └── simulator/
│       ├── contrib/
│       │   ├── satellite-network/  # 卫星网络模块（激光链路/GSL/转发）
│       │   └── basic-sim/         # 基础仿真工具
│       ├── src/satellite/         # SGP4 卫星位置传播
│       └── scratch/main_satnet/   # 仿真主程序入口
│
├── satviz/                      # Cesium 可视化
├── paper/                       # 论文复现（实验配置+图表）
└── integration_tests/           # 端到端集成测试
    └── test_manila_dalian_over_kuiper/  # 完整 5 步流水线示例
```
