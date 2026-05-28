#!/usr/bin/env python3
"""Standalone traffic matrix generator for my_experiments.

Generates a backbone-style N×N OD traffic matrix using low-rank factorization
and writes it as a schedule.csv for the ns-3 simulator.

Usage:
    python generate_traffic_matrix.py --num-gs 100 --gs-start-id 1156 \\
        --rank 5 --density 0.3 --flow-size-unit 1000000000 \\
        --seed 42 --output schedule.csv
"""

import argparse
import sys

from matrix_generator import generate_od_matrix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a low-rank OD traffic matrix for ns-3 simulation."
    )
    parser.add_argument("--num-gs", type=int, required=True,
                        help="Number of ground stations")
    parser.add_argument("--gs-start-id", type=int, required=True,
                        help="Starting node ID for ground stations "
                             "(equals number of satellites)")
    parser.add_argument("--rank", type=int, default=5,
                        help="Rank of the low-rank traffic matrix (default: 5)")
    parser.add_argument("--density", type=float, default=0.3,
                        help="Fraction of OD pairs with traffic, in (0,1] (default: 0.3)")
    parser.add_argument("--flow-size-unit", type=int, default=1_000_000_000,
                        help="Scaling factor for flow sizes in bytes (default: 1000000000)")
    parser.add_argument("--start-time", type=int, default=0,
                        help="Start time of all flows in ns (default: 0)")
    parser.add_argument("--seed", type=int, default=123456789,
                        help="Random seed for reproducibility (default: 123456789)")
    parser.add_argument("--weight-dist", type=str, default="lognormal",
                        choices=["lognormal", "pareto", "uniform"],
                        help="Factor matrix distribution (default: lognormal)")
    parser.add_argument("--output", type=str, default="schedule.csv",
                        help="Output CSV file path (default: schedule.csv)")
    parser.add_argument("--ground-truth", type=str, default=None,
                        help="Save the clean low-rank matrix (before noise/truncation) "
                             "as a .npy file for matrix completion evaluation")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print flow list to stdout instead of writing a CSV")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.num_gs < 2:
        sys.exit(f"num-gs must be >= 2, got {args.num_gs}")
    if args.rank < 1:
        sys.exit(f"rank must be >= 1, got {args.rank}")
    if args.density <= 0 or args.density > 1:
        sys.exit(f"density must be in (0, 1], got {args.density}")
    if args.flow_size_unit < 1:
        sys.exit(f"flow-size-unit must be >= 1, got {args.flow_size_unit}")


def main() -> None:
    args = parse_args()
    validate_args(args)

    # Generate the OD matrix
    local_pairs, base_sizes, T_clean = generate_od_matrix(
        n=args.num_gs,
        rank=args.rank,
        density=args.density,
        distribution=args.weight_dist,
        seed=args.seed,
    )

    # Optionally save the clean ground truth matrix
    if args.ground_truth:
        import numpy as np
        np.save(args.ground_truth, T_clean)
        print(f"Ground truth matrix saved to {args.ground_truth}")

    # Map to actual node IDs and scale flow sizes
    list_from_to: list[tuple[int, int]] = []
    list_flow_sizes: list[int] = []
    for (local_from, local_to), base_size in zip(local_pairs, base_sizes):
        actual_from = local_from + args.gs_start_id
        actual_to = local_to + args.gs_start_id
        flow_size = base_size * args.flow_size_unit
        list_from_to.append((actual_from, actual_to))
        list_flow_sizes.append(flow_size)

    num_flows = len(list_from_to)
    print(f"Generated {num_flows} flows "
          f"(N={args.num_gs}, rank={args.rank}, density={args.density})")

    if args.dry_run:
        print(f"\n{'from':>8} {'to':>8} {'size_byte':>16}")
        print("-" * 34)
        for (f, t), s in zip(list_from_to, list_flow_sizes):
            print(f"{f:>8} {t:>8} {s:>16}")
        return

    # Write schedule.csv via networkload
    try:
        import networkload
    except ImportError:
        sys.exit(
            "networkload is not installed. Install it with:\n"
            "  pip install git+https://github.com/snkas/networkload.git@v1.3\n"
            "Or use --dry-run to print flows to stdout."
        )

    networkload.write_schedule(
        args.output,
        num_flows,
        list_from_to,
        list_flow_sizes,
        [args.start_time] * num_flows,
    )
    print(f"Written to {args.output}")


if __name__ == "__main__":
    main()
