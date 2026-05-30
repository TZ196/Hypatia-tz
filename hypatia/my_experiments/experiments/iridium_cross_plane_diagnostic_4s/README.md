## Iridium Cross-Plane Diagnostic 4s

Small experiment for checking why cross-plane ISLs have zero utilization.

It uses:

- Iridium 780 km, 66 satellites
- 8 fixed globally distributed ground stations
- 8 directed long-distance TCP flows
- 4 seconds of simulation
- 1-second dynamic-state updates

Run:

```bash
cd /home/xuke/tz-Hypatia/hypatia
source venv/bin/activate
export CC=gcc-9 CXX=g++-9

cd my_experiments/experiments/iridium_cross_plane_diagnostic_4s
python run_all.py --threads 4 --build
```

If ns-3 has already been rebuilt after the latest C++ changes, omit `--build`.

`run_all.py` first sweeps `isl_shift=0..10`. With
`AUTO_SELECT_ISL_SHIFT = True`, it then runs the experiment using the best
shift found by the sweep.

The diagnosis prints:

- whether each flow finished
- source/destination access satellites and their orbit planes
- whether recovered fstate paths contain intermediate ground stations
- whether recovered fstate paths contain cross-plane satellite hops
- active satellite-only graph components for each dynamic-state time
- fstate same-plane/cross-plane next-hop counts
- same-plane/cross-plane bytes from `isl_utilization.csv`
