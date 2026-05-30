# Project Rules

This repository contains Hypatia-based satellite-network experiments under
`hypatia/my_experiments`. When designing or modifying experiments, preserve the
separation between shared reusable code and per-experiment configuration.

## Experiment workspace layout

- Shared logic lives in `hypatia/my_experiments/shared/`.
- Each experiment lives in `hypatia/my_experiments/experiments/<experiment_name>/`.
- Per-experiment files should include:
  - `experiment_config.py`: all experiment parameters
  - `run_pipeline.py`: thin wrapper around the shared pipeline
  - optional diagnosis scripts such as `diagnose_cross_plane.py`
  - `README.md`: concise run instructions and experiment purpose
- Generated runtime outputs belong inside the experiment directory:
  - `input/`: generated ground stations, traffic schedule, traffic design summary
  - `gen_data/`: generated TLEs, `isls.txt`, dynamic state and fstate files
  - `runs/`: ns-3 run directory and logs
  - `logs/`: optional experiment notes/logs
- Do not put large generated outputs into shared code areas.

## Standard experiment pipeline

Use the shared pipeline in `shared/experiment_pipeline.py`.

A normal experiment runs:

```bash
cd hypatia/my_experiments/experiments/<experiment_name>
python run_pipeline.py --threads 4 --build
```

Use `--build` after C++ changes or when ns-3 has not been built. Omit it for
repeat runs when the simulator binary is already current.

The pipeline stages are:

1. `define_ground_stations(config)`
   - creates `input/ground_stations.basic.txt`
   - creates `input/ground_stations_manifest.csv`
2. `design_traffic(config)`
   - creates `input/schedule.csv`
   - creates OD traffic matrix and traffic design summary
3. `generate_satellite_network_state(config, constellation_helper, threads)`
   - creates `gen_data/<satellite_network_name>/`
   - creates `tles.txt`, `isls.txt`, `description.txt`, `gsl_interfaces_info.txt`
   - creates `dynamic_state_<TIME_STEP_MS>ms_for_<DURATION_S>s/fstate_*.txt`
4. `generate_ns3_run(config)`
   - creates `runs/main/`
   - copies topology files and schedule into the run directory
   - writes `runs/main/config_ns3.properties`
5. `run_ns3(config, build=...)`
   - runs `main_satnet`
   - writes ns-3 logs under `runs/main/logs_ns3/`

After ns-3 finishes, build tensors from `hypatia/my_experiments`:

```bash
python tensor_cli.py <experiment_name> sat-path-flow
python tensor_cli.py <experiment_name> sat-connectivity --bin-ms 1000
```

## Core experiment parameters

Every experiment config should define the following path and identity fields:

- `EXPERIMENT_DIR`, `EXPERIMENT_NAME`, `EXPERIMENTS_DIR`
- `MY_EXPERIMENTS_DIR`, `HYPATIA_DIR`
- `INPUT_DIR`, `GEN_DATA_ROOT`, `RUNS_DIR`, `LOGS_DIR`
- `GROUND_STATIONS_FILE`, `GROUND_STATIONS_MANIFEST`
- `TRAFFIC_SCHEDULE_FILE`, `TRAFFIC_DESIGN_FILE`, `TRAFFIC_MATRIX_FILE`
- `TRAFFIC_ACTIVITY_FILE`, optionally `TRAFFIC_FLOW_DETAILS_FILE`

Satellite/network fields:

- `SATELLITE_NETWORK`: constellation helper name, e.g. `iridium_780`,
  `starlink_550_324`
- `DURATION_S`: simulation duration in seconds
- `TIME_STEP_MS`: dynamic-state/fstate update interval
- `ISL_MODE`: usually `isls_plus_grid`
- `GS_SELECTION`: string used in generated network directory naming
- `ROUTING_ALGORITHM`: usually `algorithm_free_one_only_over_isls`
- `NUM_SATELLITES`: satellite count
- `NUM_GROUND_STATIONS`: ground station count
- `GS_START_NODE_ID`: normally `NUM_SATELLITES`
- `ISL_SHIFT`: plus-grid cross-plane ISL shift; see ISL rules below

Traffic fields:

- `TRAFFIC_PAIR_MODE`:
  - `explicit`: use `TRAFFIC_PAIRS`
  - `random`: random OD pair sample
  - `long_distance_balanced`: preferred for large synthetic datasets
  - `full_mesh`: all directed OD pairs
