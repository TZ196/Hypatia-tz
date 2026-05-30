#!/usr/bin/env python3
"""Diagnose cross-plane ISL routing for the small Iridium experiment."""

import csv
import sys
from collections import defaultdict, deque

import experiment_config as config

if str(config.MY_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(config.MY_EXPERIMENTS_DIR))
if str(config.HYPATIA_DIR / "satgenpy") not in sys.path:
    sys.path.insert(0, str(config.HYPATIA_DIR / "satgenpy"))


def plane(node_id):
    return node_id // config.NUM_SATS_PER_ORBIT


def is_sat(node_id):
    return 0 <= node_id < config.NUM_SATELLITES


def is_gs(node_id):
    return node_id >= config.NUM_SATELLITES


def read_schedule():
    flows = []
    with open(config.run_dir() / "schedule.csv", "r", encoding="utf-8") as f:
        for row in csv.reader(f):
            if row:
                flows.append({
                    "flow_id": int(row[0]),
                    "src": int(row[1]),
                    "dst": int(row[2]),
                    "size": int(row[3]),
                    "start_ns": int(row[4]),
                })
    return flows


def read_tcp_results():
    path = config.run_dir() / "logs_ns3" / "tcp_flows.csv"
    if not path.exists():
        return {}
    results = {}
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row:
                continue
            results[int(row[0])] = {
                "sent": int(row[7]),
                "finished": row[8],
            }
    return results


def available_fstate_times():
    dyn_dir = config.generated_satellite_network_dir() / config.dynamic_state_dir_name()
    times = []
    for path in dyn_dir.glob("fstate_*.txt"):
        try:
            times.append(int(path.stem.split("_", 1)[1]))
        except ValueError:
            pass
    return sorted(times)


def read_fstate_update(time_ns):
    path = config.generated_satellite_network_dir() / config.dynamic_state_dir_name() / f"fstate_{time_ns}.txt"
    update = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            current, dst, next_hop, own_if, next_if = line.split(",", 4)
            update[(int(current), int(dst))] = (int(next_hop), int(own_if), int(next_if))
    return update


def cumulative_fstates():
    current = {}
    result = {}
    for time_ns in available_fstate_times():
        current.update(read_fstate_update(time_ns))
        result[time_ns] = dict(current)
    return result


def recover_path(fstate, src, dst):
    path = [src]
    current = src
    visited = set()
    max_hops = config.NUM_SATELLITES * 4 + config.NUM_GROUND_STATIONS + 8

    for _ in range(max_hops):
        if current == dst:
            return "ok", path
        key = (current, dst)
        if key not in fstate:
            return "missing_route", path
        next_hop = fstate[key][0]
        if next_hop < 0:
            return "drop", path
        edge = (current, next_hop)
        if edge in visited or next_hop == current:
            path.append(next_hop)
            return "loop", path
        visited.add(edge)
        path.append(next_hop)
        current = next_hop

    return "max_hops_exceeded", path


def sat_path_only(path):
    return [node for node in path if is_sat(node)]


def has_intermediate_gs(path):
    return any(is_gs(node) for node in path[1:-1])


def cross_sat_hops(path):
    hops = []
    for a, b in zip(path, path[1:]):
        if is_sat(a) and is_sat(b) and plane(a) != plane(b):
            hops.append((a, b))
    return hops


def access_sats(path):
    sats = sat_path_only(path)
    if not sats:
        return None, None
    return sats[0], sats[-1]


def diagnose_flows(fstates):
    flows = read_schedule()
    tcp_results = read_tcp_results()

    print("=== Flow completion and recovered fstate paths ===")
    print(f"flow_count={len(flows)}")

    all_access_same_plane = True
    any_cross_hop = False
    any_intermediate_gs = False

    for flow in flows:
        result = tcp_results.get(flow["flow_id"], {})
        finished = result.get("finished", "UNKNOWN")
        sent = result.get("sent", "UNKNOWN")
        print(
            f"\nflow_id={flow['flow_id']} src={flow['src']} dst={flow['dst']} "
            f"size={flow['size']} sent={sent} finished={finished}"
        )

        seen = set()
        for time_ns, fstate in fstates.items():
            status, path = recover_path(fstate, flow["src"], flow["dst"])
            key = (status, tuple(path))
            if key in seen:
                continue
            seen.add(key)

            src_access, dst_access = access_sats(path)
            if src_access is None:
                access_same_plane = False
                access_desc = "access_sats=NONE"
            else:
                access_same_plane = plane(src_access) == plane(dst_access)
                access_desc = (
                    f"src_access={src_access}(plane={plane(src_access)}) "
                    f"dst_access={dst_access}(plane={plane(dst_access)}) "
                    f"same_access_plane={access_same_plane}"
                )

            intermediate_gs = has_intermediate_gs(path)
            cross_hops = cross_sat_hops(path)
            all_access_same_plane = all_access_same_plane and access_same_plane
            any_cross_hop = any_cross_hop or bool(cross_hops)
            any_intermediate_gs = any_intermediate_gs or intermediate_gs

            print(f"  fstate_time_ns={time_ns} status={status}")
            print(f"    path={path}")
            print(f"    {access_desc}")
            print(f"    intermediate_ground_station={intermediate_gs}")
            print(f"    cross_plane_satellite_hops={cross_hops}")

    print("\n=== Flow path verdict ===")
    print(f"all_recovered_paths_have_same_access_plane={all_access_same_plane}")
    print(f"any_recovered_path_has_cross_plane_satellite_hop={any_cross_hop}")
    print(f"any_recovered_path_has_intermediate_ground_station={any_intermediate_gs}")


