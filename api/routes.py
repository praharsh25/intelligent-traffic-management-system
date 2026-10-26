"""REST API routes and blueprint registration for the Traffic Management System.
Includes persistent storage and analytical query endpoints.
"""

import logging
from flask import Blueprint, current_app, jsonify, render_template, request

from api.validators import (
    validate_baseline_compare_payload,
    validate_control_payload,
    validate_emergency_payload,
    validate_flow_rate_payload,
    validate_scenario_payload,
    validate_settings_payload,
    validate_signal_payload,
    validate_traffic_payload,
)
from database.analytics import TrafficAnalytics
from database.connection import reset_db
from database.repository import TrafficRepository

logger = logging.getLogger("traffic_system.api")
api_bp = Blueprint("api", __name__)


def get_engine():
    """Retrieves the active simulation engine from Flask application context."""
    return current_app.config["SIMULATION_ENGINE"]


def get_analytics():
    """Returns an analytics service instance connected to the active database."""
    engine = get_engine()
    return TrafficAnalytics(db_path=engine.db_path)


def get_repo():
    """Returns a repository instance connected to the active database."""
    engine = get_engine()
    return TrafficRepository(db_path=engine.db_path)


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
        "scenario": engine.scenario,
        "session_id": engine.session_id,
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


@api_bp.route("/api/scenario", methods=["POST"])
def api_scenario():
    """Switches the active traffic flow scenario (low, medium, high, peak_hour, emergency)."""
    engine = get_engine()
    raw_data = request.get_json(silent=True) or {}
    valid_junctions = list(engine.junctions.keys())
    is_valid, error_msg, validated = validate_scenario_payload(raw_data, valid_junctions)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    success = engine.set_scenario(
        scenario_name=validated["scenario"],
        target_junction=validated.get("junction"),
        target_direction=validated.get("direction"),
    )
    if not success:
        return jsonify({"error": "Failed to switch traffic scenario."}), 400

    return jsonify(engine.snapshot())


@api_bp.route("/api/emergency", methods=["POST"])
def api_emergency():
    """Dispatches an emergency vehicle on a specific junction approach, triggering priority preemption."""
    engine = get_engine()
    raw_data = request.get_json(silent=True) or {}
    valid_junctions = list(engine.junctions.keys())
    is_valid, error_msg, validated = validate_emergency_payload(raw_data, valid_junctions)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    success = engine.trigger_emergency(
        junction_id=validated["junction"],
        direction=validated["direction"],
    )
    if not success:
        return jsonify({"error": "Failed to trigger emergency vehicle preemption."}), 400

    return jsonify(engine.snapshot())


@api_bp.route("/api/flow-rate", methods=["POST"])
def api_flow_rate():
    """Configures the overall traffic arrival rate multiplier."""
    engine = get_engine()
    raw_data = request.get_json(silent=True) or {}
    is_valid, error_msg, validated = validate_flow_rate_payload(raw_data)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    success = engine.set_arrival_multiplier(validated["multiplier"])
    if not success:
        return jsonify({"error": "Failed to set arrival rate multiplier."}), 400

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


# =====================================================================
# PERSISTENT STORAGE & ANALYTICS ENDPOINTS
# =====================================================================

@api_bp.route("/api/analytics/sessions")
def api_analytics_sessions():
    """Returns list of historical simulation sessions from SQLite."""
    repo = get_repo()
    try:
        limit = min(100, max(1, int(request.args.get("limit", 30))))
    except ValueError:
        limit = 30
    sessions = repo.get_sessions(limit=limit)
    return jsonify({
        "total_sessions": len(sessions),
        "sessions": sessions,
    })


@api_bp.route("/api/analytics/summary")
def api_analytics_summary():
    """Calculates aggregated performance analytics (wait times, queues, throughput, congestion dist, utilization) from recorded data."""
    analytics = get_analytics()
    session_id = request.args.get("session_id")
    junction_id = request.args.get("junction_id")
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")

    # If no session specified, default to active running session
    if not session_id and not start_time:
        engine = get_engine()
        session_id = engine.session_id

    summary = analytics.get_session_analytics(
        session_id=session_id,
        junction_id=junction_id,
        start_time=start_time,
        end_time=end_time,
    )
    return jsonify(summary)


