"""build_rtt_tensor.py

从 ns-3 仿真 rtt 文件构建 RTT 张量。

默认情况下，每个元素表示一个时间片内从 src 到 dst 的平均 RTT（单位 ns）。
时间片大小由 TIME_SLICE_S 控制（例如从 1s 改为 5s）。

相邻采样点之间 RTT 恒定；若区间跨越多个时间片，按时间比例拆分后做加权平均。
"""

import os
import numpy as np

LOGS_DIR = "/home/xuke/tz-Hypatia/hypatia/my_experiments/experiments/iridium_top50_1800s/runs/logs_ns3"
OUT_DIR  = "/home/xuke/tz-Hypatia/hypatia/my_experiments/experiments/iridium_top50_1800s/runs/data"

NUM_NODES = 50
OFFSET    = 66
DURATION  = 1800
TIME_SLICE_S = 5
NS_PER_S  = 1_000_000_000

if TIME_SLICE_S <= 0:
    raise ValueError("TIME_SLICE_S must be a positive integer")

NUM_SLICES = DURATION // TIME_SLICE_S
if NUM_SLICES * TIME_SLICE_S != DURATION:
    raise ValueError(
        f"DURATION ({DURATION}s) must be divisible by TIME_SLICE_S ({TIME_SLICE_S}s)"
    )

SLICE_NS = NS_PER_S * TIME_SLICE_S

os.makedirs(OUT_DIR, exist_ok=True)

# ===== 1. 解析 tcp_flows.txt =====
print("Parsing tcp_flows.txt ...")
flow_map = {}

with open(os.path.join(LOGS_DIR, "tcp_flows.txt")) as f:
    lines = f.readlines()

for line in lines[1:]:
    line = line.strip()
    if not line:
        continue
    parts = line.split()
    flow_id = int(parts[0])
    src = int(parts[1])
    dst = int(parts[2])
    src_idx = src - OFFSET
    dst_idx = dst - OFFSET
    if 0 <= src_idx < NUM_NODES and 0 <= dst_idx < NUM_NODES:
        flow_map[flow_id] = (src_idx, dst_idx)

print(f"  Loaded {len(flow_map)} flows.")

# ===== 2. 构建 RTT 张量（加权平均） =====
rtt_weighted = np.zeros((NUM_NODES, NUM_NODES, NUM_SLICES), dtype=np.float64)
rtt_weight   = np.zeros((NUM_NODES, NUM_NODES, NUM_SLICES), dtype=np.float64)

processed = 0
skipped = 0

for flow_id in sorted(flow_map.keys()):
    filepath = os.path.join(LOGS_DIR, f"tcp_flow_{flow_id}_rtt.csv")
    if not os.path.exists(filepath):
        skipped += 1
        continue

    src_idx, dst_idx = flow_map[flow_id]
    prev_time = None
    prev_rtt = None

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            time_ns = int(parts[1])
            rtt = int(parts[2])

            if prev_time is not None:
                rtt_value = prev_rtt
                t_start = prev_time
                t_end = time_ns

                if t_end > t_start and rtt_value > 0:
                    slice_start = t_start // SLICE_NS
                    slice_end   = t_end // SLICE_NS

                    if slice_start == slice_end:
                        # 同一时间片内
                        duration = t_end - t_start
                        if 0 <= slice_start < NUM_SLICES:
                            rtt_weighted[src_idx, dst_idx, slice_start] += rtt_value * duration
                            rtt_weight[src_idx, dst_idx, slice_start]   += duration
                    else:
                        # 跨越多个时间片，按时间比例拆分
                        # 第一段：从 t_start 到 slice_start 这个时间片结束
                        end_of_first_slice = (slice_start + 1) * SLICE_NS
                        duration = end_of_first_slice - t_start
                        if 0 <= slice_start < NUM_SLICES:
                            rtt_weighted[src_idx, dst_idx, slice_start] += rtt_value * duration
                            rtt_weight[src_idx, dst_idx, slice_start]   += duration

                        # 中间完整时间片
                        for s in range(slice_start + 1, slice_end):
                            if 0 <= s < NUM_SLICES:
                                rtt_weighted[src_idx, dst_idx, s] += rtt_value * SLICE_NS
                                rtt_weight[src_idx, dst_idx, s]   += SLICE_NS

                        # 最后一段：从 slice_end 这个时间片开始到 t_end
                        start_of_last_slice = slice_end * SLICE_NS
                        duration = t_end - start_of_last_slice
                        if duration > 0 and 0 <= slice_end < NUM_SLICES:
                            rtt_weighted[src_idx, dst_idx, slice_end] += rtt_value * duration
                            rtt_weight[src_idx, dst_idx, slice_end]   += duration

            prev_time = time_ns
            prev_rtt = rtt

    processed += 1
    if processed % 100 == 0:
        print(f"  {processed} flows processed ...")

print(f"  Done: {processed} processed, {skipped} skipped")

# 计算加权平均
mask = rtt_weight > 0
tensor = np.zeros((NUM_NODES, NUM_NODES, NUM_SLICES), dtype=np.float64)
tensor[mask] = rtt_weighted[mask] / rtt_weight[mask]

# ===== 3. 保存 =====
out_path = os.path.join(OUT_DIR, "rtt_tensor.npy")
np.save(out_path, tensor)
print(f"Saved tensor {tensor.shape} to {out_path}")
print(
    f"Time slice: {TIME_SLICE_S}s, total slices: {NUM_SLICES}, total duration: {DURATION}s"
)
print(f"Non-zero entries: {np.count_nonzero(tensor)} / {tensor.size}")
