# starlink_550_168_mincover_180s

Starlink-like 550 km, 53 degree compact shell experiment:

- 14 orbital planes x 12 satellites per plane = 168 satellites
- 550 km altitude, 53 degree inclination
- 180 seconds, 1 second dynamic-state interval
- 168 satellite-anchored ground stations
- distance shortest-path routing with `isl_weight_scale=0.1`
- Kuiper-style min-cover traffic and timezone-sized flow volumes
- single-flow base size `300 MB`
- ISL capacity `5 Gbps`, GSL capacity `1 Gbps`
- post-ns-3 tensor export enabled

Prepare inputs only:

```bash
python run_prepare.py --threads 4 --with-run-dir
```

Full ns-3 run:

```bash
python run_pipeline.py --threads 4
```

Background run:

```bash
nohup python run_pipeline.py --threads 4 > pipeline.log 2>&1 &
tail -f pipeline.log
```

After ns-3 finishes, the full pipeline builds post-processing tensors under
`runs/main/data/`:

- `sat_path_bytes_mb_tensor.npy`: satellite path traffic in MB, rounded to 2 decimals, shape `(168, 168, 180)`
- `sat_path_drop_mb_tensor.npy`: satellite path drops in MB, rounded to 2 decimals, shape `(168, 168, 180)`
- `sat_path_rtt_ms_tensor.npy`: satellite path RTT in ms, rounded to 2 decimals, shape `(168, 168, 180)`
- `sat_adjacency_tensor.npy`: active satellite ISL adjacency, shape `(168, 168, 180)`
- `sat_adjacency_time_ns.npy`: time index for the adjacency tensor

If ns-3 has already finished, build only the tensor outputs:

```bash
python run_postprocess.py
```
