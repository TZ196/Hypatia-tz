# Project Rules

This repository currently keeps one active dataset experiment under
`hypatia/my_experiments` plus one isolated diagnostic experiment:

- `experiments/starlink_550_120_satfill_3s`
- `experiments/starlink_550_120_udp_drop_test`

Old Iridium, Starlink-324, Kuiper, OneWeb, and Telesat experiment wrappers and
constellation helpers have been intentionally removed. Do not reintroduce them
unless the user explicitly asks for a new experiment.

## Current Workspace Layout

- `hypatia/my_experiments/experiments/starlink_550_120_satfill_3s/`
  contains the active TCP matrix-filling dataset experiment.
- `hypatia/my_experiments/experiments/starlink_550_120_udp_drop_test/`
  contains only the UDP drop-accounting diagnostic. Keep it separate from the
  main dataset experiment.
- `hypatia/my_experiments/shared/experiment_pipeline.py` contains the narrow
  shared pipeline for this experiment.
- `hypatia/my_experiments/shared/traffic/traffic_plan.py` contains only the
  satellite-pair stratified traffic generator.
- `hypatia/my_experiments/shared/constellation/` contains only:
  - `main_helper.py`
  - `main_starlink_550_120.py`
- `tensor_cli.py` and `shared/tensor_tools.py` remain available for post-run
  tensor construction.

Generated outputs should stay inside the experiment directory:

- `input/`: generated ground stations and traffic schedule/design files
- `gen_data/`: TLEs, `isls.txt`, dynamic state, fstate files
- `runs/`: ns-3 run directory and logs
- `logs/`: optional notes

## Active Experiment Semantics

The current experiment is a small matrix-filling Starlink shell:

- 120 satellites
- 10 orbital planes
- 12 satellites per plane
- 240 satellite-anchored ground stations
- 3 seconds
- `ISL_SHIFT = 0`
- `ISL_DATA_RATE_MBIT_PER_S = 10_000`
- `GSL_DATA_RATE_MBIT_PER_S = 10_000`
- `120 * 120 = 14400` TCP flows
- every source access satellite sends to every destination access satellite,
  including itself
- self-satellite logical pairs must use two different ground stations anchored
  to the same satellite, because ns-3 rejects TCP flows from a node to itself
- every TCP flow uses the same size: `TRAFFIC_FLOW_SIZE_BYTES`

The current shared pipeline supports only:

- `GROUND_STATION_SELECTION_MODE = "satellite_anchored"`
- `TRAFFIC_PAIR_MODE = "satellite_pair_stratified"`
- Starlink-120 constellation generation

Do not assume older modes such as `uniform_global`, `random_sample`,
`long_distance_balanced`, `satellite_access_far`, or `full_mesh` still exist.

## Run

From the experiment directory:

```bash
cd hypatia/my_experiments/experiments/starlink_550_120_satfill_3s
python run_pipeline.py --threads 4 --build
```

Use `--build` after C++ changes or when the ns-3 binary has not been built.
Omit it for repeat runs when the simulator binary is current.

To test whether satellite path drop accounting is working, use the dedicated
UDP diagnostic experiment instead of the main TCP workload:

```bash
cd hypatia/my_experiments/experiments/starlink_550_120_udp_drop_test
python run_udp_drop_test.py --threads 4 --build
```

This creates `runs/main/` under the UDP diagnostic directory, disables TCP, sends high-rate UDP bursts,
uses high GSL bandwidth, and constrains ISL bandwidth/queue size to force
device-level ISL drops after packets have entered satellite paths. If the
drop matrices are still zero, inspect the printed drop audit counters:
`satellite_drop_events`, `satellite_drop_events_without_path_tag`,
`satellite_drop_events_without_open_path`, and
`satellite_drop_events_recorded`.

The pipeline stages are:

1. `define_ground_stations(config)`
   - creates `input/ground_stations.basic.txt`
   - creates `input/ground_stations_manifest.csv`
2. `design_traffic(config)`
   - creates `input/schedule.csv`
   - creates `input/traffic_matrix_bytes.csv`
   - creates `input/traffic_design.txt`
   - creates `input/traffic_flow_details.csv`
3. `generate_satellite_network_state(config, constellation_helper, threads)`
   - creates `gen_data/<satellite_network_name>/`
   - creates `tles.txt`, `isls.txt`, `description.txt`,
     `gsl_interfaces_info.txt`
   - creates `dynamic_state_<TIME_STEP_MS>ms_for_<DURATION_S>s/fstate_*.txt`
