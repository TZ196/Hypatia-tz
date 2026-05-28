## Iridium Top50 1800s

This workspace contains the full pipeline and outputs for the `iridium_top50_1800s` experiment.

## Contents

- `generate_iridium_top50_1800s.py`: main experiment entry point
- `gen_data/`: generated constellation state and traffic matrix inputs
- `runs/`: ns-3 run directory and simulation outputs
- `scripts/`: experiment-specific helper scripts for tensor generation and post-processing
- `logs/`: execution logs
- `notes/`: ad hoc notes and summaries

## Typical Commands

```bash
cd /home/xuke/tz-Hypatia/hypatia/my_experiments/experiments/iridium_top50_1800s
/home/xuke/tz-Hypatia/.venv/bin/python generate_iridium_top50_1800s.py --step 1 --threads 4
/home/xuke/tz-Hypatia/.venv/bin/python generate_iridium_top50_1800s.py --step 2
/home/xuke/tz-Hypatia/.venv/bin/python generate_iridium_top50_1800s.py --step 3
/home/xuke/tz-Hypatia/.venv/bin/python generate_iridium_top50_1800s.py --step 4
```
