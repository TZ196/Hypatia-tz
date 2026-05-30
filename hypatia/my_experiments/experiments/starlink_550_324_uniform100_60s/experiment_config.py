"""Configuration for a reduced Starlink dense path-flow experiment."""

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

SHARED_INPUT_DIR = MY_EXPERIMENTS_DIR / "shared" / "input_data"
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

SATELLITE_NETWORK = "starlink_550_324"
DURATION_S = 10
TIME_STEP_MS = 1000
ISL_MODE = "isls_plus_grid"
GS_SELECTION = "ground_stations_satellite_anchored_648"
ROUTING_ALGORITHM = "algorithm_free_one_only_over_isls"

NUM_SATELLITES = 324
NUM_ORBITS = 18
NUM_SATS_PER_ORBIT = 18
NUM_GROUND_STATIONS = 648
GS_START_NODE_ID = NUM_SATELLITES
ISL_SHIFT = 0

# 10000 directed long-distance flows whose anchored access satellites are as far apart as possible.
TRAFFIC_PAIR_MODE = "satellite_access_far"
TRAFFIC_FLOW_COUNT = 10000
TRAFFIC_MIN_DISTANCE_KM = 5000
TRAFFIC_MAX_FLOWS_PER_CITY_ROLE = 20
TRAFFIC_PREFERRED_REGION_PAIRS = [
    ("Asia", "South America"),
    ("Asia", "Africa"),
    ("North America", "Oceania"),
    ("Europe", "Oceania"),
    ("Africa", "North America"),
    ("South America", "Europe"),
]
TRAFFIC_SEED = 123456789
TRAFFIC_START_TIME_NS = 0
TRAFFIC_ACTIVITY_PROFILE = "flat"
TRAFFIC_REFERENCE_UTC_HOUR = 0
TRAFFIC_OD_WEIGHT_MODE = "distance"
TRAFFIC_DISTANCE_WEIGHT_POWER = 1.0
TRAFFIC_PREFERRED_REGION_WEIGHT = 1.3
TRAFFIC_RANDOMNESS_SIGMA = 0.35
TRAFFIC_CAPACITY_SCOPE = "single_bottleneck"
TRAFFIC_OFFERED_LOAD = 1.0

# Keep flows intentionally larger than a 10s congested run can drain.
TRAFFIC_TARGET_AVG_FLOW_SIZE_BYTES = 500_000_000
TRAFFIC_MIN_FLOW_SIZE_BYTES = 200_000_000
TRAFFIC_MAX_FLOW_SIZE_BYTES = 1_000_000_000
TRAFFIC_REFERENCE_BANDWIDTH_MBIT_PER_S = 100

DATA_RATE_MBIT_PER_S = 100
QUEUE_SIZE_PKTS = 100
TCP_SOCKET_TYPE = "TcpNewReno"

ENABLE_TCP_FLOW_LOGGING = False

ENABLE_ISL_UTILIZATION_TRACKING = True
ISL_UTILIZATION_TRACKING_INTERVAL_NS = 1_000_000_000

ENABLE_SATELLITE_PATH_TRACKING = True
SATELLITE_PATH_TRACKING_INTERVAL_NS = 1_000_000_000


def satellite_network_name() -> str:
    return f"{SATELLITE_NETWORK}_{ISL_MODE}_{GS_SELECTION}_{ROUTING_ALGORITHM}"


def dynamic_state_dir_name() -> str:
    return f"dynamic_state_{TIME_STEP_MS}ms_for_{DURATION_S}s"


def generated_satellite_network_dir() -> Path:
    return GEN_DATA_ROOT / satellite_network_name()


def run_dir() -> Path:
    return RUNS_DIR / "main"
