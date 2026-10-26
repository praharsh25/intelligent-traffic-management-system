"""Request payload validation and sanitization for API endpoints.
"""

from typing import Any, Dict, List, Optional, Tuple
from config import DIRECTIONS, SCENARIOS, SIMULATION_DEFAULTS, TIMING_BOUNDS


def validate_control_payload(data: Any) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Validates /api/control payload."""
    if not isinstance(data, dict):
        return False, "Request body must be a JSON object.", {}

    action = data.get("action")
    allowed_actions = ["pause", "resume", "auto", "manual", "reset", "speed"]
    if action not in allowed_actions:
        return False, f"Invalid action '{action}'. Must be one of: {', '.join(allowed_actions)}.", {}

    validated_data: Dict[str, Any] = {"action": action}

    if action == "speed":
        speed = data.get("speed")
        try:
            speed_val = float(speed)
        except (TypeError, ValueError):
            return False, f"Speed must be a number, allowed: {SIMULATION_DEFAULTS['allowed_speeds']}.", {}

        if speed_val not in SIMULATION_DEFAULTS["allowed_speeds"]:
            return False, f"Invalid speed {speed_val}x. Allowed values: {SIMULATION_DEFAULTS['allowed_speeds']}.", {}
        validated_data["speed"] = speed_val

    elif action == "reset":
        if "seed" in data and data["seed"] is not None:
            try:
                validated_data["seed"] = int(data["seed"])
            except (TypeError, ValueError):
                return False, "Seed must be an integer if provided.", {}
        else:
            validated_data["seed"] = None

    return True, None, validated_data


def validate_scenario_payload(data: Any, valid_junctions: List[str]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Validates /api/scenario payload."""
    if not isinstance(data, dict):
        return False, "Request body must be a JSON object.", {}

    scenario = data.get("scenario")
    if not scenario or scenario not in SCENARIOS:
        return False, f"Invalid scenario '{scenario}'. Allowed: {list(SCENARIOS.keys())}.", {}

    junction = data.get("junction")
    direction = data.get("direction")

    if scenario == "emergency":
        if junction and junction not in valid_junctions:
            return False, f"Invalid junction '{junction}'. Allowed: {valid_junctions}.", {}
        if direction and direction not in DIRECTIONS:
            return False, f"Invalid direction '{direction}'. Allowed: {DIRECTIONS}.", {}

    return True, None, {
        "scenario": scenario,
        "junction": junction or "J1",
        "direction": direction or "North",
    }


def validate_emergency_payload(data: Any, valid_junctions: List[str]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Validates /api/emergency payload."""
    if not isinstance(data, dict):
        return False, "Request body must be a JSON object.", {}

    junction = data.get("junction", "J1")
    direction = data.get("direction", "North")

    if junction not in valid_junctions:
        return False, f"Invalid junction '{junction}'. Allowed: {valid_junctions}.", {}

    if direction not in DIRECTIONS:
        return False, f"Invalid direction '{direction}'. Allowed: {DIRECTIONS}.", {}

    return True, None, {"junction": junction, "direction": direction}


def validate_flow_rate_payload(data: Any) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Validates /api/flow-rate multiplier payload."""
    if not isinstance(data, dict):
        return False, "Request body must be a JSON object.", {}

    raw_multiplier = data.get("multiplier")
    try:
        multiplier = float(raw_multiplier)
    except (TypeError, ValueError):
        return False, "Multiplier must be a numeric value.", {}

    min_r, max_r = SIMULATION_DEFAULTS["arrival_rate_range"]
    if not (min_r <= multiplier <= max_r):
        return False, f"Arrival multiplier must be between {min_r}x and {max_r}x.", {}

    return True, None, {"multiplier": multiplier}


def validate_signal_payload(data: Any, valid_junctions: List[str]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Validates /api/signal manual override payload."""
    if not isinstance(data, dict):
        return False, "Request body must be a JSON object.", {}

    junction = data.get("junction")
    direction = data.get("direction")

    if not junction or junction not in valid_junctions:
        return False, f"Invalid junction '{junction}'. Must be one of: {', '.join(valid_junctions)}.", {}

    if not direction or direction not in DIRECTIONS:
        return False, f"Invalid direction '{direction}'. Must be one of: {', '.join(DIRECTIONS)}.", {}

    return True, None, {"junction": junction, "direction": direction}


def validate_traffic_payload(data: Any, valid_junctions: List[str]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Validates /api/traffic injection payload."""
    if not isinstance(data, dict):
        return False, "Request body must be a JSON object.", {}

    junction = data.get("junction")
    direction = data.get("direction")
    amount = data.get("amount", 5)

    if not junction or junction not in valid_junctions:
        return False, f"Invalid junction '{junction}'. Must be one of: {', '.join(valid_junctions)}.", {}

    if not direction or direction not in DIRECTIONS:
        return False, f"Invalid direction '{direction}'. Must be one of: {', '.join(DIRECTIONS)}.", {}

    if not isinstance(amount, int) or isinstance(amount, bool):
        return False, "Amount must be a whole integer.", {}

    min_amt, max_amt = SIMULATION_DEFAULTS["traffic_injection_range"]
    if not (min_amt <= amount <= max_amt):
        return False, f"Amount must be between {min_amt} and {max_amt}.", {}

    return True, None, {"junction": junction, "direction": direction, "amount": amount}


def validate_settings_payload(
    data: Any,
    current_settings: Dict[str, int],
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Validates /api/settings adaptive timing rules payload."""
    if not isinstance(data, dict):
        return False, "Request body must be a JSON object.", {}

    min_val_raw = data.get("min_green", current_settings["min_green"])
    max_val_raw = data.get("max_green", current_settings["max_green"])

    try:
        min_green = int(min_val_raw)
        max_green = int(max_val_raw)
    except (TypeError, ValueError):
        return False, "Signal timings must be valid integer seconds.", {}

    min_lower, min_upper = TIMING_BOUNDS["min_green_range"]
    max_lower, max_upper = TIMING_BOUNDS["max_green_range"]

    if not (min_lower <= min_green <= min_upper):
        return False, f"Minimum green must be between {min_lower}s and {min_upper}s.", {}

    if not (max_lower <= max_green <= max_upper):
        return False, f"Maximum green must be between {max_lower}s and {max_upper}s.", {}

    if min_green > max_green:
        return False, f"Minimum green ({min_green}s) cannot exceed maximum green ({max_green}s).", {}

    return True, None, {"min_green": min_green, "max_green": max_green}
