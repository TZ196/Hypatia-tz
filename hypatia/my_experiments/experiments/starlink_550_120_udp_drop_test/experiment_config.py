"""Configuration for the isolated Starlink-120 UDP drop diagnostic."""

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

SATELLITE_NETWORK = "starlink_550_120"
DURATION_S = 3
TIME_STEP_MS = 1000
ISL_MODE = "isls_plus_grid"
GS_SELECTION = "ground_stations_satellite_anchored_240"
ROUTING_ALGORITHM = "algorithm_free_one_only_over_isls"

NUM_SATELLITES = 120
NUM_ORBITS = 10
NUM_SATS_PER_ORBIT = 12
NUM_GROUND_STATIONS = 240
GS_START_NODE_ID = NUM_SATELLITES
ISL_SHIFT = 0

DATA_RATE_MBIT_PER_S = 100
QUEUE_SIZE_PKTS = 1
TCP_SOCKET_TYPE = "TcpNewReno"

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
