# 2. 框架存储的数据

整个仿真框架的核心是一个**数据生成流水线**。输入是星座参数 + 配置选择，输出是一组文件供 ns-3 读取运行。

---

## 2.1 星座轨道参数

内置 3 个完整星座，参数来自 FCC 申请文档，位于 `paper/satellite_networks_state/main_*.py`：

| 参数 | Kuiper-630 | Starlink-550 | Telesat-1015 |
|------|-----------|-------------|-------------|
| 轨道高度 | 630 km | 550 km | 1,015 km |
| 倾角 | 51.9° | 53.0° | 98.98° (极轨) |
| 轨道面数 | 34 | 72 | 27 |
| 每面卫星数 | 34 | 22 | 13 |
| **卫星总数** | **1,156** | **1,584** | **351** |
| 离心率 | 0.0000001 | 0.0000001 | 0.0000001 |
| 每天绕地圈数 | 14.80 | 15.19 | 13.66 |
| 最小仰角 | 30° | 25° | 10° |

> **注意**：TLE 并非真实星链数据，而是根据上述参数从零生成的合成 TLE，epoch 统一为 2000-01-01 00:00:00。

## 2.2 ISL（星间链路）

ISL **不预存**，每次运行时根据选择动态生成：

| 模式 | 参数值 | 生成函数 | 行为 |
|------|--------|---------|------|
| +Grid 网格 | `isls_plus_grid` | `generate_plus_grid_isls()` | 每颗卫星连接 4 个邻居：同轨前后 + 邻轨左右 |
| 无 ISL | `isls_none` | `generate_empty_isls()` | 不建立任何星间链路，卫星间必须通过地面站中继 |

输出格式（`isls.txt`），每行一对卫星 ID：
```
0 1
0 4
2 3
```

## 2.3 地面站数据

位于 `paper/satellite_networks_state/input_data/`：

| 文件 | 数量 | 用途 |
|------|------|------|
| `ground_stations_cities_sorted_by_estimated_2025_pop_top_100.basic.txt` | 100 | 全球前 100 大城市 |
| `ground_stations_cities_sorted_by_estimated_2025_pop_top_1000.basic.txt` | 1,000 | 全球前 1000 大城市 |
| `ground_stations_paris_moscow_grid.basic.txt` | 77 | 巴黎-莫斯科网格（弯管中继用） |

**基础格式**（`.basic.txt`）：
```
编号,城市名,纬度,经度,海拔
1,0,Tokyo,35.6895,139.69171,0
```

处理后补全 ECEF 笛卡尔坐标变为扩展格式。

## 2.4 路由算法

内置 4 种，位于 `satgenpy/satgen/dynamic_state/`，是 Hypatia 框架**自带**的：

| 算法 | ISL | 每卫星 GSL 接口 | GSL 配对 | 路径形式 |
|------|-----|----------------|---------|---------|
| `algorithm_free_one_only_over_isls` | 需要 | 1 | 自由 | GS→SAT→...→SAT→GS |
| `algorithm_free_one_only_gs_relays` | **禁止** | 1 | 自由 | GS→SAT→GS→SAT→...→GS |
| `algorithm_free_gs_one_sat_many_only_over_isls` | 需要 | =地面站数 | 自由（每地面站独占一接口） | GS→SAT→...→SAT→GS |
| `algorithm_paired_many_only_over_isls` | 需要 | =地面站数 | 固定配对（最近卫星） | GS→配对SAT→...→配对SAT→GS |

### 逐一说明

**算法1 — `algorithm_free_one_only_over_isls`（最常用，论文默认算法）**

- 每卫星只有 1 个 GSL 接口，数据包只能走 ISL 星间网络
- 路径严格为：源地面站 → 卫星 → (ISL) → ... → 卫星 → 目标地面站
- 源/目的卫星自由选择：Floyd-Warshall 计算纯卫星图最短路径，在可视范围内选最优的源卫星和目标卫星

**算法2 — `algorithm_free_one_only_gs_relays`（唯一不走 ISL 的算法）**

- 禁止 ISL，每卫星 1 个 GSL 接口
- 数据包反复在卫星和地面站之间弹跳：GS→SAT→GS→SAT→...→GS，称为"弯管中继"
- 论文中用于巴黎-莫斯科弯管中继对照实验
- 蓝图是一个卫星+地面站混合图（Floyd-Warshall），但没有 ISL 边
- 代码中有硬校验：任何卫星有 ISL 则直接报错

**算法3 — `algorithm_free_gs_one_sat_many_only_over_isls`**

- 每卫星有等于地面站数量的 GSL 接口（如 100 个地面站 = 每卫星 100 个 GSL 接口）
- 每个地面站独占一颗卫星的一个接口，自由选择最优
- 路径同样只走 ISL：GS→SAT→(ISL)→SAT→GS
- 适用于卫星硬件能力强、可同时服务大量地面站的场景

**算法4 — `algorithm_paired_many_only_over_isls`**

- 每卫星也有等于地面站数量的 GSL 接口
- 区别在于 GSL 配对是固定的：每个时间步，地面站锁定它可视范围内距离最近的那颗卫星
- 不自由选择源/目的卫星，配对由几何距离决定，每个时间步动态更新

### 关键区别总结

| 维度 | 算法1 | 算法2 | 算法3 | 算法4 |
|------|------|------|------|------|
| GSL 接口数 | 1 | 1 | N (=地面站数) | N (=地面站数) |
| GSL 配对方式 | 自由选择最优 | 自由选择最优 | 自由选择最优 | 固定（最近卫星） |
| ISL 网络 | 走 | 不走 | 走 | 走 |
| 用途 | 论文主实验 | 弯管中继对照 | 多接口场景 | 固定配对场景 |

### 底层引擎

4 种算法共享两套 Floyd-Warshall 最短路径引擎：

- 算法 1、3、4 调用 `calculate_fstate_shortest_path_without_gs_relaying()` —— 在**纯卫星图**上计算最短路径 + 选择最优源/目的卫星
- 算法 2 调用 `calculate_fstate_shortest_path_with_gs_relaying()` —— 在**卫星+地面站混合图**上计算最短路径

### ISL 与弯管中继能否混合？

当前 4 种算法不支持 ISL + 弯管中继同时使用，因为 `generate_dynamic_state.py` 中构造了两张互不相通的图：一张只有卫星+ISL 边，另一张只有卫星+地面站+GSL 边。但从底层 `calculate_fstate_shortest_path_with_gs_relaying` 的代码来看，该函数已经能正确处理三种链路类型（GS→SAT、SAT→GS、SAT→SAT），只需将 ISL 边也加入到混合图中即可启用混合路由。
