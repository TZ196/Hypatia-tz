# 6. 流量仿真指南

## 6.1 数据流总览

```
流量数据 (你的数据)
      │
      ▼
  步骤1: 确定地面站归属  ← 将地理坐标映射到最近的地面站
      │
      ▼
  步骤2: 编写 schedule.csv  ← 定义 TCP 流的源、目的、大小、时间
      │
      ▼
  步骤3: 配置 config_ns3.properties  ← 引用 satgenpy 生成的星座和路由
      │
      ▼
  步骤4: 运行 ns-3 仿真  ← ./waf --run="main_satnet --run_dir=..."
      │
      ▼
  步骤5: 后分析 (吞吐量/延迟/ISL利用率)
```

---

## 6.2 流量注入机制

### schedule.csv 格式

仿真的流量调度由 `schedule.csv` 定义，位于每个运行目录中。格式如下：

```
tcp_flow_id,from_node_id,to_node_id,size_byte,start_time_ns,additional_parameters,metadata
0,17,18,100000000000,0,,
```

| 字段 | 含义 |
|------|------|
| `tcp_flow_id` | 流编号，从 0 开始递增 |
| `from_node_id` | 源地面站节点 ID |
| `to_node_id` | 目的地面站节点 ID |
| `size_byte` | 流量大小（字节） |
| `start_time_ns` | 开始时间（纳秒） |
| `additional_parameters` | 可选，留空 |
| `metadata` | 可选，留空 |

### 重要：路由不由 schedule.csv 指定

转发路由由 satgenpy 在步骤 1 预计算，写入 `dynamic_state_<t_ms>/fstate_<timestamp>.txt`。ns-3 运行时每个时间步（默认 100ms）重新加载转发表，实现随卫星运动的动态路由。

---

## 6.3 数据位置不在标准地面站上怎么办

### 方案 A：映射到最近地面站（推荐，适用于卫星骨干网分析）

```python
from geopy.distance import geodesic

def find_nearest_gs(my_lat, my_lon, gs_file):
    nearest_gs = None
    min_dist = float('inf')
    with open(gs_file) as f:
        for line in f:
            parts = line.strip().split(',')
            gs_id = int(parts[0])
            gs_lat, gs_lon = float(parts[2]), float(parts[3])
            dist = geodesic((my_lat, my_lon), (gs_lat, gs_lon)).km
            if dist < min_dist:
                min_dist = dist
                nearest_gs = (gs_id, gs_lat, gs_lon)
    return nearest_gs, min_dist

# 例：北京顺义 (40.13, 116.65) → 归到 Beijing GS (ID=6)
```

### 方案 B：自定义添加地面站（适用于需要精确端到端仿真）

仿照地面站文件格式创建新条目，重新运行 satgenpy 步骤 1：

```
编号,城市名,纬度,经度,海拔
0,MyLocation,39.9042,116.4074,0
```

### 方案 C：手动补偿接入延迟

在后处理中对 RTT 结果加上接入段修正：

```
接入延迟 ≈ 地面站到用户的直线距离 / 光速
例：50 km → 0.17 ms
```

---

## 6.4 修改转发路由的方法

### 方式 A：更换路由算法（步骤 1 参数）

satgenpy 步骤 1 的第 5 个命令行参数选择算法：

| 算法 | ISL | 路由形式 |
|------|-----|---------|
| `algorithm_free_one_only_over_isls` | 需要 | GS→SAT→...→SAT→GS |
| `algorithm_free_one_only_gs_relays` | 禁止 | GS→SAT→GS→...→GS（弯管中继） |
| `algorithm_free_gs_one_sat_many_only_over_isls` | 需要 | 每地面站独占一接口 |
| `algorithm_paired_many_only_over_isls` | 需要 | 固定配对最近卫星 |

例：
```bash
python main_kuiper_630.py 200 100 isls_plus_grid \
  ground_stations_top_100 algorithm_free_one_only_over_isls 4
```

### 方式 B：直接修改转发表（高级）

编辑 `dynamic_state_<t_ms>/fstate_<timestamp>.txt`，每行格式：

```
current_node_id,target_node_id,next_hop_node_id,my_if_id,next_if_id
```

修改特定 `<当前节点, 目标节点>` 对的 `next_hop_node_id` 即可强制改变转发路径。

---

## 6.5 论文实验参考

| 实验 | 位置 | 特点 |
|------|------|------|
| a_b | `paper/ns3_experiments/a_b/` | 单对地面站点对点转发 |
| traffic_matrix | `paper/ns3_experiments/traffic_matrix/` | 50 对地面站同时发流 |
| two_compete | `paper/ns3_experiments/two_compete/` | 两对地面站竞争带宽 |

实验流水线：
```bash
# 1. 生成运行目录和 schedule.csv
python step_1_generate_runs.py

# 2. 运行 ns-3 仿真
python step_2_run.py

# 3. 生成图表
python step_3_generate_plots.py
```

---

## 6.6 Handover（切换）能力说明

| 切换类型 | 是否支持 | 说明 |
|---------|---------|------|
| 地面站↔卫星切换 | ✅ 内置 | satgenpy 每个时间步重新计算可见卫星，自动切换 |
| 用户设备↔地面站/卫星切换 | ❌ 不支持 | 框架没有移动用户设备模型 |

Hypatia 的长处是**卫星骨干网的传输性能分析**（路由、拥塞控制、吞吐量）。如果需要用户移动性仿真，建议改用 ns-3 原生移动模型 + 卫星模块。
