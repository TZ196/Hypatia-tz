import csv
import os


def _decision_next_hop(decision):
    if decision is None:
        return -1
    if isinstance(decision, tuple):
        return decision[0]
    return decision


def _format_path(path):
    if path is None:
        return ""
    return " ".join(map(str, path))


def recover_route_path(src, dst, fstate, max_hops):
    path = [src]
    seen = {src}
    curr = src
    for _ in range(max_hops):
        decision = fstate.get((curr, dst))
        next_hop = _decision_next_hop(decision)
        if next_hop == -1:
            return None, "no_next_hop"
        path.append(next_hop)
        if next_hop == dst:
            return path, "ok"
        if next_hop in seen:
            return None, "loop"
        seen.add(next_hop)
        curr = next_hop
    return None, "max_hops_exceeded"


def route_weight(path, graph):
    if path is None:
        return None
    total = 0.0
    for idx in range(1, len(path)):
        edge_data = graph.get_edge_data(path[idx - 1], path[idx])
        if edge_data is None:
            return None
        total += edge_data["weight"]
    return total


def export_route_paths(output_dynamic_state_dir, time_since_epoch_ns, fstate, prev_route_paths,
                       graph, num_satellites, num_ground_stations):
    rows = []
    route_paths = {}
    max_hops = num_satellites + num_ground_stations + 1

    for (src, dst) in sorted(fstate.keys()):
        path, status = recover_route_path(src, dst, fstate, max_hops)
        total_weight = route_weight(path, graph) if path is not None else None
        previous_path = prev_route_paths.get((src, dst)) if prev_route_paths else None
        route_paths[(src, dst)] = path
        if previous_path is None and path is not None:
            event = "birth"
        elif previous_path is not None and path is None:
            event = "death"
        elif previous_path != path:
            event = "change"
        else:
            event = "persist"

        rows.append({
            "time_ns": time_since_epoch_ns,
            "src": src,
            "dst": dst,
            "status": status,
            "event": event,
            "path": _format_path(path),
            "previous_path": _format_path(previous_path),
            "hop_count": "" if path is None else max(0, len(path) - 1),
            "total_weight": "" if total_weight is None else total_weight,
        })

    fieldnames = [
        "time_ns",
        "src",
        "dst",
        "status",
        "event",
        "path",
        "previous_path",
        "hop_count",
        "total_weight",
    ]
    with open(os.path.join(output_dynamic_state_dir, "route_paths_%d.csv" % time_since_epoch_ns),
              "w", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    events_path = os.path.join(output_dynamic_state_dir, "route_events_%d.csv" % time_since_epoch_ns)
    with open(events_path, "w", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            if row["event"] != "persist":
                writer.writerow(row)

    return route_paths