@api_bp.route("/api/analytics/history")
def api_analytics_history():
    """Queries historical intersection snapshots for analytical charting."""
    repo = get_repo()
    session_id = request.args.get("session_id")
    junction_id = request.args.get("junction_id")
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    try:
        limit = min(500, max(1, int(request.args.get("limit", 150))))
    except ValueError:
        limit = 150

    snapshots = repo.get_snapshots(
        session_id=session_id,
        junction_id=junction_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    return jsonify({
        "count": len(snapshots),
        "snapshots": snapshots,
    })


@api_bp.route("/api/analytics/signal-logs")
def api_analytics_signal_logs():
    """Retrieves recorded signal phase transition audit logs."""
    repo = get_repo()
    session_id = request.args.get("session_id")
    junction_id = request.args.get("junction_id")
    try:
        limit = min(200, max(1, int(request.args.get("limit", 50))))
    except ValueError:
        limit = 50

    logs = repo.get_signal_logs(
        session_id=session_id,
        junction_id=junction_id,
        limit=limit,
    )
    return jsonify({
        "count": len(logs),
        "signal_logs": logs,
    })


@api_bp.route("/api/analytics/events")
def api_analytics_events():
    """Retrieves recorded audit events from SQLite."""
    repo = get_repo()
    session_id = request.args.get("session_id")
    kind = request.args.get("kind")
    try:
        limit = min(200, max(1, int(request.args.get("limit", 50))))
    except ValueError:
        limit = 50

    events = repo.get_audit_events(
        session_id=session_id,
        kind=kind,
        limit=limit,
    )
    return jsonify({
        "count": len(events),
        "events": events,
    })


@api_bp.route("/api/analytics/compare-baseline", methods=["POST"])
def api_compare_baseline():
    """Executes side-by-side Fixed-Time vs Adaptive benchmark comparison with equivalent reproducible seeds."""
    analytics = get_analytics()
    raw_data = request.get_json(silent=True) or {}
    is_valid, error_msg, validated = validate_baseline_compare_payload(raw_data)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    try:
        comparison_result = analytics.run_baseline_comparison(
            duration_ticks=validated["duration_ticks"],
            seed=validated["seed"],
            scenario=validated["scenario"],
        )
        return jsonify({
            "status": "success",
            "comparison": comparison_result,
        })
    except Exception as e:
        logger.error(f"Error executing baseline comparison: {e}", exc_info=True)
        return jsonify({"error": f"Baseline comparison execution failed: {str(e)}"}), 500


@api_bp.route("/api/analytics/comparisons")
def api_analytics_comparisons():
    """Retrieves list of past baseline comparison runs."""
    repo = get_repo()
    try:
        limit = min(50, max(1, int(request.args.get("limit", 10))))
    except ValueError:
        limit = 10
    comparisons = repo.get_baseline_comparisons(limit=limit)
    return jsonify({
        "count": len(comparisons),
        "comparisons": comparisons,
    })


@api_bp.route("/api/database/reset", methods=["POST"])
def api_database_reset():
    """Resets the SQLite database tables and schema for development testing."""
    engine = get_engine()
    try:
        reset_db(engine.db_path)
        # Re-register current session
        engine.repo.create_session(
            session_id=engine.session_id,
            control_mode="adaptive" if engine.auto_mode else "manual",
            scenario=engine.scenario,
            seed=engine.current_seed,
            arrival_multiplier=engine.arrival_multiplier,
            min_green=engine.settings["min_green"],
            max_green=engine.settings["max_green"],
        )
        engine.add_event("Database reset and re-initialized.", "warning")
        return jsonify({"status": "success", "message": "Database reset and re-initialized."})
    except Exception as e:
        logger.error(f"Failed to reset database: {e}", exc_info=True)
        return jsonify({"error": f"Database reset failed: {str(e)}"}), 500