def read_static_isls():
    path = config.generated_satellite_network_dir() / "isls.txt"
    edges = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                a, b = line.split()
                edges.append((int(a), int(b)))
    return edges


def read_max_isl_length_m():
    path = config.generated_satellite_network_dir() / "description.txt"
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("max_isl_length_m="):
                return float(line.split("=", 1)[1])
    raise ValueError(f"max_isl_length_m not found in {path}")


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


def diagnose_static_isls():
    edges = read_static_isls()
    same = [(a, b) for a, b in edges if plane(a) == plane(b)]
    cross = [(a, b) for a, b in edges if plane(a) != plane(b)]

    print("\n=== Static isls.txt summary ===")
    print(f"undirected_isls={len(edges)}")
    print(f"same_plane_isls={len(same)}")
    print(f"cross_plane_isls={len(cross)}")
    print(f"cross_plane_examples={cross[:12]}")


def diagnose_active_graph():
    print("\n=== Active satellite-only graph by dynamic-state time ===")
    try:
        import satgen
        from astropy import units as u
    except Exception as exc:
        print(f"SKIPPED active graph check: could not import satgen/astropy: {exc}")
        return

    gen_dir = config.generated_satellite_network_dir()
    tles = satgen.read_tles(str(gen_dir / "tles.txt"))
    satellites = tles["satellites"]
    epoch = tles["epoch"]
    max_isl_length_m = read_max_isl_length_m()
    edges = read_static_isls()

    for time_ns in available_fstate_times():
        time = epoch + time_ns * u.ns
        active = []
        same_active = 0
        cross_active = 0
        for a, b in edges:
            distance_m = satgen.distance_m_between_satellites(
                satellites[a],
                satellites[b],
                str(epoch),
                str(time),
            )
            if distance_m <= max_isl_length_m:
                active.append((a, b))
                if plane(a) == plane(b):
                    same_active += 1
                else:
                    cross_active += 1

        comps = connected_components(active)
        comp_sizes = sorted(len(comp) for comp in comps)
        six_orbit_rings = len(comps) == config.NUM_ORBITS and comp_sizes == [config.NUM_SATS_PER_ORBIT] * config.NUM_ORBITS
        print(
            f"time_ns={time_ns} active_isls={len(active)} "
            f"same_active={same_active} cross_active={cross_active} "
            f"components={len(comps)} component_sizes={comp_sizes} "
            f"six_independent_orbit_rings={six_orbit_rings}"
        )


def diagnose_fstate_next_hops(fstates):
    print("\n=== Fstate satellite next-hop summary ===")
    for time_ns, fstate in fstates.items():
        same = 0
        cross = 0
        drops = 0
        sat_to_gs = 0
        cross_examples = []
        for (current, _dst), (next_hop, _own_if, _next_if) in fstate.items():
            if not is_sat(current):
                continue
            if next_hop < 0:
                drops += 1
            elif is_sat(next_hop):
                if plane(current) == plane(next_hop):
                    same += 1
                else:
                    cross += 1
                    if len(cross_examples) < 12:
                        cross_examples.append((current, next_hop))
            else:
                sat_to_gs += 1

        print(
            f"time_ns={time_ns} same_plane_sat_next_hops={same} "
            f"cross_plane_sat_next_hops={cross} sat_to_gs_next_hops={sat_to_gs} "
            f"drops={drops} cross_examples={cross_examples}"
        )


def diagnose_isl_utilization():
    print("\n=== ns-3 isl_utilization.csv summary ===")
    path = config.run_dir() / "logs_ns3" / "isl_utilization.csv"
    if not path.exists():
        print(f"SKIPPED utilization check: missing {path}")
        return

    same_bytes = 0
    cross_bytes = 0
    same_nonzero = set()
    cross_nonzero = set()
    directed_edges = set()

    with open(path, "r", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row:
                continue
            src = int(row[0])
            dst = int(row[1])
            byte_count = int(row[5])
            directed_edges.add((src, dst))
            if plane(src) == plane(dst):
                same_bytes += byte_count
                if byte_count > 0:
                    same_nonzero.add((src, dst))
            else:
                cross_bytes += byte_count
                if byte_count > 0:
                    cross_nonzero.add((src, dst))

    same_edges = [edge for edge in directed_edges if plane(edge[0]) == plane(edge[1])]
    cross_edges = [edge for edge in directed_edges if plane(edge[0]) != plane(edge[1])]
    print(f"directed_edges={len(directed_edges)} same_plane_directed_edges={len(same_edges)} cross_plane_directed_edges={len(cross_edges)}")
    print(f"same_plane_bytes={same_bytes} cross_plane_bytes={cross_bytes}")
    print(f"same_plane_nonzero_edges={len(same_nonzero)} cross_plane_nonzero_edges={len(cross_nonzero)}")
    print(f"cross_plane_edge_examples={cross_edges[:12]}")


def main():
    fstates = cumulative_fstates()
    print("=== Experiment ===")
    print(f"name={config.EXPERIMENT_NAME}")
    print(f"num_satellites={config.NUM_SATELLITES}")
    print(f"num_orbits={config.NUM_ORBITS}")
    print(f"num_sats_per_orbit={config.NUM_SATS_PER_ORBIT}")
    print(f"isl_shift={config.ISL_SHIFT}")
    print(f"duration_s={config.DURATION_S}")
    print(f"fstate_times_ns={list(fstates)}")

    diagnose_static_isls()
    diagnose_active_graph()
    diagnose_fstate_next_hops(fstates)
    diagnose_flows(fstates)
    diagnose_isl_utilization()


if __name__ == "__main__":
    main()