4. `generate_ns3_run(config)`
   - creates `runs/main/`
   - copies topology files and schedule into the run directory
   - writes `runs/main/config_ns3.properties`
5. `run_ns3(config, build=...)`
   - runs `main_satnet`
   - writes ns-3 logs under `runs/main/logs_ns3/`

## Post-Processing

After ns-3 finishes, build tensors from `hypatia/my_experiments`:

```bash
python tensor_cli.py starlink_550_120_satfill_3s sat-path-flow
python tensor_cli.py starlink_550_120_satfill_3s sat-connectivity --bin-ms 1000
```

`sat-path-flow` is the preferred dataset source for satellite path-flow
matrices. It reads C++ monitor CSVs under
`runs/main/logs_ns3/sat_path_flow/`.

Path-flow semantics:

- for multi-hop satellite path `A->B->C`, bytes are expanded to `A->B`,
  `A->C`, and `B->C`
- diagonal `A->A` is only for single-satellite paths where traffic enters and
  exits through the same satellite
- `one_way_delay_ns[A][B]` is the byte-weighted time between the packet receive
  event at satellite `A` and the later receive event at satellite `B`
- `rtt_ns[A][B]` is a satellite-path RTT estimate:
  `one_way_delay_ns[A][B] + one_way_delay_ns[B][A]` within the same time bin
  and is `0` if the reverse direction has no observation
- `isl_utilization.csv` reports actual link utilization, not theoretical
  availability

## ISL Generation Rules

- Never use `int(NUM_SATS_PER_ORB / 2)` as the default cross-plane ISL shift.
- Default `ISL_SHIFT` must be `0` unless explicitly configured.
- `experiment_config.py` may explicitly set `ISL_SHIFT`.
- If no experiment-specific `ISL_SHIFT` is set, shared generation must use `0`.
- Different constellations may need different shift values. Use shift
  enumeration or nearest-neighbor geometry instead of guessing.
- Do not fix cross-plane traffic by changing post-processing statistics. Fix
  ISL candidate generation and dynamic routing.

Validation checklist for any future constellation:

- candidate cross-plane ISLs in `isls.txt`
- active cross-plane ISLs after dynamic-state distance filtering
- connected components of the satellite-only graph
- cross-plane next-hops in fstate/path tracking
- cross-plane bytes in `isl_utilization.csv`

Recommended shift enumeration output:

- `cross_active`
- `components`
- `avg_cross_distance_m`

Recommended shift choice:

1. choose maximum `cross_active`
2. if tied, choose minimum `components`
3. if still tied, choose minimum `avg_cross_distance_m`

Known historical failure:

- Iridium with `shift=5` generated edges such as `0->16` and `1->17`
- those edges were filtered out by dynamic-state distance checks
- the result was `cross_active=0`, `components=6`, and `cross_plane_bytes=0`

## Validation Checklist

After a run, record:

- `gen_data/.../isls.txt` same-plane/cross-plane candidate counts
- active graph summary:
  - `same_active`
  - `cross_active`
  - connected component count and sizes
- fstate summary:
  - `same_plane_sat_next_hops`
  - `cross_plane_sat_next_hops`
  - drops
- ns-3 utilization:
  - same-plane directed edge count
  - cross-plane directed edge count
  - same-plane bytes
  - cross-plane bytes
  - nonzero same-plane/cross-plane edge counts
- satellite path-flow metadata:
  - `max_path_length_seen`
  - `transit_pair_observations`
  - `non_adjacent_pair_observations`
  - `non_adjacent_bytes`
  - `path_length_histogram`
- final tensor shapes from `tensor_cli.py`

If matrix coverage is still sparse, do not change the post-processing first.
Inspect OD design, fstate paths, dynamic graph connectivity, simulation
duration, unfinished TCP flows, and the path-flow monitor metadata.

## What Not To Do

- Do not reuse old `gen_data` or `runs` after changing `DURATION_S`,
  `TIME_STEP_MS`, `ISL_SHIFT`, ground stations, traffic pairs, or routing
  algorithm.
- Do not infer cross-plane routing only from flow completion.
- Do not treat large geographic OD distance as a guarantee of cross-plane ISL
  usage.
- Do not edit `isl_utilization.csv` or tensor post-processing to create traffic
  that did not occur in ns-3.
