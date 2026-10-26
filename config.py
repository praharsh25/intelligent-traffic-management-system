"""Configuration module for Intelligent Traffic Management System.

Defines simulation parameters, intersection topology, timing bounds,
safety clearance intervals, traffic scenarios, and scoring weights.
"""

import logging
import os

# Base directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Traffic topology
DIRECTIONS = ["North", "East", "South", "West"]

DEFAULT_JUNCTIONS = [
    {
        "id": "J1",
        "name": "Central Square",
        "location": "Main Road × Station Road",
    },
    {
        "id": "J2",
        "name": "Market Junction",
        "location": "Market Street × College Road",
    },
    {
        "id": "J3",
        "name": "River Bridge",
        "location": "Riverside Road × Ring Road",
    },
    {
        "id": "J4",
        "name": "Tech Park Gate",
        "location": "IT Park Road × Airport Road",
    },
]

# Explicit Signal Phases
SIGNAL_PHASES = {
    "GREEN": "GREEN",
    "YELLOW": "YELLOW",
    "ALL_RED": "ALL_RED",
    "RED": "RED",
}

# Safety Clearance Intervals (in seconds)
SAFETY_INTERVALS = {
    "yellow_duration": 3,      # NEMA TS2 standard amber clearance interval
    "all_red_duration": 1,     # Intersection box conflict clearance interval
}

# Signal timing constraints (in seconds)
TIMING_BOUNDS = {
    "min_green_range": (3, 20),
    "max_green_range": (8, 60),
    "default_min_green": 8,
    "default_max_green": 35,
    "manual_green_duration": 15,
}

# Adaptive Scoring Weights (Sum = 1.0)
SCORING_WEIGHTS = {
    "queue_density": 0.45,     # Weight for normalized vehicle queue length
    "waiting_time": 0.35,      # Weight for normalized accumulated waiting time
    "starvation": 0.20,        # Weight for lanes with prolonged denial of green
    "max_wait_threshold": 90,  # Max wait time seconds for normalization ceiling
    "starvation_cycle_threshold": 3, # Consecutive cycles without green before penalty
}

# Traffic Scenarios
SCENARIOS = {
    "low": {
        "name": "Low Traffic",
        "description": "Light, free-flowing off-peak traffic conditions",
        "arrival_weights": [55, 35, 9, 1],  # 0, 1, 2, 3 arrivals
        "multiplier": 0.6,
    },
    "medium": {
        "name": "Medium Traffic",
        "description": "Standard steady-state urban traffic flow",
        "arrival_weights": [25, 45, 23, 7],
        "multiplier": 1.0,
    },
    "high": {
        "name": "High Traffic",
        "description": "Dense, heavily congested rush-hour volume",
        "arrival_weights": [10, 30, 40, 20],
        "multiplier": 1.6,
    },
    "peak_hour": {
        "name": "Peak Hour (Tidal)",
        "description": "Directional tidal flow with heavy North-South corridor volume",
        "arrival_weights": [15, 35, 35, 15],
        "multiplier": 2.0,
    },
    "emergency": {
        "name": "Emergency Preemption",
        "description": "Active emergency vehicle requesting priority corridor clearance",
        "arrival_weights": [25, 45, 23, 7],
        "multiplier": 1.0,
    },
}

# Simulation settings
SIMULATION_DEFAULTS = {
    "tick_interval_seconds": 1.0,
    "default_speed": 1.0,
    "allowed_speeds": [0.25, 0.5, 1.0, 2.0, 4.0],
    "default_seed": None,
    "max_lane_capacity": 60,
    "traffic_injection_range": (1, 25),
    "event_history_limit": 60,
    "autostart_engine": True,
    "default_scenario": "medium",
    "arrival_rate_range": (0.2, 3.0),
}

# Congestion classification thresholds (by total queued vehicles in junction)
CONGESTION_THRESHOLDS = {
    "low_cutoff": 28,
    "moderate_cutoff": 58,
}


def setup_logging(level=logging.INFO):
    """Configures structured console logging for the application."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger("traffic_system")
