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
