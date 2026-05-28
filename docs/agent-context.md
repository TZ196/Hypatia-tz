# Agent 上下文：Hypatia 仿真项目速览

> 供 AI Agent 快速理解项目结构、关键路径和运行方式。

---

## 项目定位

**LEO 卫星网络仿真框架**，将天体动力学计算与 ns-3 网络仿真结合，评估卫星互联网的端到端网络性能。

---

## 目录结构（关键路径）

```
hypatia/
├── satgenpy/satgen/                # Python 星座生成库
│   ├── tles/                       #   TLE 轨道参数生成
│   ├── ground_stations/            #   地面站定义
│   ├── isls/                       #   星间链路拓扑
│   ├── dynamic_state/              #   动态路由状态（4 种算法）
│   └── post_analysis/              #   后分析（RTT/路径）
│
├── ns3-sat-sim/simulator/          # ns-3 包级仿真
│   ├── build.sh                    #   编译入口
│   ├── contrib/satellite-network/  #   卫星网络模块
│   └── scratch/main_satnet/        #   仿真主程序
│
├── paper/satellite_networks_state/ # 实验脚本（星座生成入口）
├── satviz/                         # Cesium 3D 可视化
├── integration_tests/              # 端到端集成测试
├── my_experiments/                 # 你的自定义实验目录
│   ├── constellation/              #   星座实验脚本 + 生成数据
│   └── input_data/                 #   地面站输入数据
│
└── venv/                           # Python 3.10.12 虚拟环境
```

---

## 环境激活（每次终端必须执行）

```bash
cd /home/xuke/tz-Hypatia/hypatia
conda deactivate 2>/dev/null
unset CONDA_PREFIX VIRTUAL_ENV
export PATH="/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin"
source venv/bin/activate
export CC=gcc-9 CXX=g++-9
```

> 系统默认 gcc/g++ 已是 9.5.0。Conda 会劫持 PATH，必须先 deactivate。

---

## 仿真流水线（4 步）

```
步骤1: satgenpy 生成星座状态 → gen_data/<name>/
步骤2: 生成 ns-3 运行配置   → <run_dir>/
步骤3: 运行 ns-3 仿真       → <run_dir>/logs_ns3/
步骤4: 后分析/可视化
```

### 步骤 1：生成星座状态

```bash
cd paper/satellite_networks_state
python main_kuiper_630.py 200 100 isls_plus_grid \
  ground_stations_top_100 algorithm_free_one_only_over_isls 4
```

**6 个参数**：`duration_s` `time_step_ms` `isl_selection` `gs_selection` `algorithm` `num_threads`

输出到 `gen_data/<BASE_NAME>_<isl>_<gs>_<algorithm>/`：

| 文件 | 内容 |
|------|------|
| `tles.txt` | 卫星轨道参数 |
| `ground_stations.txt` | 地面站 3D 坐标 |
| `isls.txt` | 星间链路邻接表 |
| `gsl_interfaces_info.txt` | GSL 接口数/带宽 |
| `dynamic_state_<t_ms>/` | 转发表 + GSL 带宽（按时间步） |

### 步骤 3：运行 ns-3

```bash
cd ns3-sat-sim/simulator
./waf --run="main_satnet --run_dir='<运行目录路径>'" 2>&1 | tee console.log
```

> 程序名是 `main_satnet`，不是 `sat-sim`。路径相对 `simulator/`。

---

## 内置星座

| 星座 | 轨道壳 | 主卫星数 | 脚本示例 |
|------|--------|---------|---------|
| Starlink | 540/550km | 1,584 | `main_starlink_550.py` |
| Kuiper | 590/610/630km | 1,156 | `main_kuiper_630.py` |
| OneWeb | 1200km 极轨 | 588 | `main_oneweb_1200_polar.py` |
| Iridium NEXT | 780km 极轨 | 66 | `main_iridium_780.py` |
| Telesat | 1015/1325km | 351 | `main_telesat_1015.py` |

---

## 4 种路由算法

| 算法名（简称关键词） | 走 ISL？ | 每卫星 GSL 接口 | 特点 |
|---------------------|---------|----------------|------|
| `algorithm_free_one_only_over_isls` | ✅ | 1 | 自由配对，经 ISL 路由 |
| `algorithm_free_one_only_gs_relays` | ❌ | 1 | 纯地面站弯管中继 |
| `algorithm_free_gs_one_sat_many_only_over_isls` | ✅ | =地面站数 | 多接口自由配对 |
| `algorithm_paired_many_only_over_isls` | ✅ | =地面站数 | 固定配对最近卫星 |

---

## ISL 模式

| 参数值 | 含义 |
|--------|------|
| `isls_plus_grid` | +Grid 网格拓扑：每卫星连 4 邻居（同轨前后 + 邻轨左右） |
| `isls_none` | 无 ISL，卫星间必须通过地面站中继 |

---

## 你的实验目录

- **实验脚本**：`hypatia/my_experiments/constellation/main_*.py`
- **输入数据**：`hypatia/my_experiments/input_data/`
- **生成数据**：`hypatia/my_experiments/constellation/gen_data/`
- **已添加的新地面站**：`ground_stations_iridium_6_gateways.basic.txt`

---

## 已安装的关键依赖

| 类别 | 内容 |
|------|------|
| 编译器 | gcc-9.5 / g++-9.5（系统默认） |
| Python | venv @ Python 3.10.12 |
| Python 包 | numpy, astropy, ephem, networkx, sgp4, geopy, matplotlib, cartopy, exputilpy, networkload |
| 系统库 | boost, sqlite3, xml2, proj, geos, openmpi, gnuplot, lcov |
| GPU | RTX 4090, CUDA 12.1/12.8（Hypatia 不依赖） |

---

## 安全红线

- 不修改 `/usr/bin/python3` 或 `/usr/bin/gcc` 的 symlink
- 不使用 `update-alternatives` 切换默认编译器
- 不将 venv 路径写入 `~/.bashrc`
- 不使用 `sudo pip install`
- Conda base 必须在编译/运行前 deactivate
