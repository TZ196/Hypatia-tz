## Iridium Satellite-Anchored 132 10s

This experiment keeps the existing directory name for continuity, but the
current design is no longer based on 100 uniform-global ground stations.

Current configuration:

- 66 Iridium satellites
- 132 satellite-anchored ground stations, exactly `2 * NUM_SATELLITES`
- one base ground station at each satellite shadow point at `t=0`
- one jittered ground station per satellite, about 350-700 km from the base point
- stratified satellite-pair traffic sampling
- each source access satellite samples all 66 destination access satellites, including itself
- `66 * 66 = 4356` directed TCP flows
- each flow is 10-20 MB, with 15 MB target average
- 10 seconds of simulation
- `TRAFFIC_MIN_DISTANCE_KM = 5000`
- `ISL_SHIFT = 0`
- ISL utilization tracking enabled
- satellite path-flow tracking enabled
- per-flow TCP progress/RTT/cwnd logging disabled

## Run

```bash
cd /home/xuke/tz-Hypatia/hypatia
source venv/bin/activate
export CC=gcc-9 CXX=g++-9

cd my_experiments/experiments/iridium_uniform100_10s
python run_pipeline.py --threads 4 --build
```

## Tensorize

```bash
cd /home/xuke/tz-Hypatia/hypatia/my_experiments
python tensor_cli.py iridium_uniform100_10s sat-path-flow
```

## Required checks

- generated ground station names follow `SatAnchor-<sat_id>-...`
- every Iridium satellite has exactly two anchored ground station candidates
- every source access satellite contributes flows at `t=0`
- the destination access satellites cover all 66 satellites, including same-satellite cases
- `logs_ns3/isl_utilization.csv` shows nonzero cross-plane bytes
- `logs_ns3/sat_path_flow/metadata.txt` reports nonzero path observations
