"""Unit and integration tests for SQLite database persistence, repository, and analytics."""

import os
import pytest
from database.connection import get_db_connection, init_db, reset_db
from database.repository import TrafficRepository
from database.analytics import TrafficAnalytics
from app import create_app
from core.simulation_engine import SimulationEngine


@pytest.fixture
def test_db_path(tmp_path):
    """Provides an isolated temporary database path for testing."""
    db_file = str(tmp_path / "test_traffic.db")
    init_db(db_file)
    return db_file


def test_database_initialization_and_tables(test_db_path):
    """Verifies that all 6 tables and indexes are created properly with foreign keys enabled."""
    with get_db_connection(test_db_path) as conn:
        # Check foreign keys pragma
        fk = conn.execute("PRAGMA foreign_keys;").fetchone()
        assert list(fk.values())[0] == 1

        # Check tables exist
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        expected = [
            "audit_event_logs",
            "baseline_comparisons",
            "intersection_snapshots",
            "lane_metrics",
            "signal_phase_logs",
            "simulation_sessions",
        ]
        for exp in expected:
            assert exp in table_names


def test_persistence_of_sessions_and_snapshots(test_db_path):
    """Verifies recording and retrieving sessions, snapshots, and lane metrics."""
    repo = TrafficRepository(test_db_path)

    # 1. Create Session
    session_id = "test_sess_001"
    repo.create_session(session_id=session_id, control_mode="adaptive", scenario="medium", seed=42)

    session = repo.get_session(session_id)
    assert session is not None
    assert session["session_id"] == session_id
    assert session["control_mode"] == "adaptive"
    assert session["seed"] == 42

    # 2. Record Snapshot with Lanes
    lanes = {
        "North": {"vehicles": 12, "waiting": 4, "waiting_seconds": 15.0, "signal": "GREEN", "green_remaining": 10, "total_passed": 20, "cycles_without_green": 0, "priority_score": 0.45, "is_emergency": False},
        "East": {"vehicles": 8, "waiting": 2, "waiting_seconds": 8.0, "signal": "RED", "green_remaining": 0, "total_passed": 15, "cycles_without_green": 1, "priority_score": 0.25, "is_emergency": False},
        "South": {"vehicles": 5, "waiting": 1, "waiting_seconds": 5.0, "signal": "RED", "green_remaining": 0, "total_passed": 10, "cycles_without_green": 1, "priority_score": 0.18, "is_emergency": False},
        "West": {"vehicles": 4, "waiting": 1, "waiting_seconds": 4.0, "signal": "RED", "green_remaining": 0, "total_passed": 12, "cycles_without_green": 1, "priority_score": 0.15, "is_emergency": False},
    }

    repo.record_step_snapshot(
        session_id=session_id,
        tick=1,
        timestamp="2026-10-26T12:00:00",
        junction_id="J1",
        active_direction="North",
        current_phase="GREEN",
        phase_remaining=10,
        total_vehicles=29,
        total_passed=57,
        avg_wait_seconds=8.0,
        congestion_level="Moderate",
        emergency_active=False,
        lanes_dict=lanes,
    )

    # 3. Query back snapshots
    snaps = repo.get_snapshots(session_id=session_id)
    assert len(snaps) == 1
    assert snaps[0]["junction_id"] == "J1"
    assert snaps[0]["total_vehicles"] == 29
    assert snaps[0]["congestion_level"] == "Moderate"

    # Close session
    repo.close_session(session_id)
    updated_sess = repo.get_session(session_id)
    assert updated_sess["ended_at"] is not None


