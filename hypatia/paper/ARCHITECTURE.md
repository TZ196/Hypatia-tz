# Paper 目录架构

论文 *"Exploring the 'Internet from space' with Hypatia"* (Simon Kassing 等, IMC 2020) 的复现实验代码。

---

## 目录总览

```
paper/
├── paper.sh                                 # 一键执行全部实验的入口脚本
├── extract_temp_data.py                     # 解压预计算数据包（跳过长时间计算）
├── package_temp_data.py                     # 打包临时数据供分发
│
├── satellite_networks_state/                # 步骤1：生成星座状态
├── satgenpy_analysis/                       # 步骤3：路由分析
├── ns3_experiments/                         # 步骤4：ns-3 包级仿真
├── figures/                                 # 步骤6：汇总绘图
└── satviz_plots/                            # Cesium 可视化输出（运行时生成）
```

---

## 一、satellite_networks_state/ — 步骤1：生成星座状态

从星座参数生成 ns-3 所需的全部输入文件（TLE、ISL、地面站、转发表）。

| 文件 | 作用 |
|------|------|
| `generate_all_local.sh` | 本地并行调度：将 15 个任务分发给 generate_for_paper.sh |
| `generate_for_paper.sh` | 单一配置生成器，id 0-14 对应不同星座×更新间隔组合 |
| `generate_all_remote.py` | 远程集群版调度器（SSH 分发到多机并行） |
| `main_kuiper_630.py` | Kuiper-630 星座参数（34面×34星） + 入口 |
| `main_starlink_550.py` | Starlink-550 星座参数（72面×22星） + 入口 |
| `main_telesat_1015.py` | Telesat-1015 星座参数（27面×13星） + 入口 |
| `main_25x25.py` | 旧版 25×25 测试星座（论文未使用） |
| `main_helper.py` | 公共生成逻辑：调用 satgenpy 生成 TLE/ISL/GSL/转发表 |
| `input_data/` | 地面站基础数据：top 100/1000 城市、Paris-Moscow 网格 |

### generate_for_paper.sh 的 15 个任务

| id | 星座 | ISL | 地面站 | 更新间隔 |
|----|------|-----|--------|----------|
| 0 | Kuiper-630 | 无 | Paris-Moscow 网格 | 50ms |
| 1 | Kuiper-630 | 无 | Paris-Moscow 网格 | 100ms |
| 2 | Kuiper-630 | 无 | Paris-Moscow 网格 | 1000ms |
| 3 | Kuiper-630 | +Grid | Top 100 城市 | 50ms |
| 4 | Kuiper-630 | +Grid | Top 100 城市 | 100ms |
| 5 | Kuiper-630 | +Grid | Top 100 城市 | 1000ms |
| 6 | Starlink-550 | +Grid | Top 100 城市 | 50ms |
| 7 | Starlink-550 | +Grid | Top 100 城市 | 100ms |
| 8 | Starlink-550 | +Grid | Top 100 城市 | 1000ms |
| 9 | Telesat-1015 | +Grid | Top 100 城市 | 50ms |
| 10 | Telesat-1015 | +Grid | Top 100 城市 | 100ms |
| 11 | Telesat-1015 | +Grid | Top 100 城市 | 1000ms |
| 12-14 | 旧版 25×25 | +Grid | 旧版地面站 | 50/100/1000ms |

---

## 二、satgenpy_analysis/ — 步骤3：路由层面分析

| 文件 | 作用 |
|------|------|
| `perform_full_analysis.py` | 批量分析：6 个城市对 × 路由/图表 + 4 星座配置对比 |

### 分析的城市对

| 星座 | 地面站对 | 分析内容 |
|------|---------|---------|
| Kuiper | Rio de Janeiro → St. Petersburg | 路由路径 + RTT 时序 |
| Kuiper | Manila → Dalian | 路由路径 + RTT 时序 |
| Kuiper | Istanbul → Nairobi | 路由路径 + RTT 时序 |
| Kuiper | Paris → Moscow (ISL) | 路由路径 + 图表 + RTT 时序 |
| Kuiper | Paris → Moscow (GS Relay) | 路由路径 + 图表 + RTT 时序 |
| Kuiper | Chicago → Zhengzhou | 路由路径 + 图表 + RTT 时序 |
| Starlink | Paris → Luanda | 路由路径 + 图表 + RTT 时序 |

