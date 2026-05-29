## Iridium Path Validation 10s

This experiment is designed only to validate the online satellite path-flow
monitor. It uses Iridium, two far-apart ground stations, and one explicit TCP
flow sized close to one 10-second 100 Mbit/s bottleneck:

```text
New-York-Newark -> Sydney
```

The expected behavior is easy to inspect. If the packet path is:

```text
A -> B -> C -> D
```

the monitor should record:

```text
A->B, A->C, A->D, B->C, B->D, C->D
```

It should not record diagonal entries for multi-satellite paths. Diagonal
`A->A` is only valid for traffic that enters and leaves the satellite network
through the same single satellite.

## Run

```bash
cd /home/xuke/tz-Hypatia/hypatia
source venv/bin/activate
export CC=gcc-9 CXX=g++-9

cd my_experiments/experiments/iridium_path_validation_10s
python run_pipeline.py --threads 4 --build
```

Use `--build` because this validation is meant for C++ monitor changes.

## Inspect

```bash
cd /home/xuke/tz-Hypatia/hypatia/my_experiments/experiments/iridium_path_validation_10s
python validate_path_flow.py
```

The script prints:

- the single validation flow
- monitor metadata
- nonzero satellite pairs from `logs_ns3/sat_path_flow/bytes`
- fstate-derived path expansion as a reference
- missing or extra satellite pairs

To build tensors after inspection:

```bash
cd /home/xuke/tz-Hypatia/hypatia/my_experiments
python tensor_cli.py iridium_path_validation_10s sat-path-flow
```
