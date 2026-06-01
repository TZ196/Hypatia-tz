## OneWeb 1200 588 SatFill 30s

This experiment builds a OneWeb Phase 1 / Eutelsat OneWeb near-polar shell
dataset using satellite-anchored ground stations.

Current configuration:

- 588 satellites in `12` orbital planes with `49` satellites per plane
- altitude `1200 km`, inclination `87.9 deg`, mean motion `13.18 rev/day`
- 588 satellite-anchored ground stations, exactly `1 * NUM_SATELLITES`
- one base ground station at each satellite shadow point at `t=0`
- 30 seconds of simulation
- 10 Gbit/s ISL links and 100 Mbit/s GSL links
- `588 * 587 = 345156` directed TCP flows
- per source satellite:
  every other destination satellite is covered exactly once, excluding itself
- each flow is exactly 5 MB
- `ISL_SHIFT = 0`

## Run

```bash
cd hypatia/my_experiments/experiments/oneweb_1200_588_satfill_30s
python run_pipeline.py --threads 4 --build
```

Background run:

```bash
nohup python run_pipeline.py --threads 4 --build > run_30s.log 2>&1 &
tail -f run_30s.log
```

## Tensors

After ns-3 finishes:

```bash
python build_sat_path_tensors.py
```

This reads `runs/main/logs_ns3/sat_path_flow/{bytes,drop_bytes,rtt_ns}/t_*.csv`
and writes:

- `data/sat_path_bytes_tensor.npy`
- `data/sat_path_drop_bytes_tensor.npy`
- `data/sat_path_rtt_ns_tensor.npy`

Each tensor has shape:

```text
(588, 588, 30)
```

The third dimension is time.

## Note

This is a large workload: `345156` TCP flows at 5 MB each is about 1.7 TB of
offered demand. It is intended for dataset generation and stress testing, not
for quick smoke tests.