### 星座对比

对 4 种星座配置分析路径跳数、RTT、路径变更频率，分别用 50/100/1000ms 更新间隔。

---

## 三、ns3_experiments/ — 步骤4：ns-3 包级仿真

### 3.1 a_b/ — 单 TCP 流端点对通信

4 个城市对 × 2 种 TCP（NewReno + Vegas） + Paris→Moscow 地面弯管中继 + Ping 探测，共 16 个仿真运行。

| 文件 | 作用 |
|------|------|
| `run_list.py` | 定义 8 个 TCP 流 + 8 个 Ping 流配置 |
| `step_1_generate_runs.py` | 模板替换生成 ns-3 运行目录 |
| `step_2_run.py` | 并行启动 ns-3 仿真（最多 4 进程） |
| `step_3_generate_plots.py` | 生成 TCP cwnd/progress/rtt/rate 图表 |
| `templates/` | config_ns3.properties + schedule.csv 模板 |

### 3.2 traffic_matrix/ — 竞争流量下 TCP 表现

Rio → St.Petersburg 在随机排列背景流量矩阵下的吞吐量表现。

| 文件 | 作用 |
|------|------|
| `step_1_generate_runs.py` | 生成随机排列流量矩阵 + 目标流 |
| `step_2_run.py` | 并行仿真 |
| `step_3_generate_plots.py` | 分析路径可用带宽 vs 实际吞吐 |
| `plots/` | gnuplot 绘图脚本 |

### 3.3 traffic_matrix_load/ — 仿真器可扩展性

全流量矩阵在不同链路速率和仿真时长下的吞吐量，测试仿真器计算规模。

| 文件 | 作用 |
|------|------|
| `step_1_generate_runs.py` | 生成不同速率/时长的全矩阵加载 |
| `step_2_run.py` | 并行仿真 |
| `step_3_generate_plots.py` | 绘制吞吐 vs 规模曲线 |
| `templates/` | TCP 和 UDP 两种配置模板 |

### 3.4 two_compete/ — 两流竞争

两条 TCP 流竞争同一路径链路的带宽分析。

| 文件 | 作用 |
|------|------|
| `step_1-3_*.py` | 同上三步模式 |
| `plots/` | 路径可用带宽 vs 时间绘脚本 |

---

## 四、figures/ — 步骤6：汇总绘图

| 文件 | 作用 |
|------|------|
| `plot_all.py` | 遍历所有子目录执行 .plt 生成 PDF，并复制 satgenpy 图表 |
| `generate_pngs.py` | PDF 转 PNG |

### 9 个图表子目录

| 子目录 | 图纸内容 |
|--------|---------|
| `a_b/multiple_rtt_matching/` | ns-3 仿真 RTT vs satgenpy 计算 RTT 对比 |
| `a_b/tcp_cwnd/` | TCP 拥塞窗口 vs BDP + 队列容量 |
| `a_b/tcp_rate/` | TCP 吞吐量时序 |
| `a_b/tcp_mayhem/` | 极端路径切换对 TCP 的影响 |
| `a_b/tcp_isls_vs_gs_relays/` | ISL 路由 vs 地面弯管中继性能对比 |
| `constellation_comparison/general_ecdfs/` | 星座间 RTT/跳数/路径变更频率 ECDF |
| `traffic_matrix_unused_bandwidth/` | 竞争流量下路径未利用带宽 |
| `traffic_matrix_load_scalability/` | 仿真器扩展性：吞吐 vs 网络规模 |
| `two_compete/` | 两流竞争带宽分配 |

---

## 五、辅助文件

| 文件 | 作用 |
|------|------|
| `extract_temp_data.py` | 从 `hypatia_paper_temp_data.tar.gz` 解压预计算结果，跳过数天计算 |
| `package_temp_data.py` | 将本地运行产生的临时数据打包为 tar.gz 供分发 |

---

## 数据流

```
satellite_networks_state/ ──生成──→ gen_data/
                                       │
        ┌──────────────────────────────┤
        │                              │
        ▼                              ▼
 satgenpy_analysis/              ns3_experiments/
 (路由路径 + RTT)               (包级 TCP 仿真)
        │                              │
        └──────────┬───────────────────┘
                   ▼
              figures/
           (gnuplot 汇总)
```
