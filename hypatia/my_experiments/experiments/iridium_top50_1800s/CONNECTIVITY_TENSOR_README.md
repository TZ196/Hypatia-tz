Satellite Connectivity Tensor (Dynamic ISL, 1800s, 1s)
======================================================

This generates a time-series tensor where each time slice is an N x N matrix
of satellite connectivity (1 = connected by ISL, 0 = no ISL).

Assumptions
-----------
- ISL connectivity is computed per time step using satellite distances.
- Satellite count is derived from tles.txt.

Generate
--------
```bash
cd /home/xuke/tz-Hypatia/hypatia/my_experiments/experiments/iridium_top50_1800s
/home/xuke/tz-Hypatia/.venv/bin/python scripts/generate_sat_connectivity_tensor.py
```

Output
------
- runs/data/sat_connectivity_tensor_dynamic_1800s_1s.npz
  - sat_connectivity: uint8 (N, N, T)
  - sat_ids: int32 (N,)
  - time_ms: int64 (T,)

Verify
------
```bash
cd /home/xuke/tz-Hypatia/hypatia/my_experiments/experiments/iridium_top50_1800s
/home/xuke/tz-Hypatia/.venv/bin/python scripts/verify_sat_connectivity_tensor.py
```