- `TRAFFIC_FLOW_COUNT`: number of TCP flows for random/long-distance modes
- `TRAFFIC_MIN_DISTANCE_KM`: minimum great-circle OD distance for long-distance mode
- `TRAFFIC_MAX_FLOWS_PER_CITY_ROLE`: cap to avoid one city dominating sources/dests
- `TRAFFIC_PREFERRED_REGION_PAIRS`: optional region-pair weighting
- `TRAFFIC_SEED`: deterministic OD/size generation seed
- `TRAFFIC_START_TIME_NS`: normally `0` for simultaneous flows
- `TRAFFIC_ACTIVITY_PROFILE`: `flat` for synthetic dataset generation, `geant`
  for time-zone weighted activity
- `TRAFFIC_OD_WEIGHT_MODE`: often `distance`
- `TRAFFIC_DISTANCE_WEIGHT_POWER`: distance weight exponent
- `TRAFFIC_RANDOMNESS_SIGMA`: reproducible lognormal size variation
- `TRAFFIC_CAPACITY_SCOPE`:
  - `single_bottleneck`: total budget based on one bottleneck
  - `per_ground_station`: budget scales with ground station count
- `TRAFFIC_OFFERED_LOAD`: offered load multiplier
- `TRAFFIC_TARGET_AVG_FLOW_SIZE_BYTES`: direct average flow target
- `TRAFFIC_MIN_FLOW_SIZE_BYTES`, `TRAFFIC_MAX_FLOW_SIZE_BYTES`: flow size bounds
- `TRAFFIC_REFERENCE_BANDWIDTH_MBIT_PER_S`: budget reference bandwidth

ns-3/link fields:

- `DATA_RATE_MBIT_PER_S`: ISL/GSL link data rate used by generated ns-3 config
- `QUEUE_SIZE_PKTS`: ISL/GSL queue size
- `TCP_SOCKET_TYPE`: e.g. `TcpNewReno`
- `ENABLE_TCP_FLOW_LOGGING`: set `False` for large dense dataset runs unless
  per-flow progress/RTT/cwnd is required
- `ENABLE_ISL_UTILIZATION_TRACKING`: keep `True` for cross-plane validation
- `ISL_UTILIZATION_TRACKING_INTERVAL_NS`: usually `1_000_000_000`
- `ENABLE_SATELLITE_PATH_TRACKING`: keep `True` for path-flow datasets
- `SATELLITE_PATH_TRACKING_INTERVAL_NS`: usually `1_000_000_000`

Required helper functions in every config:

```python
def satellite_network_name() -> str:
    return f"{SATELLITE_NETWORK}_{ISL_MODE}_{GS_SELECTION}_{ROUTING_ALGORITHM}"

def dynamic_state_dir_name() -> str:
    return f"dynamic_state_{TIME_STEP_MS}ms_for_{DURATION_S}s"

def generated_satellite_network_dir() -> Path:
    return GEN_DATA_ROOT / satellite_network_name()

def run_dir() -> Path:
    return RUNS_DIR / "main"
```

## ISL generation rules

- Never use `int(NUM_SATS_PER_ORB / 2)` as the default cross-plane ISL shift.
- Default `ISL_SHIFT` must be `0` unless explicitly configured.
- `experiment_config.py` may explicitly set `ISL_SHIFT`.
- If no experiment-specific `ISL_SHIFT` is set, shared generation must use `0`.
- For Iridium, `ISL_SHIFT = 0` is required for the current TLE geometry.
- The old `shift=5` Iridium behavior generated edges such as `0->16` and
  `1->17`; these were filtered out by dynamic-state distance checks and caused
  `cross_active=0`, `components=6`, and `cross_plane_bytes=0`.
- For each constellation, validate cross-plane ISLs by checking:
  - candidate cross-plane ISLs in `isls.txt`
  - active cross-plane ISLs after dynamic_state distance filtering
  - connected components of the satellite-only graph
  - cross-plane next-hops in fstate/path tracking
  - cross-plane bytes in `isl_utilization.csv`
- Different constellations may need different shift values. Use shift
  enumeration or nearest-neighbor geometry instead of guessing.
- Shift enumeration should report:
  - `cross_active`
  - `components`
  - `avg_cross_distance_m`
- Recommended shift rule:
  - choose maximum `cross_active`
  - if tied, choose minimum `components`
  - if still tied, choose minimum `avg_cross_distance_m`
- Do not fix cross-plane traffic by changing post-processing statistics. Fix
  ISL candidate generation and dynamic routing.

