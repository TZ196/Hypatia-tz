from dataclasses import dataclass
import math

import ephem
from astropy import units as u

from satgen.distance_tools import distance_m_between_satellites
from .orbit_geometry import (
    classify_isl_link,
    predict_link_duration_s,
    satellite_latitude_deg,
    satellite_pair_clearance_m,
    satellite_pair_geometry,
    satellite_pair_tracking_rate_deg_s,
)


LIGHT_SPEED_M_PER_S = 299792458.0


@dataclass
class LinkLifecycle:
    active: bool = False
    birth_time_ns: int = None
    death_time_ns: int = None
    last_change_time_ns: int = None
    activation_count: int = 0
    deactivation_count: int = 0
    last_reason: str = "initial"


@dataclass
class LinkDecision:
    active: bool
    raw_active: bool
    event: str
    reason: str
    distance_m: float
    weight: float
    link_type: str = ""
    lat_a_deg: float = None
    lat_b_deg: float = None
    pointing_a_deg: float = None
    pointing_b_deg: float = None
    tracking_rate_a_deg_s: float = None
    tracking_rate_b_deg_s: float = None
    earth_clearance_m: float = None
    predicted_link_duration_s: float = None
    elevation_deg: float = None
    age_s: float = 0.0


def _section(config, name):
    if config is None:
        return {}
    return config.get(name, {}) if isinstance(config, dict) else getattr(config, name, {}) or {}


def _value(section, name, default=None):
    if isinstance(section, dict):
        return section.get(name, default)
    return getattr(section, name, default)


def _bool_value(section, name, default):
    value = _value(section, name, default)
    return default if value is None else bool(value)


def dynamic_topology_enabled(config):
    if config is None:
        return False
    general = _section(config, "general")
    return _bool_value(general, "enabled", True)


def continuity_enabled(config):
    if not dynamic_topology_enabled(config):
        return False
    continuity = _section(config, "continuity")
    return _bool_value(continuity, "enabled", True)


def _lat_allowed(lat_deg, max_abs_latitude_deg):
    return max_abs_latitude_deg is None or abs(lat_deg) <= max_abs_latitude_deg


def _isl_latitude_limit_for_link_type(isl_config, link_type):
    if link_type == "same_orbit":
        return _value(
            isl_config,
            "same_orbit_max_abs_latitude_deg",
            _value(isl_config, "intra_plane_max_abs_latitude_deg")
        )
    if link_type == "adjacent_orbit":
        return _value(
            isl_config,
            "adjacent_orbit_max_abs_latitude_deg",
            _value(isl_config, "inter_plane_max_abs_latitude_deg")
        )
    if link_type == "seam_link":
        return _value(
            isl_config,
            "seam_max_abs_latitude_deg",
            _value(isl_config, "inter_plane_max_abs_latitude_deg")
        )
    if link_type == "cross_plane":
        return _value(
            isl_config,
            "cross_plane_max_abs_latitude_deg",
            _value(isl_config, "inter_plane_max_abs_latitude_deg")
        )
    return _value(isl_config, "max_abs_latitude_deg")


def _is_inter_plane_link(link_type):
    return link_type in ("adjacent_orbit", "seam_link", "cross_plane")


def _list_value(section, name, default=None):
    value = _value(section, name, default)
    if value is None:
        return default
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


def _base_route_weight(distance_m, mode):
    if mode == "delay_s":
        return distance_m / LIGHT_SPEED_M_PER_S
    if mode == "delay_ms":
        return distance_m / LIGHT_SPEED_M_PER_S * 1000.0
    return distance_m


