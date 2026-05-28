# 3. 仿真流水线

完整流程分 4 步，数据流向为：

```
星座参数 ──→ 步骤1: 生成星座状态 ──→ 步骤2: 生成运行配置 ──→ 步骤3: 运行 ns-3 ──→ 步骤4: 分析结果
(TLE/ISL/     (satgenpy)              (模板替换)            (./waf)          (Python 脚本)
 地面站/路由)
```

---

## 步骤 1：生成星座状态（satgenpy）

**目的**：从星座参数生成 ns-3 所需的全部输入文件。

**输出文件**（全部写入 `gen_data/<name>/`）：

| 文件 | 内容 | 生成函数 |
|------|------|---------|
| `tles.txt` | 卫星轨道参数 | `generate_tles_from_scratch_manual()` |
| `ground_stations.txt` | 地面站 3D 坐标 | `extend_ground_stations()` |
| `isls.txt` | 星间链路邻接表 | `generate_plus_grid_isls()` 或 `generate_empty_isls()` |
| `gsl_interfaces_info.txt` | 每节点 GSL 接口数/带宽 | `generate_simple_gsl_interfaces_info()` |
| `description.txt` | 最大 GSL/ISL 距离 | `generate_description()` |
| `dynamic_state_<t_ms>/` | 转发表 + GSL 带宽（按时间步） | `help_dynamic_state()` |

其中 `dynamic_state_<t_ms>/` 是核心输出：
- `fstate_<timestamp_ns>.txt` — 每个时间步的转发表
- `gsl_if_bandwidth_<timestamp_ns>.txt` — GSL 接口带宽

**调用示例**（所有 `main_*.py` 通用）：
```bash
cd paper/satellite_networks_state

# 有 ISL：卫星网络路由 + 100 个全球地面站
python main_kuiper_630.py 200 100 isls_plus_grid \
  ground_stations_top_100 algorithm_free_one_only_over_isls 4

# 无 ISL：纯弯管中继
python main_kuiper_630.py 200 100 isls_none \
  ground_stations_paris_moscow_grid algorithm_free_one_only_gs_relays 4
```

**6 个命令行参数**：

| 位置 | 参数 | 含义 | 可选值 |
|------|------|------|--------|
| 1 | `duration_s` | 仿真时长（秒） | 典型 200 |
| 2 | `time_step_ms` | 时间步长（毫秒） | 典型 100 |
| 3 | `isl_selection` | ISL 模式 | `isls_plus_grid` / `isls_none` |
| 4 | `gs_selection` | 地面站选择 | `ground_stations_top_100` / `ground_stations_paris_moscow_grid` |
| 5 | `algorithm` | 路由算法 | 4 种算法名（见 02-framework-data.md） |
| 6 | `num_threads` | 并行线程数 | 如 4 |

输出目录名自动为：`gen_data/<BASE_NAME>_<isl>_<gs>_<algorithm>/`

---

## 步骤 2：生成 ns-3 运行配置

**目的**：从步骤 1 输出生成 ns-3 运行目录。

每个运行目录包含：

```
<run_dir>/
├── config_ns3.properties    # 仿真参数
├── schedule.csv             # 流量调度
├── tles.txt                 # → 符号链接到步骤1输出
├── ground_stations.txt      # → 符号链接
├── isls.txt                 # → 符号链接
├── gsl_interfaces_info.txt  # → 符号链接
├── description.txt          # → 符号链接
└── dynamic_state_<t_ms>/    # → 符号链接
```

**`config_ns3.properties` 示例**：
```properties
simulation_end_time_ns=200000000000
dynamic_state_update_interval_ns=100000000
isl_data_rate_megabit_per_s=10   # 星间链路数据速率兆比特每秒
gsl_data_rate_megabit_per_s=10   # 地星链路数据速率兆比特每秒
isl_max_queue_size_pkts=100    #星间链路最大队列数据包数
gsl_max_queue_size_pkts=100    #地星链路最大队列数据包数
tcp_socket_type=TcpNewReno   #传输控制协议套接字类型
enable_isl_utilization_tracking=true    #开启星间链路利用率统计
```schedule.csv 中的 size_byte 字段定义了单个 TCP 流的总数据量，结合 start_time_ns 和 duration_ns（在 additional_parameters 中可以通过特定格式指定），可以控制发送速率。

**`schedule.csv` 格式**（每行一个 TCP 流）：
```csv
flow_id,from_node,to_node,start_time_ns,duration_ns,rate,path
0,17,18,0,100000000000,,
```
- `path` 为空 = 动态路由；可指定固定路径如 `17-0-1-2-18`

> 参考实现：`integration_tests/test_manila_dalian_over_kuiper/step_2_generate_runs.py`

---

## 步骤 3：运行 ns-3 仿真

```bash
cd ns3-sat-sim/simulator

./waf --run="main_satnet --run_dir='<运行目录路径>'" 2>&1 | tee console.log
```

**输出**（写入 `<run_dir>/logs_ns3/`）：

| 文件 | 内容 |
|------|------|
| `console.txt` | 控制台日志 |
| `tcp_flow_results.csv` | TCP 吞吐量/延迟 |
| `isl_utilization.csv` | ISL 利用率时间序列 |
| `gsl_if_bandwidth.csv` | GSL 带宽时间序列 |
| `finished.txt` | 完成标记 ("Yes") |

**注意**：
- 确保 `CC=gcc-9 CXX=g++-9`
- 程序名是 `main_satnet`，非 `sat-sim`
- 路径相对基准是 `simulator/` 目录

---

## 步骤 4：后分析

```bash
# TCP 流绘图
python ns3-sat-sim/simulator/contrib/basic-sim/tools/plotting/plot_tcp_flow/plot_tcp_flow.py \
  <logs_ns3_dir> <output_data_dir> <output_pdf_dir> <flow_id> <interval_ns>

# RTT / 路由分析
cd satgenpy
python satgen/post_analysis/main_analyze_time_step_path.py

# Cesium 可视化
cd satviz/scripts
python visualize_path.py
```

---

## 完整示例：Manila → Dalian over Kuiper

集成测试提供了完整的 5 步示例流水线：

```bash
cd /home/xuke/tz-Hypatia/hypatia

# 0. 激活环境（见 01-environment.md）

# 先编译 ns-3（仅首次）
cd ns3-sat-sim && bash build.sh --optimized && cd ..

# 1. 生成星座状态
cd integration_tests/test_manila_dalian_over_kuiper
python step_1_generate_satellite_networks_state.py

# 2. 生成运行配置
python step_2_generate_runs.py

# 3. 运行仿真
python step_3_run.py

# 4. 生成图表
python step_4_generate_plots.py

# 5. 验证结果
python step_5_verify.py
```

该示例使用 Kuiper 约化子集（17 颗卫星 + 2 个地面站），TCP NewReno @ 10 Mbps。
