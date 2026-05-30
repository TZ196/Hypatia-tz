# Starlink 550 324 Satellite-Anchored 648 10s

This experiment is a dense Starlink path-flow run for validating whether
satellite-anchored demand points can fill the satellite path-flow matrix more
densely than purely geographic random/uniform ground points.

The experiment keeps the original directory name for continuity, but the
current configuration is:

- 324 Starlink satellites
- 648 satellite-anchored ground stations, at most `2 * NUM_SATELLITES`
- one base ground station at each satellite shadow point at `t=0`
- one jittered ground station per satellite, about 350-700 km from the base point
- stratified satellite-pair traffic sampling
- each source access satellite samples `K = 100` distinct destination access satellites
- destination satellites are mixed across near, medium, far, and cross-plane strata
- default stratum weights are near 20%, medium 30%, far 30%, cross-plane 20%
- `324 * 100 = 32400` directed TCP flows
- each flow is 10-20 MB, with 15 MB target average
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

- generated ground station names follow `SatAnchor-<sat_id>-...`
- every satellite has at least one anchored source/destination candidate
- `isls.txt` contains cross-plane candidate ISLs
- dynamic-state active graph has `cross_active > 0`
- fstate has `cross_plane_sat_next_hops > 0`
- `logs_ns3/isl_utilization.csv` has `cross_plane_bytes > 0`
- `logs_ns3/sat_path_flow/metadata.txt` reports nonzero path observations

Remember that `sat-path-flow` is a path-expanded matrix, not a pure adjacent
ISL link-utilization matrix. Use `isl_utilization.csv` for actual directed ISL
edge bytes.
