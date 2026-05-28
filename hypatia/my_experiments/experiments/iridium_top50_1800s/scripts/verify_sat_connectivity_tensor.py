#!/usr/bin/env python3
"""Quick check for sat_connectivity_tensor_dynamic_1800s_1s.npz."""
import os
import numpy as np


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    experiment_dir = os.path.dirname(script_dir)
    path = os.path.join(
        experiment_dir,
        "runs",
        "data",
        "sat_connectivity_tensor_dynamic_1800s_1s.npz",
    )
    data = np.load(path)
    conn = data["sat_connectivity"]
    print("sat_connectivity shape:", conn.shape)
    print("sat_connectivity dtype:", conn.dtype)
    print("time_ms len:", len(data["time_ms"]))
    print("sat_ids len:", len(data["sat_ids"]))


if __name__ == "__main__":
    main()
