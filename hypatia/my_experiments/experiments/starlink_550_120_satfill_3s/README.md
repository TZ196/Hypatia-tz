## Starlink 550 120 SatFill 5s

This is the active Starlink matrix-filling experiment in `my_experiments`.
It uses a 120-satellite shell so dense path-flow dataset iterations stay fast.

Current configuration:

- 120 Starlink satellites in `10` orbital planes with `12` satellites per plane
- 120 satellite-anchored ground stations, exactly `1 * NUM_SATELLITES`
- one base ground station at each satellite shadow point at `t=0`
- 5 seconds of simulation
- 100 Mbit/s ISL links and 10 Mbit/s GSL links
- `120 * 119 = 14280` directed TCP flows
- per source satellite:
  every other destination satellite is covered exactly once, excluding itself
- each flow is exactly 5 MB
- `TRAFFIC_MIN_DISTANCE_KM = 0`; satellite OD coverage is enforced directly
  by the anchored source/destination satellite pair selection
- `ISL_SHIFT = 0`

## Run

```bash
cd hypatia/my_experiments/experiments/starlink_550_120_satfill_3s
python run_pipeline.py --threads 4 --build
```

## Check

- every source access satellite injects traffic at `t=0`
- all 119 non-self destination access satellites are covered for each source
- `logs_ns3/isl_utilization.csv` shows nonzero cross-plane bytes
- `logs_ns3/sat_path_flow/metadata.txt` shows nonzero path observations
- `logs_ns3/sat_path_flow/rtt_ns/` contains satellite-path RTT matrices
- `logs_ns3/sat_path_flow/bytes/` and `drop_bytes/` contain path traffic and
  unfinished/drop attribution matrices

## Tensors

After ns-3 finishes, build the three satellite path tensors:

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
(NUM_SATELLITES, NUM_SATELLITES, num_time_bins)
```

For this experiment, that is normally:

```text
(120, 120, 5)
```
