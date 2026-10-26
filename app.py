"""Application entry point and factory for Intelligent Traffic Management System.

Serves the REST API and dashboard interface for software-based traffic simulation
and adaptive signal control.
"""

import atexit
import logging
import os
from flask import Flask

from api.routes import api_bp
from config import SIMULATION_DEFAULTS, setup_logging
from core.simulation_engine import SimulationEngine

logger = setup_logging()


def create_app(test_config=None, engine=None) -> Flask:
    """Creates and configures the Flask application instance."""
    app = Flask(__name__, template_folder="templates", static_folder="static")

    if test_config:
        app.config.update(test_config)

    # Initialize or attach the singleton simulation engine
    if engine is not None:
        simulation_engine = engine
    else:
        seed = app.config.get("SIMULATION_SEED", SIMULATION_DEFAULTS["default_seed"])
        autostart = app.config.get("AUTOSTART_ENGINE", SIMULATION_DEFAULTS["autostart_engine"])
        simulation_engine = SimulationEngine(seed=seed, autostart=autostart)

    app.config["SIMULATION_ENGINE"] = simulation_engine

    # Ensure worker thread stops cleanly on shutdown
    def cleanup():
        try:
            simulation_engine.stop_worker()
        except Exception:
            pass

    atexit.register(cleanup)

    # Register API blueprint
    app.register_blueprint(api_bp)

    return app


# Module-level app instance for WSGI / flask run
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"============================================================")
    print(f"  Intelligent Traffic Management System")
    print(f"  Software IoT Simulation & Adaptive Traffic Signal Control")
    print(f"  Dashboard: http://{host}:{port}")
    print(f"============================================================")
    # Debug reloader is disabled to prevent duplicate background worker threads
    app.run(host=host, port=port, debug=True, use_reloader=False)
