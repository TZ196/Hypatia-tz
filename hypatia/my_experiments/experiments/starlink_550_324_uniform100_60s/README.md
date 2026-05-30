# Starlink 550 324 Latitude-Band 1000 10s

This experiment is a dense Starlink path-flow run for validating whether a
large number of ground demand points inside the Starlink 550 km, 53-degree
inclination service band can fill the satellite path-flow matrix more densely.

The experiment keeps the original directory name for continuity, but the
current configuration is:

- 324 Starlink satellites
- 1000 uniformly distributed ground stations inside `[-52.5, 52.5]` degrees latitude
- 10000 directed long-distance TCP flows
- 10 seconds of simulation
- `TRAFFIC_MIN_DISTANCE_KM = 5000`
- `ISL_SHIFT = 0`
- ISL utilization tracking enabled
- satellite path-flow tracking enabled
- per-flow TCP progress/RTT/cwnd logging disabled

## Run

```bash
cd hypatia/my_experiments/experiments/starlink_550_324_uniform100_60s
python run_pipeline.py --threads 4 --build
```

Use `--build` after C++ changes or when the ns-3 binary is not current.

## Build tensors

```bash
cd hypatia/my_experiments
python tensor_cli.py starlink_550_324_uniform100_60s sat-path-flow
python tensor_cli.py starlink_550_324_uniform100_60s sat-connectivity --bin-ms 1000
```

## Required checks

After the run, check:

- generated ground stations stay inside the configured latitude band
- `isls.txt` contains cross-plane candidate ISLs
- dynamic-state active graph has `cross_active > 0`
- fstate has `cross_plane_sat_next_hops > 0`
- `logs_ns3/isl_utilization.csv` has `cross_plane_bytes > 0`
- `logs_ns3/sat_path_flow/metadata.txt` reports nonzero path observations

Remember that `sat-path-flow` is a path-expanded matrix, not a pure adjacent
ISL link-utilization matrix. Use `isl_utilization.csv` for actual directed ISL
edge bytes.
