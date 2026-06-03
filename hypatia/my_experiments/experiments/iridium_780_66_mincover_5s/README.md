## Iridium 780 66 MinCover 5s

This experiment runs a compact Iridium NEXT-like shell with minimum-cover
traffic generation.

Current configuration:

- 66 satellites in `6` orbital planes with `11` satellites per plane
- altitude `780 km`, inclination `86.4 deg`, mean motion `14.36 rev/day`
- 66 satellite-anchored ground stations, exactly `1 * NUM_SATELLITES`
- 5 seconds of simulation
- 10 Gbit/s ISL links and 100 Mbit/s GSL links
- `TRAFFIC_PAIR_MODE = "satellite_pair_min_cover"`
- min-cover traffic reads the generated `dynamic_state_* / fstate_*.txt`
  snapshots for this 5 s run and greedily covers ordered satellite path pairs
- repeated source/destination ground-station pairs are merged by default
- each selected flow unit is 5 MB
- `ISL_SHIFT = 0`

## Run

```bash
cd hypatia/my_experiments/experiments/iridium_780_66_mincover_5s
python run_pipeline.py --threads 4 --build
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
- `data/sat_path_rtt_ms_tensor.npy`

The RTT tensor is converted from ns to ms during export.
