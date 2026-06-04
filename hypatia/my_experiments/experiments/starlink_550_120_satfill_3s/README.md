## Starlink 550 120 MinCover 600s

This is the active Starlink minimum-cover experiment in `my_experiments`.
It uses a 120-satellite shell and covers the generated 10-minute forwarding
state horizon.

Current configuration:

- 120 Starlink satellites in `10` orbital planes with `12` satellites per plane
- 120 satellite-anchored ground stations, exactly `1 * NUM_SATELLITES`
- one base ground station at each satellite shadow point at `t=0`
- 600 seconds of simulation
- 10 Gbit/s ISL links and 100 Mbit/s GSL links
- `TRAFFIC_PAIR_MODE = "satellite_pair_min_cover"`
- min-cover traffic reads the generated `dynamic_state_* / fstate_*.txt`
  snapshots for this 600 s run and greedily covers ordered satellite path pairs
- repeated source/destination ground-station pairs are not merged, so selected
  flows start at their corresponding time slices across the full 10 minutes
- each selected flow is exactly 10 MB
- `ISL_SHIFT = 0`

## Run

```bash
cd hypatia/my_experiments/experiments/starlink_550_120_satfill_3s
python run_pipeline.py --threads 4 --build
```

## Check

- `input/traffic_design.txt` reports `pair_mode=satellite_pair_min_cover`
  and `min_cover_time_slices=600`
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
directly. It does not import `shared/tensor_tools.py`. It writes:

- `data/sat_path_bytes_mb_tensor.npy`
- `data/sat_path_drop_mb_tensor.npy`
- `data/sat_path_rtt_ms_tensor.npy`

Each tensor has shape:

```text
(NUM_SATELLITES, NUM_SATELLITES, num_time_bins)
```

For this experiment, that is normally:

```text
(120, 120, 600)
```
