# The MIT License (MIT)
#
# Copyright (c) 2020 ETH Zurich
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from satgen.distance_tools import *
from astropy import units as u
import math
import networkx as nx
import numpy as np
from .algorithm_free_one_only_gs_relays import algorithm_free_one_only_gs_relays
from .algorithm_free_one_only_over_isls import algorithm_free_one_only_over_isls
from .algorithm_paired_many_only_over_isls import algorithm_paired_many_only_over_isls
from .algorithm_free_gs_one_sat_many_only_over_isls import algorithm_free_gs_one_sat_many_only_over_isls
from .link_policies import (
    apply_gsl_access_limit,
    dynamic_topology_enabled,
    evaluate_gsl,
    evaluate_isl,
)
from .route_export import export_route_paths
from .topology_export import export_gsl_decisions, export_isl_decisions, export_topology_stats


def generate_dynamic_state(
        output_dynamic_state_dir,
        epoch,
        simulation_end_time_ns,
        time_step_ns,
        offset_ns,
        satellites,
        ground_stations,
        list_isls,
        list_gsl_interfaces_info,
        max_gsl_length_m,
        max_isl_length_m,
        dynamic_state_algorithm,  # Options:
                                  # "algorithm_free_one_only_gs_relays"
                                  # "algorithm_free_one_only_over_isls"
                                  # "algorithm_paired_many_only_over_isls"
        enable_verbose_logs,
        dynamic_state_config=None
):
    if offset_ns % time_step_ns != 0:
        raise ValueError("Offset must be a multiple of time_step_ns")
    prev_output = None
    i = 0
    total_iterations = ((simulation_end_time_ns - offset_ns) / time_step_ns)
    progress_interval = max(1, int(math.floor(total_iterations) / 10.0))
    for time_since_epoch_ns in range(offset_ns, simulation_end_time_ns, time_step_ns):
        if not enable_verbose_logs:
            if i % progress_interval == 0:
                print("Progress: calculating for T=%d (time step granularity is still %d ms)" % (
                    time_since_epoch_ns, time_step_ns / 1000000
                ))
            i += 1
        prev_output = generate_dynamic_state_at(
            output_dynamic_state_dir,
            epoch,
            time_since_epoch_ns,
            satellites,
            ground_stations,
            list_isls,
            list_gsl_interfaces_info,
            max_gsl_length_m,
            max_isl_length_m,
            dynamic_state_algorithm,
            prev_output,
            enable_verbose_logs,
            dynamic_state_config
        )


