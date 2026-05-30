"""Small Iridium experiment for diagnosing cross-plane ISL routing."""

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

DEFAULT_GROUND_STATIONS_SOURCE = INPUT_DIR / "ground_stations_source.basic.txt"
GROUND_STATION_SELECTION_MODE = "copy"
GROUND_STATIONS_FILE = INPUT_DIR / "ground_stations.basic.txt"
GROUND_STATIONS_MANIFEST = INPUT_DIR / "ground_stations_manifest.csv"
TRAFFIC_SCHEDULE_FILE = INPUT_DIR / "schedule.csv"
TRAFFIC_DESIGN_FILE = INPUT_DIR / "traffic_design.txt"
TRAFFIC_MATRIX_FILE = INPUT_DIR / "traffic_matrix_bytes.csv"
TRAFFIC_ACTIVITY_FILE = INPUT_DIR / "station_activity.csv"
TRAFFIC_FLOW_DETAILS_FILE = INPUT_DIR / "traffic_flow_details.csv"

SATELLITE_NETWORK = "iridium_780"
DURATION_S = 4
TIME_STEP_MS = 1000
ISL_MODE = "isls_plus_grid"
GS_SELECTION = "ground_stations_cross_plane_diag_8"
ROUTING_ALGORITHM = "algorithm_free_one_only_over_isls"

NUM_SATELLITES = 66
NUM_GROUND_STATIONS = 8
GS_START_NODE_ID = NUM_SATELLITES
NUM_ORBITS = 6
NUM_SATS_PER_ORBIT = 11
ISL_SHIFT = 0
IRIDIUM_ISL_SHIFT = ISL_SHIFT
AUTO_SELECT_ISL_SHIFT = True

# Eight directed long-distance flows over globally spread stations.
TRAFFIC_PAIR_MODE = "explicit"
TRAFFIC_PAIRS = [
    (0, 4),  # Quito -> Singapore
    (1, 5),  # Reykjavik -> Auckland
    (2, 6),  # Nairobi -> Honolulu
    (3, 7),  # Anchorage -> Ushuaia
    (4, 0),  # Singapore -> Quito
    (5, 1),  # Auckland -> Reykjavik
    (6, 2),  # Honolulu -> Nairobi
    (7, 3),  # Ushuaia -> Anchorage
]
TRAFFIC_SEED = 123456789
TRAFFIC_START_TIME_NS = 0
TRAFFIC_ACTIVITY_PROFILE = "flat"
TRAFFIC_REFERENCE_UTC_HOUR = 0
TRAFFIC_OD_WEIGHT_MODE = "source_destination"
TRAFFIC_RANDOMNESS_SIGMA = 0
TRAFFIC_CAPACITY_SCOPE = "single_bottleneck"
TRAFFIC_TOTAL_BUDGET_BYTES = 1_600_000
TRAFFIC_MIN_FLOW_SIZE_BYTES = 200_000
TRAFFIC_MAX_FLOW_SIZE_BYTES = 200_000
TRAFFIC_REFERENCE_BANDWIDTH_MBIT_PER_S = 100

DATA_RATE_MBIT_PER_S = 100
QUEUE_SIZE_PKTS = 100
TCP_SOCKET_TYPE = "TcpNewReno"

ENABLE_TCP_FLOW_LOGGING = True

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
