## Starlink 550 120 UDP Drop Test

This is an isolated diagnostic experiment for satellite path drop accounting.
It is intentionally separate from `starlink_550_120_satfill_3s` so the main
TCP matrix-filling experiment is not changed by drop-debug settings.

The diagnostic:

- disables TCP flow scheduling
- enables UDP burst scheduling
- uses the same 120-satellite Starlink shell and satellite-anchored ground
  station generation
- sends four high-rate UDP bursts between far-apart anchored ground stations
- defaults to high GSL bandwidth, low ISL bandwidth, one-packet ISL queues,
  and large GSL queues so the ground-to-satellite hop does not absorb the loss
- prints satellite path drop audit counters from `sat_path_flow/metadata.txt`

## Run

```bash
cd hypatia/my_experiments/experiments/starlink_550_120_udp_drop_test
python run_udp_drop_test.py --threads 4 --build
```

Useful overrides:

```bash
python run_udp_drop_test.py --isl-mbps 1 --gsl-mbps 10000 --isl-queue-pkts 1 --gsl-queue-pkts 100000 --udp-rate-mbps 10000 --build
```

The run directory is:

```text
runs/main/
```

The final summary reports:

- `path_drop_bytes`
- `path_drop_packets`
- `satellite_drop_events`
- `satellite_drop_events_without_path_tag`
- `satellite_drop_events_without_open_path`
- `satellite_drop_events_recorded`
- `satellite_drop_events_recorded_with_next_hop`
- `satellite_drop_events_next_hop_not_satellite`

If `path_drop_*` is zero, use the audit counters to identify whether the
device-level drop callback was never reached, reached without a path tag, or
reached after the open path had already been removed.

If all `satellite_drop_events*` counters are zero while many UDP packets are
not delivered, the loss happened before a satellite device drop hook. The most
common cause is a tiny GSL/source queue or UDP socket admission failure. Keep
GSL queues large and ISL queues tiny when testing satellite-path drop
accounting.
