## Starlink 550 120 SatFill 3s

This is a small Starlink matrix-filling experiment derived from the
`starlink_550_324_uniform100_60s` workflow, but reduced to a 120-satellite
shell so we can iterate faster.

Current configuration:

- 120 Starlink satellites in `10` orbital planes with `12` satellites per plane
- 240 satellite-anchored ground stations, exactly `2 * NUM_SATELLITES`
- one base ground station at each satellite shadow point at `t=0`
- one jittered ground station per satellite, about 350-700 km from the base point
- 3 seconds of simulation
- `120 * 140 = 16800` directed TCP flows
- per source satellite:
  every destination satellite is covered once, then 20 repeated destinations are added
  through mixed near/mid/far/cross-plane strata
- each flow is 10-20 MB, with 15 MB target average
- `TRAFFIC_MIN_DISTANCE_KM = 3000`
- `ISL_SHIFT = 0`

## Run

```bash
cd hypatia/my_experiments/experiments/starlink_550_120_satfill_3s
python run_pipeline.py --threads 4 --build
```

## Check

- every source access satellite injects traffic at `t=0`
- all 120 destination access satellites are covered for each source before repeats
- `logs_ns3/isl_utilization.csv` shows nonzero cross-plane bytes
- `logs_ns3/sat_path_flow/metadata.txt` shows nonzero path observations
