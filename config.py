"""Configuration module for Intelligent Traffic Management System.

Defines default simulation parameters, intersection topology,
logging settings, and operational bounds.
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

# Signal timing constraints (in seconds)
TIMING_BOUNDS = {
    "min_green_range": (3, 20),
    "max_green_range": (8, 60),
    "default_min_green": 8,
    "default_max_green": 35,
    "manual_green_duration": 15,
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
}

# Congestion classification thresholds
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
