"""postprocess_tensors.py

从 ns-3 仿真 progress 文件构建流量张量。

默认情况下，每个元素表示一个时间片内从 src 到 dst 发送的字节数。
通过 TIME_SLICE_S 控制时间片大小（例如从 1s 改为 5s）。
"""

import os
import numpy as np
from collections import defaultdict

# ===== 路径配置 =====
LOGS_DIR = "/home/xuke/tz-Hypatia/hypatia/my_experiments/experiments/iridium_top50_1800s/runs/logs_ns3"
OUT_DIR  = "/home/xuke/tz-Hypatia/hypatia/my_experiments/experiments/iridium_top50_1800s/runs/data"

NUM_NODES = 50
OFFSET    = 66          # 基站编号从 66 开始
DURATION  = 1800        # 仿真时长 1800 秒
TIME_SLICE_S = 5        # 时间片大小（秒）
NS_PER_S  = 1_000_000_000

if TIME_SLICE_S <= 0:
    raise ValueError("TIME_SLICE_S must be a positive integer")

NUM_SLICES = DURATION // TIME_SLICE_S
if NUM_SLICES * TIME_SLICE_S != DURATION:
    raise ValueError(
        f"DURATION ({DURATION}s) must be divisible by TIME_SLICE_S ({TIME_SLICE_S}s)"
    )

os.makedirs(OUT_DIR, exist_ok=True)

# ===== 1. 解析 tcp_flows.txt，建立 flow_id -> (src_idx, dst_idx) =====
print("Parsing tcp_flows.txt ...")
flow_map = {}  # flow_id -> (src_idx, dst_idx)

with open(os.path.join(LOGS_DIR, "tcp_flows.txt")) as f:
    lines = f.readlines()

for line in lines[1:]:  # 跳过表头
    line = line.strip()
    if not line:
        continue
    parts = line.split()
    flow_id = int(parts[0])
    src     = int(parts[1])
    dst     = int(parts[2])
    src_idx = src - OFFSET
    dst_idx = dst - OFFSET
    if 0 <= src_idx < NUM_NODES and 0 <= dst_idx < NUM_NODES:
        flow_map[flow_id] = (src_idx, dst_idx)

print(f"  Loaded {len(flow_map)} flows.")

# ===== 2. 初始化张量 =====
tensor = np.zeros((NUM_NODES, NUM_NODES, NUM_SLICES), dtype=np.float64)

# ===== 3. 遍历所有 progress 文件，差分累加 =====
processed = 0
skipped   = 0

for flow_id in sorted(flow_map.keys()):
    filepath = os.path.join(LOGS_DIR, f"tcp_flow_{flow_id}_progress.csv")
    if not os.path.exists(filepath):
        skipped += 1
        continue

    src_idx, dst_idx = flow_map[flow_id]

    prev_time = None
    prev_bytes = None

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            time_ns = int(parts[1])
            bytes_cum = int(parts[2])

            if prev_time is not None:
                delta = bytes_cum - prev_bytes
                if delta > 0:
                    slice_idx = prev_time // (NS_PER_S * TIME_SLICE_S)
                    if 0 <= slice_idx < NUM_SLICES:
                        tensor[src_idx, dst_idx, slice_idx] += delta

            prev_time = time_ns
            prev_bytes = bytes_cum

    processed += 1
    if processed % 100 == 0:
        print(f"  Processed {processed} flows ...")

print(f"  Done: {processed} flows processed, {skipped} skipped (file missing).")

# ===== 4. 保存 =====
out_path = os.path.join(OUT_DIR, "traffic_tensor.npy")
np.save(out_path, tensor)
print(f"Saved tensor {tensor.shape} to {out_path}")

print(
    f"Time slice: {TIME_SLICE_S}s, total slices: {NUM_SLICES}, total duration: {DURATION}s"
)

# 简单统计
total_gb = tensor.sum() / 1e9
print(f"Total traffic: {total_gb:.2f} GB")
print(f"Non-zero entries: {np.count_nonzero(tensor)} / {tensor.size}")
