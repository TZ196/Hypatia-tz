# kuiper_590_180_mincover_180s

Kuiper-like 590 km, 33 degree compact shell experiment:

- 10 orbital planes x 18 satellites per plane = 180 satellites
- 590 km altitude, 33 degree inclination
- mean motion from a 96.3 minute period
- 180 seconds, 1 second dynamic-state interval
- 180 satellite-anchored ground stations
- ordinary distance shortest-path routing without ISL weight scaling
- geometry-aware ISL exports with Earth-clearance and tracking-rate fields
- 95% satellite-pair min-cover traffic with repeated source/destination pairs merged

The base min-cover event size is `500_000_000` bytes before timezone scaling.

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

- `sat_path_bytes_mb_tensor.npy`: satellite path traffic in MB, rounded to 2 decimals, shape `(180, 180, 180)`
- `sat_path_drop_mb_tensor.npy`: satellite path drops in MB, rounded to 2 decimals, shape `(180, 180, 180)`
- `sat_path_rtt_ms_tensor.npy`: satellite path RTT in ms, rounded to 2 decimals, shape `(180, 180, 180)`
- `sat_adjacency_tensor.npy`: active satellite ISL adjacency, shape `(180, 180, 180)`
- `sat_adjacency_time_ns.npy`: time index for the adjacency tensor

If ns-3 has already finished, build only the tensor outputs:

```bash
python run_postprocess.py
```