def _compute_stability_aware_weight(distance_m, link_type, tracking_rate_a_deg_s,
                                    tracking_rate_b_deg_s, predicted_duration_s,
                                    age_s, config):
    routing_config = _section(config, "routing")
    isl_config = _section(config, "isl")

    base_metric = _value(routing_config, "base_metric", "delay_ms")
    base_weight = _base_route_weight(distance_m, base_metric)
    apply_to = _list_value(
        routing_config,
        "apply_to_link_types",
        ["adjacent_orbit", "seam_link", "cross_plane"],
    )
    if link_type not in apply_to:
        return base_weight

    lambda_value = float(_value(routing_config, "lambda", 1.0) or 0.0)
    geometry_alpha = float(_value(routing_config, "geometry_alpha", 1.0) or 0.0)
    temporal_beta = float(_value(routing_config, "temporal_beta", 2.0) or 0.0)
    initialization_gamma = float(_value(routing_config, "initialization_gamma", 0.5) or 0.0)

    tracking_scale = _value(
        routing_config,
        "tracking_rate_scale_deg_s",
        _value(isl_config, "max_tracking_rate_deg_s"),
    )
    geometry_risk = 0.0
    if tracking_scale is not None and float(tracking_scale) > 0.0:
        tracking_values = [
            v for v in (tracking_rate_a_deg_s, tracking_rate_b_deg_s)
            if v is not None
        ]
        if tracking_values:
            geometry_risk = _clamp(max(tracking_values) / float(tracking_scale), 0.0, 1.0)

    tau_duration_s = float(_value(routing_config, "tau_duration_s", 60.0) or 60.0)
    temporal_risk = 0.0
    if predicted_duration_s is not None and tau_duration_s > 0.0:
        temporal_risk = math.exp(-float(predicted_duration_s) / tau_duration_s)

    tau_warmup_s = float(_value(routing_config, "tau_warmup_s", 30.0) or 30.0)
    initialization_risk = 0.0
    if tau_warmup_s > 0.0:
        initialization_risk = math.exp(-float(age_s or 0.0) / tau_warmup_s)

    instability_score = (
        geometry_alpha * geometry_risk
        + temporal_beta * temporal_risk
        + initialization_gamma * initialization_risk
    )
    return base_weight * (1.0 + lambda_value * instability_score)


def compute_isl_route_weight(distance_m, link_type, tracking_rate_a_deg_s,
                             tracking_rate_b_deg_s, predicted_duration_s,
                             age_s, config):
    routing_config = _section(config, "routing")
    isl_config = _section(config, "isl")
    weight_mode = _value(
        routing_config,
        "weight_mode",
        _value(isl_config, "weight", "distance"),
    )
    if weight_mode in ("distance", "distance_only"):
        return distance_m
    if weight_mode in ("delay_s", "delay_ms"):
        return _base_route_weight(distance_m, weight_mode)
    if weight_mode == "stability_aware":
        return _compute_stability_aware_weight(
            distance_m,
            link_type,
            tracking_rate_a_deg_s,
            tracking_rate_b_deg_s,
            predicted_duration_s,
            age_s,
            config,
        )
    raise ValueError("Unsupported ISL routing weight mode: %s" % weight_mode)


def _finite_or_none(value):
    if value is None:
        return None
    return float(value)


def _edge_key(a, b):
    return tuple(sorted((a, b)))


def _node_edge_key(ground_station_id, satellite_id):
    return ground_station_id, satellite_id


def _duration_s(start_time_ns, time_since_epoch_ns):
    if start_time_ns is None:
        return 0.0
    return (time_since_epoch_ns - start_time_ns) / 1e9


def _apply_continuity(edge_key, raw_active, hard_failure, reason, time_since_epoch_ns,
                      state_by_edge, config):
    continuity = _section(config, "continuity")
    min_up_time_s = float(_value(continuity, "min_up_time_s", 0.0) or 0.0)
    min_down_time_s = float(_value(continuity, "min_down_time_s", 0.0) or 0.0)

    state = state_by_edge.get(edge_key, LinkLifecycle())
    previous_active = state.active
    final_active = raw_active
    final_reason = reason

    if previous_active and not raw_active and not hard_failure:
        active_duration_s = _duration_s(state.birth_time_ns, time_since_epoch_ns)
        if active_duration_s < min_up_time_s:
            final_active = True
            final_reason = "held_by_min_up_time"

    if not previous_active and raw_active:
        down_duration_s = _duration_s(state.death_time_ns, time_since_epoch_ns)
        if state.death_time_ns is not None and down_duration_s < min_down_time_s:
            final_active = False
            final_reason = "blocked_by_min_down_time"

    if not previous_active and final_active:
        event = "birth"
        state.active = True
        state.birth_time_ns = time_since_epoch_ns
        state.last_change_time_ns = time_since_epoch_ns
        state.activation_count += 1
    elif previous_active and not final_active:
        event = "death"
        state.active = False
        state.death_time_ns = time_since_epoch_ns
        state.last_change_time_ns = time_since_epoch_ns
        state.deactivation_count += 1
    elif final_active:
        event = "persist"
    else:
        event = "remain_inactive"

    state.last_reason = final_reason
    state_by_edge[edge_key] = state
    active_start = state.birth_time_ns if state.active else state.death_time_ns
    return final_active, event, final_reason, _duration_s(active_start, time_since_epoch_ns)


