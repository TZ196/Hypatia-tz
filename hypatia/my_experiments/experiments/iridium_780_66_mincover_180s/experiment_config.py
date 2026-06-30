"""Configuration for the Iridium-780 66-satellite biased stable-routing experiment."""

from pathlib import Path


EXPERIMENT_DIR = Path(__file__).resolve().parent
EXPERIMENT_NAME = EXPERIMENT_DIR.name
EXPERIMENTS_DIR = EXPERIMENT_DIR.parent
MY_EXPERIMENTS_DIR = EXPERIMENTS_DIR.parent
HYPATIA_DIR = MY_EXPERIMENTS_DIR.parent

INPUT_DIR = EXPERIMENT_DIR / "input"
GEN_DATA_ROOT = EXPERIMENT_DIR / "gen_data"
RUNS_DIR = EXPERIMENT_DIR / "runs"
LOGS_DIR = EXPERIMENT_DIR / "logs"

GROUND_STATION_SELECTION_MODE = "satellite_anchored"
GROUND_STATION_RANDOM_SEED = 123456789
GROUND_STATION_ANCHOR_TIME_NS = 0
GROUND_STATION_ANCHOR_JITTER_KM = 700
GROUND_STATIONS_FILE = INPUT_DIR / "ground_stations.basic.txt"
GROUND_STATIONS_MANIFEST = INPUT_DIR / "ground_stations_manifest.csv"
TRAFFIC_SCHEDULE_FILE = INPUT_DIR / "schedule.csv"
TRAFFIC_DESIGN_FILE = INPUT_DIR / "traffic_design.txt"
TRAFFIC_MATRIX_FILE = INPUT_DIR / "traffic_matrix_bytes.csv"
TRAFFIC_ACTIVITY_FILE = INPUT_DIR / "station_activity.csv"
TRAFFIC_FLOW_DETAILS_FILE = INPUT_DIR / "traffic_flow_details.csv"

SATELLITE_NETWORK = "iridium_780_66"
DURATION_S = 180
TIME_STEP_MS = 1000
ISL_MODE = "isls_plus_grid"
GS_SELECTION = "gs66_scale001"
ROUTING_ALGORITHM = "algorithm_free_one_only_over_isls"

NUM_SATELLITES = 66
NUM_ORBITS = 6
NUM_SATS_PER_ORBIT = 11
NUM_GROUND_STATIONS = 66
GS_START_NODE_ID = NUM_SATELLITES
ISL_SHIFT = 0

# Biased stable routing:
# - keep the dynamic topology/stability filters enabled;
# - use consistent distance units for ISL and GSL weights;
# - scale ISL route cost down to 1% so the route planner is willing to take
#   longer satellite detours when that helps path-pair coverage.
DYNAMIC_STATE_CONFIG = {
    "general": {
        "enabled": True,
    },
    "continuity": {
        "enabled": True,
        "min_up_time_s": 10.0,
        "min_down_time_s": 10.0,
        "activate_distance_ratio": 0.98,
        "deactivate_distance_ratio": 1.0,
    },
    "isl": {
        "num_orbits": NUM_ORBITS,
        "num_sats_per_orbit": NUM_SATS_PER_ORBIT,
        "inclination_degree": 86.4,
        "allow_same_orbit": True,
        "allow_adjacent_orbit": True,
        "allow_seam_links": True,
        "allow_cross_plane": False,
        "compute_tracking_rate": True,
        "tracking_sample_ms": 1000.0,
        "duration_scan_step_s": 5.0,
    },
    "routing": {
        "weight_mode": "stability_aware",
        "base_metric": "distance",
        "isl_weight_scale": 0.01,
        "lambda": 1.0,
        "geometry_alpha": 1.0,
        "temporal_beta": 2.0,
        "initialization_gamma": 0.5,
        "tau_duration_s": 60.0,
        "tau_warmup_s": 30.0,
        "duration_prediction_horizon_s": 60.0,
        "apply_to_link_types": ["adjacent_orbit", "seam_link", "cross_plane"],
    },
    "gsl": {
        "weight": "distance",
        "weight_scale": 1.0,
    },
}

# Min-cover traffic is generated from the biased stable forwarding state.
# Repeated source/destination pairs are merged to keep the TCP flow count small
# while preserving the selected coverage demand in each pair's total size.
TRAFFIC_PAIR_MODE = "satellite_pair_min_cover"
TRAFFIC_MIN_COVER_TARGET_COVERAGE = 0.90
TRAFFIC_MIN_COVER_MERGE_SAME_PAIR = True
TRAFFIC_MIN_COVER_MAX_CANDIDATES = None
TRAFFIC_MIN_COVER_MAX_FLOWS_PER_SLICE = None
TRAFFIC_SEED = 123456789
TRAFFIC_REFERENCE_UTC_HOUR = 0
TRAFFIC_FLOW_SIZE_BYTES = 2_000_000
TRAFFIC_TIMEZONE_SIZE_ENABLED = True
TRAFFIC_TIMEZONE_SIZE_PAIR_MODE = "average"
TRAFFIC_TIMEZONE_SIZE_MIN_MULTIPLIER = 0.25
TRAFFIC_TIMEZONE_SIZE_MAX_MULTIPLIER = 2.0
TRAFFIC_TIMEZONE_SIZE_PROFILE = {
    "night": 0.35,
    "morning": 0.80,
    "business": 1.50,
    "evening": 1.15,
}

ISL_DATA_RATE_MBIT_PER_S = 1_000
GSL_DATA_RATE_MBIT_PER_S = 100
DATA_RATE_MBIT_PER_S = ISL_DATA_RATE_MBIT_PER_S
QUEUE_SIZE_PKTS = 100
TCP_SOCKET_TYPE = "TcpNewReno"

ENABLE_TCP_FLOW_LOGGING = False

ENABLE_ISL_UTILIZATION_TRACKING = True
ISL_UTILIZATION_TRACKING_INTERVAL_NS = 1_000_000_000

ENABLE_SATELLITE_PATH_TRACKING = True
SATELLITE_PATH_TRACKING_INTERVAL_NS = 1_000_000_000

POSTPROCESS_TENSORS_AFTER_NS3 = True


def satellite_network_name() -> str:
    return f"{SATELLITE_NETWORK}_{ISL_MODE}_{GS_SELECTION}_{ROUTING_ALGORITHM}"


def dynamic_state_dir_name() -> str:
    return f"dynamic_state_{TIME_STEP_MS}ms_for_{DURATION_S}s"


def generated_satellite_network_dir() -> Path:
    return GEN_DATA_ROOT / satellite_network_name()


def run_dir() -> Path:
    return RUNS_DIR / "main"
