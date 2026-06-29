import csv
import os


def _write_csv(path, fieldnames, rows):
    with open(path, "w", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def export_isl_decisions(output_dynamic_state_dir, time_since_epoch_ns, rows):
    active_rows = [row for row in rows if row["active"]]
    inactive_rows = [row for row in rows if not row["active"]]
    fieldnames = [
        "time_ns",
        "src_sat",
        "dst_sat",
        "active",
        "raw_active",
        "event",
        "reason",
        "distance_m",
        "weight",
        "link_type",
        "lat_src_deg",
        "lat_dst_deg",
        "pointing_src_deg",
        "pointing_dst_deg",
        "tracking_rate_src_deg_s",
        "tracking_rate_dst_deg_s",
        "earth_clearance_m",
        "predicted_link_duration_s",
        "age_s",
    ]
    _write_csv(
        os.path.join(output_dynamic_state_dir, "active_isls_%d.csv" % time_since_epoch_ns),
        fieldnames,
        active_rows,
    )
    _write_csv(
        os.path.join(output_dynamic_state_dir, "inactive_isls_%d.csv" % time_since_epoch_ns),
        fieldnames,
        inactive_rows,
    )


def export_gsl_decisions(output_dynamic_state_dir, time_since_epoch_ns, rows):
    active_rows = [row for row in rows if row["active"]]
    inactive_rows = [row for row in rows if not row["active"]]
    fieldnames = [
        "time_ns",
        "ground_station_id",
        "sat_id",
        "active",
        "raw_active",
        "event",
        "reason",
        "distance_m",
        "weight",
        "elevation_deg",
        "age_s",
    ]
    _write_csv(
        os.path.join(output_dynamic_state_dir, "active_gsls_%d.csv" % time_since_epoch_ns),
        fieldnames,
        active_rows,
    )
    _write_csv(
        os.path.join(output_dynamic_state_dir, "inactive_gsls_%d.csv" % time_since_epoch_ns),
        fieldnames,
        inactive_rows,
    )


def export_topology_stats(output_dynamic_state_dir, time_since_epoch_ns, isl_rows, gsl_rows, sat_graph):
    active_isls = [row for row in isl_rows if row["active"]]
    active_gsls = [row for row in gsl_rows if row["active"]]
    components = list()
    if sat_graph.number_of_nodes() > 0:
        import networkx as nx
        components = list(nx.connected_components(sat_graph))
    largest_component_size = max([len(component) for component in components], default=0)

    path = os.path.join(output_dynamic_state_dir, "topology_stats.csv")
    exists = os.path.isfile(path)
    fieldnames = [
        "time_ns",
        "candidate_isls",
        "active_isls",
        "isl_births",
        "isl_deaths",
        "candidate_gsls",
        "active_gsls",
        "gsl_births",
        "gsl_deaths",
        "sat_components",
        "largest_sat_component_size",
    ]
    with open(path, "a", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({
            "time_ns": time_since_epoch_ns,
            "candidate_isls": len(isl_rows),
            "active_isls": len(active_isls),
            "isl_births": len([row for row in isl_rows if row["event"] == "birth"]),
            "isl_deaths": len([row for row in isl_rows if row["event"] == "death"]),
            "candidate_gsls": len(gsl_rows),
            "active_gsls": len(active_gsls),
            "gsl_births": len([row for row in gsl_rows if row["event"] == "birth"]),
            "gsl_deaths": len([row for row in gsl_rows if row["event"] == "death"]),
            "sat_components": len(components),
            "largest_sat_component_size": largest_component_size,
        })
