#!/usr/bin/env python3
"""Build satellite path tensors from sat_path_flow CSV matrices."""

import re
from pathlib import Path

import numpy as np
import experiment_config as config


def time_matrix_index(path: Path) -> int:
    match = re.fullmatch(r"t_(\d+)\.csv", path.name)
    if match is None:
        raise ValueError(f"Unexpected matrix filename: {path}")
    return int(match.group(1))


def read_metadata(path: Path) -> dict[str, str]:
    values = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value
    return values


def build_metric_tensor(
    base_dir: Path,
    metric: str,
    output_name: str,
    expected_bins: int | None,
    scale: float = 1.0,
) -> Path:
    metric_dir = base_dir / metric
    files = sorted(metric_dir.glob("t_*.csv"), key=time_matrix_index)
    if not files:
        raise FileNotFoundError(f"No matrix CSV files found in {metric_dir}")
    if expected_bins is not None and len(files) != expected_bins:
        raise ValueError(f"Expected {expected_bins} {metric} CSV files in {metric_dir}, got {len(files)}")

    matrices = []
    expected_shape = (config.NUM_SATELLITES, config.NUM_SATELLITES)
    for path in files:
        matrix = np.loadtxt(path, delimiter=",", dtype=np.uint64)
        if matrix.shape != expected_shape:
            raise ValueError(f"Unexpected matrix shape in {path}: {matrix.shape}; expected {expected_shape}")
        if scale != 1.0:
            matrix = matrix.astype(np.float64) * scale
        matrices.append(matrix)

    tensor = np.stack(matrices, axis=2)
    output_dir = config.EXPERIMENT_DIR / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name
    np.save(output_path, tensor)
    print(f"Saved {metric} tensor {tensor.shape} to {output_path}")
    return output_path


def build_sat_path_tensors() -> list[Path]:
    base_dir = config.run_dir() / "logs_ns3" / "sat_path_flow"
    if not base_dir.exists():
        raise FileNotFoundError(f"Satellite path flow directory not found: {base_dir}")

    metadata_path = base_dir / "metadata.txt"
    metadata = read_metadata(metadata_path) if metadata_path.exists() else {}
    expected_bins = int(metadata["num_time_bins"]) if "num_time_bins" in metadata else None

    metric_specs = [
        ("bytes", "sat_path_bytes_tensor.npy", 1.0),
        ("drop_bytes", "sat_path_drop_bytes_tensor.npy", 1.0),
        ("rtt_ns", "sat_path_rtt_ms_tensor.npy", 1.0 / 1_000_000.0),
    ]
    return [
        build_metric_tensor(base_dir, metric, output_name, expected_bins, scale)
        for metric, output_name, scale in metric_specs
    ]


def main():
    outputs = build_sat_path_tensors()
    print("Generated tensors:")
    for path in outputs:
        print(f"  {path}")


if __name__ == "__main__":
    main()
