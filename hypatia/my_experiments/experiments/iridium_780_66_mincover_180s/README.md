# iridium_780_66_mincover_180s

Iridium-780 66-satellite, 180-second experiment using satellite-anchored
ground stations, biased stable routing, and min-cover traffic.

The routing configuration keeps stability-aware ISL filtering enabled, uses
consistent distance units for ISL/GSL weights, and sets `isl_weight_scale=0.01`
so satellite detours are deliberately cheaper than GSL access distance. This
is intended to improve ordered satellite path-pair coverage.

Local preparation only:

```bash
python run_prepare.py --threads 4 --with-run-dir
```

Full ns-3 run:

```bash
python run_pipeline.py --threads 4
```

The full pipeline also builds post-processing tensors after ns-3 finishes.
Outputs are written under `runs/main/data/`:

- `sat_path_bytes_tensor.npy`: satellite path traffic in bytes, shape `(66, 66, 180)`
- `sat_path_drop_bytes_tensor.npy`: satellite path drops in bytes, shape `(66, 66, 180)`
- `sat_path_rtt_ns_tensor.npy`: satellite path RTT in ns, shape `(66, 66, 180)`
- `sat_adjacency_tensor.npy`: active satellite ISL adjacency, shape `(66, 66, 180)`
- `sat_adjacency_time_ns.npy`: time index for the adjacency tensor

If ns-3 has already finished, build only the tensor outputs:

```bash
python run_postprocess.py
```