def test_analytics_calculations_from_db(test_db_path):
    """Verifies that analytics metrics are calculated strictly from database values."""
    repo = TrafficRepository(test_db_path)
    analytics = TrafficAnalytics(test_db_path)

    # Test empty database analytics
    empty_res = analytics.get_session_analytics(session_id="non_existent")
    assert empty_res["has_data"] is False
    assert empty_res["avg_wait_seconds"] == 0.0

    # Populate session and 2 snapshots
    sess_id = "test_analytics_sess"
    repo.create_session(session_id=sess_id)

    dummy_lanes = {
        "North": {"vehicles": 10, "waiting": 2, "waiting_seconds": 10.0, "signal": "GREEN", "green_remaining": 5, "total_passed": 10, "cycles_without_green": 0, "priority_score": 0.4, "is_emergency": False},
        "East": {"vehicles": 10, "waiting": 4, "waiting_seconds": 20.0, "signal": "RED", "green_remaining": 0, "total_passed": 10, "cycles_without_green": 1, "priority_score": 0.3, "is_emergency": False},
    }

    repo.record_step_snapshot(
        session_id=sess_id,
        tick=1,
        timestamp="2026-10-26T12:00:01",
        junction_id="J1",
        active_direction="North",
        current_phase="GREEN",
        phase_remaining=5,
        total_vehicles=20,
        total_passed=20,
        avg_wait_seconds=10.0,
        congestion_level="Low",
        emergency_active=False,
        lanes_dict=dummy_lanes,
    )

    repo.record_step_snapshot(
        session_id=sess_id,
        tick=2,
        timestamp="2026-10-26T12:00:02",
        junction_id="J1",
        active_direction="North",
        current_phase="GREEN",
        phase_remaining=4,
        total_vehicles=40,
        total_passed=25,
        avg_wait_seconds=20.0,
        congestion_level="Moderate",
        emergency_active=False,
        lanes_dict=dummy_lanes,
    )

    # Calculate analytics
    res = analytics.get_session_analytics(session_id=sess_id)
    assert res["has_data"] is True
    assert res["total_samples"] == 2
    # Mean of 10.0 and 20.0 is 15.0
    assert res["avg_wait_seconds"] == 15.0
    # Mean of 20 and 40 is 30.0
    assert res["avg_queue_length"] == 30.0
    # Peak queue is 40
    assert res["peak_queue_length"] == 40
    # Throughput: 25 - 20 = 5
    assert res["session_throughput"] == 5
    # Congestion: 1 Low and 1 Moderate -> 50% each
    assert res["congestion_distribution"]["Low"] == 50.0
    assert res["congestion_distribution"]["Moderate"] == 50.0
    assert res["congestion_distribution"]["Heavy"] == 0.0


def test_baseline_comparison_runner(test_db_path):
    """Verifies that running the baseline comparison generates valid fixed vs adaptive metrics."""
    analytics = TrafficAnalytics(test_db_path)
    repo = TrafficRepository(test_db_path)

    # Run a compact 20-tick comparison
    result = analytics.run_baseline_comparison(duration_ticks=20, seed=42, scenario="medium")

    assert "comparison_id" in result
    assert result["fixed_session_id"] is not None
    assert result["adaptive_session_id"] is not None
    assert "fixed_avg_wait" in result
    assert "adaptive_avg_wait" in result
    assert "wait_reduction_pct" in result

    # Check persistence in baseline_comparisons table
    stored = repo.get_baseline_comparisons()
    assert len(stored) >= 1
    assert stored[0]["comparison_id"] == result["comparison_id"]


def test_analytics_api_endpoints(test_db_path):
    """Verifies analytics REST endpoints using Flask test client."""
    engine = SimulationEngine(seed=42, autostart=False, db_path=test_db_path)
    app = create_app(test_config={"TESTING": True}, engine=engine)

    # Step engine to generate records
    for _ in range(5):
        engine.step()

    with app.test_client() as client:
        # GET sessions
        res = client.get("/api/analytics/sessions")
        assert res.status_code == 200
        assert res.get_json()["total_sessions"] >= 1

        # GET summary
        res = client.get("/api/analytics/summary")
        assert res.status_code == 200
        assert res.get_json()["has_data"] is True

        # GET history
        res = client.get("/api/analytics/history?limit=10")
        assert res.status_code == 200
        assert res.get_json()["count"] > 0

        # POST compare baseline
        res = client.post("/api/analytics/compare-baseline", json={
            "duration_ticks": 20,
            "seed": 42,
            "scenario": "medium",
        })
        assert res.status_code == 200
        assert res.get_json()["status"] == "success"

        # GET comparisons list
        res = client.get("/api/analytics/comparisons")
        assert res.status_code == 200
        assert res.get_json()["count"] >= 1

        # POST database reset
        res = client.post("/api/database/reset")
        assert res.status_code == 200
        assert res.get_json()["status"] == "success"

    engine.stop_worker()