## Designing a large long-duration dataset experiment

Use a two-stage design: first a small diagnostic version, then the final large
run.

### Stage 1: diagnostic prototype

Create a small experiment first:

- duration: `4` to `10` seconds
- ground stations: `8` to `100`, depending on the question
- flows: `8` explicit flows or `100-1000` long-distance flows
- tracking: enable ISL utilization and satellite path tracking
- TCP flow logging: enable only when you need per-flow route/progress checks

The prototype must answer:

- Does `isls.txt` contain cross-plane candidate ISLs?
- Does dynamic-state distance filtering leave `cross_active > 0`?
- Is the satellite-only active graph connected, ideally `components=1`?
- Does `fstate` contain `cross_plane_sat_next_hops > 0`?
- Does `isl_utilization.csv` contain `cross_plane_bytes > 0`?
- Do recovered paths contain intermediate ground stations? They should not for
  `algorithm_free_one_only_over_isls`.
- Are source access and destination access satellites sometimes in different
  orbit planes for the chosen OD pairs?

Only scale up after these pass.

### Stage 2: final dataset run

For a large dataset-style run:

- Use a dedicated experiment directory. Do not reuse a diagnostic experiment
  name if the semantics changed.
- Choose a descriptive name, for example:
  - `iridium_uniform100_10s`
  - `iridium_top1000_60s`
  - `starlink_550_324_uniform100_10s`
- Set `ISL_SHIFT` explicitly.
- Use deterministic seeds for ground station and traffic generation.
- For synthetic global coverage, prefer:
  - `GROUND_STATION_SELECTION_MODE = "uniform_global"`
  - `TRAFFIC_PAIR_MODE = "long_distance_balanced"`
  - `TRAFFIC_ACTIVITY_PROFILE = "flat"`
  - `TRAFFIC_OD_WEIGHT_MODE = "distance"`
- Use `TRAFFIC_MIN_DISTANCE_KM` to encourage long-distance routes, but remember
  this does not guarantee every flow crosses orbit planes.
- If a dataset needs guaranteed cross-plane flows, add a preselection step which
  reconstructs fstate paths and chooses OD pairs whose satellite paths contain
  cross-plane hops.
- For dense path-flow matrix datasets, keep `ENABLE_TCP_FLOW_LOGGING = False`
  to avoid huge per-flow log files; use the C++ satellite path-flow monitor
  output under `runs/main/logs_ns3/sat_path_flow/`.

### Large-run validation checklist

After a large run, always record:

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

If cross-plane utilization is unexpectedly zero:

1. Do not edit `isl_utilization.csv` post-processing.
2. Check whether `cross_active` is zero.
3. If `cross_active=0`, fix ISL shift/candidate geometry.
4. If `cross_active>0` but `cross_plane_sat_next_hops=0`, inspect routing
   weights, GSL coverage, and OD choice.
5. If `cross_plane_sat_next_hops>0` but `cross_plane_bytes=0`, inspect ns-3
   arbiter/interface mapping and dynamic state loading.
6. If `cross_plane_bytes>0` but path-flow tensors show zero cross-plane values,
   then inspect path-flow monitor/post-processing.

## Post-processing expectations

- `sat-path-flow` is the preferred dataset source for satellite path-flow
  matrices. It reads C++ monitor CSVs under `runs/main/logs_ns3/sat_path_flow/`.
- `sat-path-flow-routes` is a route-derived comparison tool. It requires TCP
  progress logs and should not be used for dense experiments unless TCP flow
  logging is enabled.
- For multi-hop satellite path `A->B->C`, path-flow semantics expand bytes to
  `A->B`, `A->C`, and `B->C`.
- Diagonal `A->A` is only for single-satellite paths where traffic enters and
  exits through the same satellite.
- `isl_utilization.csv` reports actual link utilization, not theoretical link
  availability. Cross-plane edges can be present with zero bytes if routing
  never used them.

## What not to do

- Do not reuse old `gen_data` or `runs` after changing `DURATION_S`,
  `TIME_STEP_MS`, `ISL_SHIFT`, ground stations, traffic pairs, or routing
  algorithm.
- Do not infer cross-plane routing only from flow completion. Completed global
  flows may still use same-plane source/destination access satellites.
- Do not treat large geographic OD distance as a guarantee of cross-plane ISL
  usage.
- Do not change result statistics to create cross-plane traffic. Cross-plane
  traffic must come from valid ISL candidates, active dynamic routing, and
  actual ns-3 forwarding.