def evaluate_isl(a, b, epoch, time, time_since_epoch_ns, satellites, max_isl_length_m,
                 config, state_by_edge):
    isl_config = _section(config, "isl")
    continuity_config = _section(config, "continuity")
    num_orbits = _value(isl_config, "num_orbits")
    num_sats_per_orbit = _value(isl_config, "num_sats_per_orbit")
    link_type = classify_isl_link(a, b, num_orbits, num_sats_per_orbit)

    distance_m = distance_m_between_satellites(satellites[a], satellites[b], str(epoch), str(time))
    lat_a_deg = satellite_latitude_deg(satellites[a], epoch, time)
    lat_b_deg = satellite_latitude_deg(satellites[b], epoch, time)
    _, _, _, _, pointing_a_deg, pointing_b_deg = satellite_pair_geometry(satellites[a], satellites[b], epoch, time)
    earth_clearance_m = satellite_pair_clearance_m(satellites[a], satellites[b], epoch, time)
    tracking_rate_a_deg_s = None
    tracking_rate_b_deg_s = None
    predicted_duration_s = None

    tracking_sample_ms = float(_value(isl_config, "tracking_sample_ms", 1000.0) or 1000.0)
    max_tracking_rate_deg_s = _value(isl_config, "max_tracking_rate_deg_s")
    compute_tracking_rate = _bool_value(isl_config, "compute_tracking_rate", False)
    routing_config = _section(config, "routing")
    routing_weight_mode = _value(routing_config, "weight_mode", _value(isl_config, "weight", "distance"))
    stability_aware_routing = routing_weight_mode == "stability_aware"
    if max_tracking_rate_deg_s is not None or compute_tracking_rate or stability_aware_routing:
        sample_s = tracking_sample_ms / 1000.0
        future_time = time + int(tracking_sample_ms * 1000000) * u.ns
        tracking_rate_a_deg_s, tracking_rate_b_deg_s = satellite_pair_tracking_rate_deg_s(
            satellites[a],
            satellites[b],
            epoch,
            time,
            future_time,
            sample_s,
        )

    previous_state = state_by_edge.get(_edge_key(a, b), LinkLifecycle())
    activate_ratio = float(_value(continuity_config, "activate_distance_ratio", 1.0) or 1.0)
    deactivate_ratio = float(_value(continuity_config, "deactivate_distance_ratio", 1.0) or 1.0)
    distance_ratio = deactivate_ratio if previous_state.active else activate_ratio
    distance_threshold_m = max_isl_length_m * distance_ratio

    raw_active = True
    reason = "active"
    hard_failure = False

    if distance_m > distance_threshold_m:
        raw_active = False
        reason = "distance_exceeded"
        hard_failure = distance_m > max_isl_length_m * deactivate_ratio

    min_earth_clearance_m = _value(isl_config, "min_earth_clearance_m")
    if raw_active and min_earth_clearance_m is not None and earth_clearance_m < float(min_earth_clearance_m):
        raw_active = False
        reason = "earth_blocked"
        hard_failure = True

    max_abs_latitude_deg = _isl_latitude_limit_for_link_type(isl_config, link_type)
    if raw_active and (not _lat_allowed(lat_a_deg, max_abs_latitude_deg)
                       or not _lat_allowed(lat_b_deg, max_abs_latitude_deg)):
        raw_active = False
        if _is_inter_plane_link(link_type):
            reason = "inter_plane_latitude_blocked"
        else:
            reason = "latitude_blocked"
        hard_failure = True

    enable_near_max_latitude_block = _bool_value(isl_config, "enable_near_max_latitude_inter_plane_block", False)
    inclination_degree = _value(isl_config, "inclination_degree")
    near_max_margin_deg = _value(isl_config, "near_max_latitude_margin_deg", 5.0)
    crossing_plane_limit_deg = _value(isl_config, "crossing_plane_max_abs_latitude_deg")
    if enable_near_max_latitude_block and inclination_degree is not None:
        crossing_plane_limit_deg = float(inclination_degree) - float(near_max_margin_deg)
    if raw_active and _is_inter_plane_link(link_type) and crossing_plane_limit_deg is not None:
        if abs(lat_a_deg) > float(crossing_plane_limit_deg) or abs(lat_b_deg) > float(crossing_plane_limit_deg):
            raw_active = False
            reason = "near_max_latitude_blocked"
            hard_failure = True

    max_pointing_angle_deg = _value(isl_config, "max_pointing_angle_from_zenith_deg")
    if raw_active and max_pointing_angle_deg is not None:
        if pointing_a_deg > float(max_pointing_angle_deg) or pointing_b_deg > float(max_pointing_angle_deg):
            raw_active = False
            reason = "pointing_angle_blocked"
            hard_failure = True

    if raw_active and max_tracking_rate_deg_s is not None:
        max_tracking = max(tracking_rate_a_deg_s, tracking_rate_b_deg_s)
        if max_tracking > float(max_tracking_rate_deg_s):
            raw_active = False
            reason = "tracking_rate_blocked"
            hard_failure = False

    min_inter_plane_duration_s = _value(isl_config, "min_inter_plane_link_duration_s")
    needs_duration_for_routing = stability_aware_routing and _is_inter_plane_link(link_type)
    if raw_active and _is_inter_plane_link(link_type) and (
        min_inter_plane_duration_s is not None or needs_duration_for_routing
    ):
        duration_scan_step_s = float(_value(isl_config, "duration_scan_step_s", 15.0) or 15.0)
        routing_duration_horizon_s = _value(
            routing_config,
            "duration_prediction_horizon_s",
            _value(routing_config, "tau_duration_s", 60.0),
        )
        default_max_duration_s = min_inter_plane_duration_s
        if default_max_duration_s is None:
            default_max_duration_s = routing_duration_horizon_s
        max_duration_s = float(_value(isl_config, "duration_scan_max_s", default_max_duration_s)
                               or default_max_duration_s)

        def is_sample_eligible(sample_sat_a, sample_sat_b, sample_epoch, sample_time):
            sample_distance_m = distance_m_between_satellites(sample_sat_a, sample_sat_b, str(sample_epoch), str(sample_time))
            if sample_distance_m > max_isl_length_m:
                return False
            if min_earth_clearance_m is not None:
                sample_clearance_m = satellite_pair_clearance_m(sample_sat_a, sample_sat_b, sample_epoch, sample_time)
                if sample_clearance_m < float(min_earth_clearance_m):
                    return False
            return True

        predicted_duration_s = predict_link_duration_s(
            satellites[a],
            satellites[b],
            epoch,
            time,
            max_duration_s,
            duration_scan_step_s,
            is_sample_eligible,
        )
        if min_inter_plane_duration_s is not None and predicted_duration_s < float(min_inter_plane_duration_s):
            raw_active = False
            reason = "short_predicted_duration"
            hard_failure = False

    allow_same = _bool_value(isl_config, "allow_same_orbit", True)
    allow_adjacent = _bool_value(isl_config, "allow_adjacent_orbit", True)
    allow_seam = _bool_value(isl_config, "allow_seam_links", True)
    allow_cross = _bool_value(isl_config, "allow_cross_plane", False)
    if raw_active:
        blocked = (
            (link_type == "same_orbit" and not allow_same)
            or (link_type == "adjacent_orbit" and not allow_adjacent)
            or (link_type == "seam_link" and not allow_seam)
            or (link_type == "cross_plane" and not allow_cross)
        )
        if blocked:
            raw_active = False
            reason = "orbit_relation_blocked"
            hard_failure = True

    active, event, reason, age_s = _apply_continuity(
        _edge_key(a, b),
        raw_active,
        hard_failure,
        reason,
        time_since_epoch_ns,
        state_by_edge,
        config
    )

    weight = compute_isl_route_weight(
        distance_m,
        link_type,
        tracking_rate_a_deg_s,
        tracking_rate_b_deg_s,
        predicted_duration_s,
        age_s,
        config,
    )
    return LinkDecision(
        active=active,
        raw_active=raw_active,
        event=event,
        reason=reason,
        distance_m=distance_m,
        weight=weight,
        link_type=link_type,
        lat_a_deg=lat_a_deg,
        lat_b_deg=lat_b_deg,
        pointing_a_deg=pointing_a_deg,
        pointing_b_deg=pointing_b_deg,
        tracking_rate_a_deg_s=tracking_rate_a_deg_s,
        tracking_rate_b_deg_s=tracking_rate_b_deg_s,
        earth_clearance_m=earth_clearance_m,
        predicted_link_duration_s=predicted_duration_s,
        age_s=age_s,
    )


