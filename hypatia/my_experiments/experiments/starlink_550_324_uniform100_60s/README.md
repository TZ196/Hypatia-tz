## Starlink 550 324 Uniform100 60s

This experiment checks whether a reduced Starlink-like shell exhibits the same
within-orbit-plane block pattern seen in Iridium path-flow matrices.

Design:

- Reduced Starlink shell: 18 orbital planes x 18 satellites per plane = 324 satellites
- Altitude/inclination: Starlink-like 550 km / 53 degrees
- 100 synthetic ground stations generated uniformly over the globe
- 2000 directed long-distance OD flows
- 60 seconds of simulation
- Large TCP demands designed not to finish during the run

## Run

```bash
cd /home/xuke/tz-Hypatia/hypatia
source venv/bin/activate
export CC=gcc-9 CXX=g++-9

cd my_experiments/experiments/starlink_550_324_uniform100_60s
python run_pipeline.py --threads 4 --build
```

After ns-3 finishes:

```bash
cd /home/xuke/tz-Hypatia/hypatia/my_experiments
python tensor_cli.py starlink_550_324_uniform100_60s sat-path-flow
```

## ISL Cross-Plane Check

For this shell each orbit plane has 18 satellites. Cross-plane candidate ISLs
have `a // 18 != b // 18`.

```bash
cd /home/xuke/tz-Hypatia/hypatia/my_experiments/experiments/starlink_550_324_uniform100_60s
python - <<'PY'
from pathlib import Path
p = Path("gen_data/starlink_550_324_isls_plus_grid_ground_stations_uniform_global_100_algorithm_free_one_only_over_isls/isls.txt")
same = cross = 0
for line in p.read_text().splitlines():
    a, b = map(int, line.split())
    if a // 18 == b // 18:
        same += 1
    else:
        cross += 1
print("same_plane", same)
print("cross_plane", cross)
PY
```

Per-flow TCP progress/RTT/cwnd logging is disabled; use the C++ path-flow
monitor output under `runs/main/logs_ns3/sat_path_flow/`.
