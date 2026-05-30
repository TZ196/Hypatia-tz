#!/usr/bin/env python3
"""Sweep Iridium plus-grid ISL shifts and report active cross-plane connectivity."""

import tempfile
from collections import deque
from pathlib import Path

import experiment_config as config

import sys

if str(config.MY_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(config.MY_EXPERIMENTS_DIR))
if str(config.HYPATIA_DIR / "satgenpy") not in sys.path:
    sys.path.insert(0, str(config.HYPATIA_DIR / "satgenpy"))

import satgen
from astropy import units as u
from shared.constellation.main_iridium_780 import main_helper


def plane(sat_id):
    return sat_id // config.NUM_SATS_PER_ORBIT


def connected_components(active_edges):
    graph = {sid: set() for sid in range(config.NUM_SATELLITES)}
    for a, b in active_edges:
        graph[a].add(b)
        graph[b].add(a)

    components = []
    seen = set()
    for sid in range(config.NUM_SATELLITES):
        if sid in seen:
            continue
        q = deque([sid])
        seen.add(sid)
        comp = []
        while q:
            node = q.popleft()
            comp.append(node)
            for nxt in graph[node]:
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        components.append(sorted(comp))
    return components


def make_tles(tmp_dir):
    path = Path(tmp_dir) / "tles.txt"
    satgen.generate_tles_from_scratch_manual(
        str(path),
        main_helper.NICE_NAME,
        main_helper.NUM_ORBS,
        main_helper.NUM_SATS_PER_ORB,
        main_helper.PHASE_DIFF,
        main_helper.INCLINATION_DEGREE,
        main_helper.ECCENTRICITY,
        main_helper.ARG_OF_PERIGEE_DEGREE,
        main_helper.MEAN_MOTION_REV_PER_DAY,
    )
    return path


def make_isls(tmp_dir, shift):
    path = Path(tmp_dir) / f"isls_shift_{shift}.txt"
    satgen.generate_plus_grid_isls(
        str(path),
        config.NUM_ORBITS,
        config.NUM_SATS_PER_ORBIT,
        isl_shift=shift,
        idx_offset=0,
    )
    edges = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                a, b = line.split()
                edges.append((int(a), int(b)))
    return edges


def evaluate_shift(satellites, epoch, shift):
    with tempfile.TemporaryDirectory() as tmp_dir:
        edges = make_isls(tmp_dir, shift)

    time_results = []
    num_steps = config.DURATION_S * 1000 // config.TIME_STEP_MS
    for t_idx in range(num_steps):
        time_ns = t_idx * config.TIME_STEP_MS * 1_000_000
        time = epoch + time_ns * u.ns
        active_edges = []
        same_active = 0
        cross_active = 0
        cross_candidates = 0

        for a, b in edges:
            is_cross = plane(a) != plane(b)
            if is_cross:
                cross_candidates += 1

            distance_m = satgen.distance_m_between_satellites(
                satellites[a],
                satellites[b],
                str(epoch),
                str(time),
            )
            if distance_m > main_helper.MAX_ISL_LENGTH_M:
                continue

            active_edges.append((a, b))
            if is_cross:
                cross_active += 1
            else:
                same_active += 1

        comps = connected_components(active_edges)
        time_results.append({
            "time_ns": time_ns,
            "same_active": same_active,
            "cross_active": cross_active,
            "cross_candidates": cross_candidates,
            "components": len(comps),
            "component_sizes": sorted(len(comp) for comp in comps),
        })

    return time_results


def score_shift(results):
    total_cross_active = sum(row["cross_active"] for row in results)
    max_components = max(row["components"] for row in results)
    avg_components = sum(row["components"] for row in results) / len(results)
    return total_cross_active, -max_components, -avg_components


def main():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tles_path = make_tles(tmp_dir)
        tles = satgen.read_tles(str(tles_path))
        satellites = tles["satellites"]
        epoch = tles["epoch"]

        summaries = []
        print("=== Iridium ISL shift sweep ===")
        print(f"duration_s={config.DURATION_S}")
        print(f"time_step_ms={config.TIME_STEP_MS}")
        print(f"max_isl_length_m={main_helper.MAX_ISL_LENGTH_M}")

        for shift in range(config.NUM_SATS_PER_ORBIT):
            results = evaluate_shift(satellites, epoch, shift)
            total_cross_candidates = results[0]["cross_candidates"] if results else 0
            total_cross_active = sum(row["cross_active"] for row in results)
            min_components = min(row["components"] for row in results)
            max_components = max(row["components"] for row in results)
            summaries.append((score_shift(results), shift, results))

            print(
                f"shift={shift} total_cross_plane_candidate_isls={total_cross_candidates} "
                f"active_cross_plane_isls_sum={total_cross_active} "
                f"components_min={min_components} components_max={max_components}"
            )
            for row in results:
                print(
                    f"  time_ns={row['time_ns']} same_active={row['same_active']} "
                    f"cross_active={row['cross_active']} components={row['components']} "
                    f"component_sizes={row['component_sizes']}"
                )

        _score, best_shift, best_results = max(summaries, key=lambda item: item[0])
        print("\n=== Recommended shift ===")
        print(f"best_shift={best_shift}")
        print(f"best_active_cross_plane_isls_sum={sum(row['cross_active'] for row in best_results)}")
        print(f"best_components_max={max(row['components'] for row in best_results)}")
        print(f"configured_ISL_SHIFT={config.ISL_SHIFT}")
        if best_shift != config.ISL_SHIFT:
            print("WARNING configured_ISL_SHIFT differs from best_shift")
        return best_shift


if __name__ == "__main__":
    main()