def evaluate_gsl(ground_station, satellite_id, satellite, epoch, time, time_since_epoch_ns,
                 max_gsl_length_m, config, state_by_edge):
    gsl_config = _section(config, "gsl")
    observer = ephem.Observer()
    observer.epoch = str(epoch)
    observer.date = str(time)
    observer.lat = str(ground_station["latitude_degrees_str"])
    observer.lon = str(ground_station["longitude_degrees_str"])
    observer.elevation = ground_station["elevation_m_float"]
    satellite.compute(observer)

    distance_m = satellite.range
    elevation_deg = math.degrees(satellite.alt)
    max_distance_m = float(_value(gsl_config, "max_gsl_length_m", max_gsl_length_m) or max_gsl_length_m)
    min_elevation_deg = _value(gsl_config, "min_elevation_deg")

    raw_active = True
    reason = "active"
    hard_failure = False
    if distance_m > max_distance_m:
        raw_active = False
        reason = "distance_exceeded"
        hard_failure = True
    if raw_active and min_elevation_deg is not None and elevation_deg < float(min_elevation_deg):
        raw_active = False
        reason = "elevation_blocked"
        hard_failure = True

    ground_station_node_id = ground_station["gid"]
    active, event, reason, age_s = _apply_continuity(
        _node_edge_key(ground_station_node_id, satellite_id),
        raw_active,
        hard_failure,
        reason,
        time_since_epoch_ns,
        state_by_edge,
        config
    )

    weight_mode = _value(gsl_config, "weight", "distance")
    weight = distance_m / LIGHT_SPEED_M_PER_S if weight_mode == "delay_s" else distance_m
    return LinkDecision(
        active=active,
        raw_active=raw_active,
        event=event,
        reason=reason,
        distance_m=distance_m,
        weight=weight,
        link_type="gsl",
        elevation_deg=elevation_deg,
        age_s=age_s,
    )


def apply_gsl_access_limit(ground_station_id, satellite_id, time_since_epoch_ns, state_by_edge):
    edge_key = _node_edge_key(ground_station_id, satellite_id)
    state = state_by_edge.get(edge_key, LinkLifecycle())
    previous_active = state.active
    state.active = False
    state.last_reason = "access_limit"
    if previous_active:
        state.death_time_ns = time_since_epoch_ns
        state.last_change_time_ns = time_since_epoch_ns
        state.deactivation_count += 1
        event = "death"
    else:
        event = "remain_inactive"
    state_by_edge[edge_key] = state
    inactive_start = state.death_time_ns
    return event, _duration_s(inactive_start, time_since_epoch_ns)
