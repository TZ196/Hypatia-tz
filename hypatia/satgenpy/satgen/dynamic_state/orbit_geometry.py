import math

from astropy import units as u
from satgen.distance_tools import geodetic2cartesian


EARTH_RADIUS_M = 6378135.0


def satellite_latitude_deg(satellite, epoch, time):
    satellite.compute(str(time), epoch=str(epoch))
    return math.degrees(satellite.sublat)


def satellite_cartesian_m(satellite, epoch, time):
    satellite.compute(str(time), epoch=str(epoch))
    return geodetic2cartesian(
        math.degrees(satellite.sublat),
        math.degrees(satellite.sublong),
        float(satellite.elevation),
    )


def vector_subtract(a, b):
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def vector_norm(vector):
    return math.sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2)


def vector_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def angle_deg_between(a, b):
    norm_a = vector_norm(a)
    norm_b = vector_norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    dot = vector_dot(a, b)
    cosine = max(-1.0, min(1.0, dot / (norm_a * norm_b)))
    return math.degrees(math.acos(cosine))


def satellite_pair_geometry(sat_a, sat_b, epoch, time):
    pos_a = satellite_cartesian_m(sat_a, epoch, time)
    pos_b = satellite_cartesian_m(sat_b, epoch, time)
    a_to_b = vector_subtract(pos_b, pos_a)
    b_to_a = vector_subtract(pos_a, pos_b)
    pointing_a_deg = angle_deg_between(a_to_b, pos_a)
    pointing_b_deg = angle_deg_between(b_to_a, pos_b)
    return pos_a, pos_b, a_to_b, b_to_a, pointing_a_deg, pointing_b_deg


def satellite_pair_tracking_rate_deg_s(sat_a, sat_b, epoch, time, future_time, sample_s):
    _, _, a_to_b_now, b_to_a_now, _, _ = satellite_pair_geometry(sat_a, sat_b, epoch, time)
    _, _, a_to_b_next, b_to_a_next, _, _ = satellite_pair_geometry(sat_a, sat_b, epoch, future_time)
    if sample_s <= 0:
        return 0.0, 0.0
    return (
        angle_deg_between(a_to_b_now, a_to_b_next) / sample_s,
        angle_deg_between(b_to_a_now, b_to_a_next) / sample_s,
    )


def earth_clearance_m_between_positions(pos_a, pos_b):
    segment = vector_subtract(pos_b, pos_a)
    segment_len_sq = vector_dot(segment, segment)
    if segment_len_sq == 0:
        return vector_norm(pos_a) - EARTH_RADIUS_M
    projection = -vector_dot(pos_a, segment) / segment_len_sq
    projection = max(0.0, min(1.0, projection))
    closest = (
        pos_a[0] + projection * segment[0],
        pos_a[1] + projection * segment[1],
        pos_a[2] + projection * segment[2],
    )
    return vector_norm(closest) - EARTH_RADIUS_M


def satellite_pair_clearance_m(sat_a, sat_b, epoch, time):
    pos_a, pos_b, _, _, _, _ = satellite_pair_geometry(sat_a, sat_b, epoch, time)
    return earth_clearance_m_between_positions(pos_a, pos_b)


def predict_link_duration_s(sat_a, sat_b, epoch, start_time, max_duration_s, sample_step_s,
                            is_link_eligible):
    if max_duration_s <= 0:
        return 0.0
    if sample_step_s <= 0:
        raise ValueError("sample_step_s must be positive")

    elapsed_s = 0.0
    while elapsed_s <= max_duration_s:
        sample_time = start_time + int(elapsed_s * 1e9) * u.ns
        if not is_link_eligible(sat_a, sat_b, epoch, sample_time):
            return elapsed_s
        elapsed_s += sample_step_s
    return max_duration_s


def orbit_position(sat_id, num_sats_per_orbit):
    if num_sats_per_orbit is None or num_sats_per_orbit <= 0:
        return None, None
    return sat_id // num_sats_per_orbit, sat_id % num_sats_per_orbit


def classify_isl_link(a, b, num_orbits=None, num_sats_per_orbit=None):
    orbit_a, index_a = orbit_position(a, num_sats_per_orbit)
    orbit_b, index_b = orbit_position(b, num_sats_per_orbit)
    if orbit_a is None or orbit_b is None:
        return "unknown"

    if orbit_a == orbit_b:
        return "same_orbit"

    if num_orbits is None or num_orbits <= 0:
        return "cross_plane"

    orbit_delta = abs(orbit_a - orbit_b)
    circular_delta = min(orbit_delta, num_orbits - orbit_delta)
    if circular_delta == 1:
        if orbit_delta == num_orbits - 1:
            return "seam_link"
        return "adjacent_orbit"

    return "cross_plane"