def generate_dynamic_state_at(
        output_dynamic_state_dir,
        epoch,
        time_since_epoch_ns,
        satellites,
        ground_stations,
        list_isls,
        list_gsl_interfaces_info,
        max_gsl_length_m,
        max_isl_length_m,
        dynamic_state_algorithm,
        prev_output,
        enable_verbose_logs,
        dynamic_state_config=None
):
    if enable_verbose_logs:
        print("FORWARDING STATE AT T = " + (str(time_since_epoch_ns))
              + "ns (= " + str(time_since_epoch_ns / 1e9) + " seconds)")

    #################################

    if enable_verbose_logs:
        print("\nBASIC INFORMATION")

    # Time
    time = epoch + time_since_epoch_ns * u.ns
    if enable_verbose_logs:
        print("  > Epoch.................. " + str(epoch))
        print("  > Time since epoch....... " + str(time_since_epoch_ns) + " ns")
        print("  > Absolute time.......... " + str(time))

    # Graphs
    sat_net_graph_only_satellites_with_isls = nx.Graph()
    sat_net_graph_all_with_only_gsls = nx.Graph()
    sat_net_graph_with_active_links = nx.Graph()

    # Information
    for i in range(len(satellites)):
        sat_net_graph_only_satellites_with_isls.add_node(i)
        sat_net_graph_all_with_only_gsls.add_node(i)
    for i in range(len(satellites) + len(ground_stations)):
        sat_net_graph_all_with_only_gsls.add_node(i)
        sat_net_graph_with_active_links.add_node(i)
    if enable_verbose_logs:
        print("  > Satellites............. " + str(len(satellites)))
        print("  > Ground stations........ " + str(len(ground_stations)))
        print("  > Max. range GSL......... " + str(max_gsl_length_m) + "m")
        print("  > Max. range ISL......... " + str(max_isl_length_m) + "m")

    #################################

    if enable_verbose_logs:
        print("\nISL INFORMATION")

    # ISL edges
    total_num_isls = 0
    active_num_isls = 0
    num_isls_per_sat = [0] * len(satellites)
    sat_neighbor_to_if = {}
    isl_policy_state = {}
    gsl_policy_state = {}
    prev_route_paths = {}
    if prev_output:
        isl_policy_state = prev_output.get("isl_policy_state", {})
        gsl_policy_state = prev_output.get("gsl_policy_state", {})
        prev_route_paths = prev_output.get("route_paths", {})
    isl_rows = []
    for (a, b) in list_isls:

        # Interface mapping must include every configured ISL, even if it is
        # currently out of range. ns-3 creates NetDevices for the static
        # isls.txt list, while the forwarding graph only uses links valid at
        # this time step.
        sat_neighbor_to_if[(a, b)] = num_isls_per_sat[a]
        sat_neighbor_to_if[(b, a)] = num_isls_per_sat[b]
        num_isls_per_sat[a] += 1
        num_isls_per_sat[b] += 1
        total_num_isls += 1

        if dynamic_topology_enabled(dynamic_state_config):
            decision = evaluate_isl(
                a,
                b,
                epoch,
                time,
                time_since_epoch_ns,
                satellites,
                max_isl_length_m,
                dynamic_state_config,
                isl_policy_state,
            )
            sat_distance_m = decision.distance_m
            edge_weight = decision.weight
            isl_rows.append({
                "time_ns": time_since_epoch_ns,
                "src_sat": a,
                "dst_sat": b,
                "active": decision.active,
                "raw_active": decision.raw_active,
                "event": decision.event,
                "reason": decision.reason,
                "distance_m": decision.distance_m,
                "weight": decision.weight,
                "link_type": decision.link_type,
                "lat_src_deg": decision.lat_a_deg,
                "lat_dst_deg": decision.lat_b_deg,
                "pointing_src_deg": decision.pointing_a_deg,
                "pointing_dst_deg": decision.pointing_b_deg,
                "tracking_rate_src_deg_s": decision.tracking_rate_a_deg_s,
                "tracking_rate_dst_deg_s": decision.tracking_rate_b_deg_s,
                "earth_clearance_m": decision.earth_clearance_m,
                "predicted_link_duration_s": decision.predicted_link_duration_s,
                "age_s": decision.age_s,
            })
            if not decision.active:
                continue
        else:
            # Only active ISLs are added to the routing graph.
            sat_distance_m = distance_m_between_satellites(satellites[a], satellites[b], str(epoch), str(time))
            if sat_distance_m > max_isl_length_m:
                continue
            edge_weight = sat_distance_m

        # Add to networkx graph
        sat_net_graph_only_satellites_with_isls.add_edge(
            a, b, weight=edge_weight, distance_m=sat_distance_m
        )
        sat_net_graph_with_active_links.add_edge(
            a, b, weight=edge_weight, distance_m=sat_distance_m
        )
        active_num_isls += 1

    if enable_verbose_logs:
        print("  > Total ISLs............. " + str(total_num_isls))
        print("  > Active ISLs............ " + str(active_num_isls))
        print("  > Min. ISLs/satellite.... " + str(np.min(num_isls_per_sat)))
        print("  > Max. ISLs/satellite.... " + str(np.max(num_isls_per_sat)))

    #################################

    if enable_verbose_logs:
        print("\nGSL INTERFACE INFORMATION")

    satellite_gsl_if_count_list = list(map(
        lambda x: x["number_of_interfaces"],
        list_gsl_interfaces_info[0:len(satellites)]
    ))
    ground_station_gsl_if_count_list = list(map(
        lambda x: x["number_of_interfaces"],
        list_gsl_interfaces_info[len(satellites):(len(satellites) + len(ground_stations))]
    ))
    if enable_verbose_logs:
        print("  > Min. GSL IFs/satellite........ " + str(np.min(satellite_gsl_if_count_list)))
        print("  > Max. GSL IFs/satellite........ " + str(np.max(satellite_gsl_if_count_list)))
        print("  > Min. GSL IFs/ground station... " + str(np.min(ground_station_gsl_if_count_list)))
        print("  > Max. GSL IFs/ground_station... " + str(np.max(ground_station_gsl_if_count_list)))

    #################################

    if enable_verbose_logs:
        print("\nGSL IN-RANGE INFORMATION")

    # What satellites can a ground station see
    ground_station_satellites_in_range = []
    gsl_rows = []
    gsl_config = {}
    if isinstance(dynamic_state_config, dict):
        gsl_config = dynamic_state_config.get("gsl", {})
    for ground_station in ground_stations:
        # Find satellites in range
        satellites_in_range = []
        per_ground_station_rows = []
        for sid in range(len(satellites)):
            if dynamic_topology_enabled(dynamic_state_config):
                decision = evaluate_gsl(
                    ground_station,
                    sid,
                    satellites[sid],
                    epoch,
                    time,
                    time_since_epoch_ns,
                    max_gsl_length_m,
                    dynamic_state_config,
                    gsl_policy_state,
                )
                row = {
                    "time_ns": time_since_epoch_ns,
                    "ground_station_id": ground_station["gid"],
                    "sat_id": sid,
                    "active": decision.active,
                    "raw_active": decision.raw_active,
                    "event": decision.event,
                    "reason": decision.reason,
                    "distance_m": decision.distance_m,
                    "weight": decision.weight,
                    "elevation_deg": decision.elevation_deg,
                    "age_s": decision.age_s,
                }
                per_ground_station_rows.append(row)
            else:
                distance_m = distance_m_ground_station_to_satellite(
                    ground_station,
                    satellites[sid],
                    str(epoch),
                    str(time)
                )
                row = {
                    "time_ns": time_since_epoch_ns,
                    "ground_station_id": ground_station["gid"],
                    "sat_id": sid,
                    "active": distance_m <= max_gsl_length_m,
                    "raw_active": distance_m <= max_gsl_length_m,
                    "event": "",
                    "reason": "active" if distance_m <= max_gsl_length_m else "distance_exceeded",
                    "distance_m": distance_m,
                    "weight": distance_m,
                    "elevation_deg": "",
                    "age_s": "",
                }
                per_ground_station_rows.append(row)

        max_active_sats = gsl_config.get("max_active_satellites_per_ground_station")
        if dynamic_topology_enabled(dynamic_state_config) and max_active_sats is not None:
            active_rows = [row for row in per_ground_station_rows if row["active"]]
            access_metric = gsl_config.get("access_selection_metric", "distance")
            reverse = access_metric == "elevation"
            sort_key = "elevation_deg" if access_metric == "elevation" else "distance_m"
            selected = set(
                row["sat_id"] for row in sorted(active_rows, key=lambda r: r[sort_key], reverse=reverse)[
                    0:int(max_active_sats)
                ]
            )
            for row in per_ground_station_rows:
                if row["active"] and row["sat_id"] not in selected:
                    event, age_s = apply_gsl_access_limit(
                        row["ground_station_id"],
                        row["sat_id"],
                        time_since_epoch_ns,
                        gsl_policy_state,
                    )
                    row["active"] = False
                    row["event"] = event
                    row["reason"] = "access_limit"
                    row["age_s"] = age_s

        for row in per_ground_station_rows:
            gsl_rows.append(row)
            if row["active"]:
                satellites_in_range.append((row["weight"], row["sat_id"]))
                gs_node_id = len(satellites) + ground_station["gid"]
                sat_net_graph_all_with_only_gsls.add_edge(
                    row["sat_id"], gs_node_id, weight=row["weight"], distance_m=row["distance_m"]
                )
                sat_net_graph_with_active_links.add_edge(
                    row["sat_id"], gs_node_id, weight=row["weight"], distance_m=row["distance_m"]
                )

        ground_station_satellites_in_range.append(satellites_in_range)

    # Print how many are in range
    ground_station_num_in_range = list(map(lambda x: len(x), ground_station_satellites_in_range))
    if enable_verbose_logs:
        print("  > Min. satellites in range... " + str(np.min(ground_station_num_in_range)))
        print("  > Max. satellites in range... " + str(np.max(ground_station_num_in_range)))

    #################################

    #
    # Call the dynamic state algorithm which:
    #
    # (a) Output the gsl_if_bandwidth_<t>.txt files
    # (b) Output the fstate_<t>.txt files
    #
    if dynamic_state_algorithm == "algorithm_free_one_only_over_isls":

        algorithm_output = algorithm_free_one_only_over_isls(
            output_dynamic_state_dir,
            time_since_epoch_ns,
            satellites,
            ground_stations,
            sat_net_graph_only_satellites_with_isls,
            ground_station_satellites_in_range,
            num_isls_per_sat,
            sat_neighbor_to_if,
            list_gsl_interfaces_info,
            prev_output,
            enable_verbose_logs
        )

    elif dynamic_state_algorithm == "algorithm_free_gs_one_sat_many_only_over_isls":

        algorithm_output = algorithm_free_gs_one_sat_many_only_over_isls(
            output_dynamic_state_dir,
            time_since_epoch_ns,
            satellites,
            ground_stations,
            sat_net_graph_only_satellites_with_isls,
            ground_station_satellites_in_range,
            num_isls_per_sat,
            sat_neighbor_to_if,
            list_gsl_interfaces_info,
            prev_output,
            enable_verbose_logs
        )

    elif dynamic_state_algorithm == "algorithm_free_one_only_gs_relays":

        algorithm_output = algorithm_free_one_only_gs_relays(
            output_dynamic_state_dir,
            time_since_epoch_ns,
            satellites,
            ground_stations,
            sat_net_graph_all_with_only_gsls,
            num_isls_per_sat,
            list_gsl_interfaces_info,
            prev_output,
            enable_verbose_logs
        )

    elif dynamic_state_algorithm == "algorithm_paired_many_only_over_isls":

        algorithm_output = algorithm_paired_many_only_over_isls(
            output_dynamic_state_dir,
            time_since_epoch_ns,
            satellites,
            ground_stations,
            sat_net_graph_only_satellites_with_isls,
            ground_station_satellites_in_range,
            num_isls_per_sat,
            sat_neighbor_to_if,
            list_gsl_interfaces_info,
            prev_output,
            enable_verbose_logs
        )

    else:
        raise ValueError("Unknown dynamic state algorithm: " + str(dynamic_state_algorithm))

    if dynamic_topology_enabled(dynamic_state_config):
        export_isl_decisions(output_dynamic_state_dir, time_since_epoch_ns, isl_rows)
        export_gsl_decisions(output_dynamic_state_dir, time_since_epoch_ns, gsl_rows)
        export_topology_stats(
            output_dynamic_state_dir,
            time_since_epoch_ns,
            isl_rows,
            gsl_rows,
            sat_net_graph_only_satellites_with_isls,
        )
        route_paths = export_route_paths(
            output_dynamic_state_dir,
            time_since_epoch_ns,
            algorithm_output["fstate"],
            prev_route_paths,
            sat_net_graph_with_active_links,
            len(satellites),
            len(ground_stations),
        )
        algorithm_output["isl_policy_state"] = isl_policy_state
        algorithm_output["gsl_policy_state"] = gsl_policy_state
        algorithm_output["route_paths"] = route_paths

    return algorithm_output
