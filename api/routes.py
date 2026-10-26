"""REST API routes and blueprint registration for the Traffic Management System.
"""

import logging
from flask import Blueprint, current_app, jsonify, render_template, request

from api.validators import (
    validate_control_payload,
    validate_settings_payload,
    validate_signal_payload,
    validate_traffic_payload,
)

logger = logging.getLogger("traffic_system.api")
api_bp = Blueprint("api", __name__)


def get_engine():
    """Retrieves the active simulation engine from Flask application context."""
    return current_app.config["SIMULATION_ENGINE"]


@api_bp.route("/")
def index():
    """Serves the primary traffic management dashboard."""
    return render_template("index.html")


@api_bp.route("/api/health")
def api_health():
    """Lightweight operational health check."""
    engine = get_engine()
    return jsonify({
        "status": "healthy",
        "running": engine.running,
        "auto_mode": engine.auto_mode,
        "tick": engine.tick,
        "speed": engine.speed,
        "is_simulated": True,
    })


@api_bp.route("/api/state")
def api_state():
    """Returns the full JSON state snapshot of the traffic network."""
    engine = get_engine()
    return jsonify(engine.snapshot())


@api_bp.route("/api/tick", methods=["POST"])
def api_tick():
    """Advances the simulation by one discrete time step (used for single-step debugging or manual triggers)."""
    engine = get_engine()
    engine.step()
    return jsonify(engine.snapshot())


@api_bp.route("/api/control", methods=["POST"])
def api_control():
    """Executes high-level simulation lifecycle commands (pause, resume, auto, manual, reset, speed)."""
    engine = get_engine()
    raw_data = request.get_json(silent=True) or {}
    is_valid, error_msg, validated = validate_control_payload(raw_data)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    action = validated["action"]
    with engine.lock:
        if action == "pause":
            engine.running = False
            engine.add_event("Simulation paused by operator.", "warning")
        elif action == "resume":
            engine.running = True
            engine.add_event("Simulation resumed.", "success")
        elif action == "auto":
            engine.auto_mode = True
            engine.add_event("Adaptive signal mode enabled.", "success")
        elif action == "manual":
            engine.auto_mode = False
            engine.add_event("Manual signal mode enabled.", "warning")
        elif action == "reset":
            seed = validated.get("seed")
            engine.reset(seed=seed)
        elif action == "speed":
            speed_val = validated["speed"]
            engine.set_speed(speed_val)

    return jsonify(engine.snapshot())


@api_bp.route("/api/signal", methods=["POST"])
def api_signal():
    """Manually commands a specific lane to receive the green signal (Manual mode only)."""
    engine = get_engine()
    raw_data = request.get_json(silent=True) or {}
    valid_junctions = list(engine.junctions.keys())
    is_valid, error_msg, validated = validate_signal_payload(raw_data, valid_junctions)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    if engine.auto_mode:
        return jsonify({
            "error": "Manual override is disabled in Adaptive mode. Switch to Manual mode first."
        }), 400

    success = engine.manual_override(validated["junction"], validated["direction"])
    if not success:
        return jsonify({"error": "Failed to apply manual signal override."}), 400

    return jsonify(engine.snapshot())


@api_bp.route("/api/traffic", methods=["POST"])
def api_traffic():
    """Injects a burst of simulated vehicles into a specific junction lane."""
    engine = get_engine()
    raw_data = request.get_json(silent=True) or {}
    valid_junctions = list(engine.junctions.keys())
    is_valid, error_msg, validated = validate_traffic_payload(raw_data, valid_junctions)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    success = engine.inject_traffic(
        junction_id=validated["junction"],
        direction=validated["direction"],
        amount=validated["amount"],
    )
    if not success:
        return jsonify({"error": "Failed to inject simulated traffic."}), 400

    return jsonify(engine.snapshot())


@api_bp.route("/api/settings", methods=["POST"])
def api_settings():
    """Configures adaptive signal minimum and maximum green timing boundaries."""
    engine = get_engine()
    raw_data = request.get_json(silent=True) or {}
    is_valid, error_msg, validated = validate_settings_payload(raw_data, engine.settings)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    engine.update_settings(
        min_green=validated["min_green"],
        max_green=validated["max_green"],
    )
    return jsonify(engine.snapshot())
