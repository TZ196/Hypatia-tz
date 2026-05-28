## Iridium Top50 1800s

This is one isolated experiment definition: Iridium constellation, top 50 ground stations, 1800 seconds.

The common workflow lives in `my_experiments/shared/experiment_pipeline.py`. This directory only provides this experiment's parameters and one small wrapper script.

It follows the simulation pipeline in `docs/03-simulation-pipeline.md`, with two explicit preparation steps before ns-3 runs:

1. Define which ground stations are used.
2. Define how many traffic flows exist and how much traffic each flow sends.
3. Generate the satgenpy satellite network state.
4. Generate the ns-3 run directory.
5. Run ns-3.

No post-analysis, plotting, RTT analysis, or Cesium visualization is included in this pipeline.

## Directory Layout

- `experiment_config.py`: this experiment's duration, time step, constellation, ground-station count, traffic budget, link rate, and TCP type.
- `run_pipeline.py`: calls the shared pipeline with this experiment's config.
- `input/`: generated at runtime from this experiment's config.
- `gen_data/`: generated at runtime by satgenpy.
- `runs/main/`: generated at runtime for ns-3.
- `logs/`: optional experiment logs.

## Run Commands

Run these on the server after activating the Hypatia environment:

```bash
cd /home/xuke/tz-Hypatia/hypatia
conda deactivate 2>/dev/null
unset CONDA_PREFIX VIRTUAL_ENV
export PATH="/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin"
source venv/bin/activate
export CC=gcc-9 CXX=g++-9

cd my_experiments/experiments/iridium_top50_1800s
python run_pipeline.py --threads 4
```

If ns-3 has not been built on the server yet, use:

```bash
python run_pipeline.py --threads 4 --build
```

Single-step execution is implemented in the shared pipeline, not copied into this experiment directory.

Tensor utilities are also shared. For example:

```bash
cd my_experiments
python tensor_cli.py iridium_top50_1800s traffic --time-slice-s 5
python tensor_cli.py iridium_top50_1800s rtt --time-slice-s 5
python tensor_cli.py iridium_top50_1800s sat-connectivity --bin-ms 1000
```

## Current Experiment Definition

- Constellation: Iridium 780 km, 66 satellites.
- Ground stations: top 50 cities copied from `my_experiments/shared/input_data/ground_stations_top_50.basic.txt`.
- Ground-station node IDs in ns-3: `66` through `115`.
- Duration: `1800` seconds.
- Dynamic-state update interval: `1000` ms.
- ISL mode: `isls_plus_grid`.
- Routing algorithm: `algorithm_free_one_only_over_isls`.
- Traffic model: full-mesh OD flows, all starting at `0 ns`.
- Traffic sizing: each ground station is mapped to a longitude-based time zone, activity comes from the 24-hour GEANT profile at `TRAFFIC_REFERENCE_UTC_HOUR=0`, and each OD flow is weighted by source and destination activity.
- Traffic budget: total offered bytes are bounded by `100 Mbit/s * 1800s * 50 ground stations * 0.2`, so flow sizes stay tied to the configured bandwidth and simulation duration.
- Link rate: `100` Mbit/s for ISL and GSL.
