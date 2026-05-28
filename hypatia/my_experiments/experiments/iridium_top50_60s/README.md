## Iridium Top50 60s

This is an isolated experiment definition for a short Iridium run: 66 Iridium satellites, top 50 city ground stations, and 60 seconds of simulation.

The shared workflow lives in `my_experiments/shared/experiment_pipeline.py`. This directory only provides this experiment's configuration and wrapper script.

## Run

```bash
cd /home/xuke/tz-Hypatia/hypatia
conda deactivate 2>/dev/null
unset CONDA_PREFIX VIRTUAL_ENV
export PATH="/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin"
source venv/bin/activate
export CC=gcc-9 CXX=g++-9

cd my_experiments/experiments/iridium_top50_60s
python run_pipeline.py --threads 4
```

Use `python run_pipeline.py --threads 4 --build` if ns-3 has not been built on the server.

## Definition

- Constellation: `iridium_780`
- Ground stations: top 50 cities from `shared/input_data/ground_stations_top_50.basic.txt`
- Duration: `60` seconds
- Dynamic-state update interval: `1000` ms
- ISL mode: `isls_plus_grid`
- Routing algorithm: `algorithm_free_one_only_over_isls`
- Traffic: full-mesh OD flows, all starting at `0 ns`, sized by time-zone activity and bounded by configured bandwidth/duration
