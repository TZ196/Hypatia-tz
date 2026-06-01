## Starlink 550 120 SatFill 5s

This is the active Starlink matrix-filling experiment in `my_experiments`.
It uses a 120-satellite shell so dense path-flow dataset iterations stay fast.

Current configuration:

- 120 Starlink satellites in `10` orbital planes with `12` satellites per plane
- 240 satellite-anchored ground stations, exactly `2 * NUM_SATELLITES`
- one base ground station at each satellite shadow point at `t=0`
- one jittered ground station per satellite, about 350-700 km from the base point
- 5 seconds of simulation
- 100 Mbit/s ISL links and 10 Mbit/s GSL links
- `120 * 120 = 14400` directed TCP flows
- per source satellite:
  every destination satellite is covered exactly once, including itself
  through mixed near/mid/far/cross-plane strata
- each flow is exactly 5 MB
- `TRAFFIC_MIN_DISTANCE_KM = 0`; satellite OD coverage is enforced directly
  by the anchored source/destination satellite pair selection
- `ISL_SHIFT = 0`

## Run

```bash
cd hypatia/my_experiments/experiments/starlink_550_120_satfill_3s
python run_pipeline.py --threads 4 --build
```

## Check

- every source access satellite injects traffic at `t=0`
- all 120 destination access satellites are covered for each source, including self loops
- `logs_ns3/isl_utilization.csv` shows nonzero cross-plane bytes
- `logs_ns3/sat_path_flow/metadata.txt` shows nonzero path observations
- `logs_ns3/sat_path_flow/rtt_ns/` contains satellite-path RTT matrices
- `logs_ns3/sat_path_flow/one_way_delay_ns/` contains byte-weighted one-way
  satellite-path delay matrices
