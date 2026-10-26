"""Integration tests for REST API endpoints and validators."""

import pytest
from app import create_app
from core.simulation_engine import SimulationEngine


@pytest.fixture
def test_client():
    """Provides a configured Flask test client with an isolated engine."""
    engine = SimulationEngine(seed=101, autostart=False)
    app = create_app(test_config={"TESTING": True}, engine=engine)
    with app.test_client() as client:
        yield client, engine
    engine.stop_worker()


def test_index_route(test_client):
    client, _ = test_client
    res = client.get("/")
    assert res.status_code == 200
    assert b"TrafficIQ" in res.data
    assert b"SOFTWARE SIMULATION" in res.data


def test_health_endpoint(test_client):
    client, _ = test_client
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"
    assert "tick" in data
    assert data["is_simulated"] is True


def test_state_endpoint(test_client):
    client, _ = test_client
    res = client.get("/api/state")
    assert res.status_code == 200
    data = res.get_json()
    assert "summary" in data
    assert "intersections" in data
    assert len(data["intersections"]) == 4
    assert data["summary"]["vehicles"] >= 0


def test_tick_endpoint(test_client):
    client, engine = test_client
    assert engine.tick == 0
    res = client.post("/api/tick")
    assert res.status_code == 200
    assert engine.tick == 1


def test_control_pause_resume_auto_manual(test_client):
    client, engine = test_client

    # Pause
    res = client.post("/api/control", json={"action": "pause"})
    assert res.status_code == 200
    assert res.get_json()["running"] is False
    assert engine.running is False

    # Resume
    res = client.post("/api/control", json={"action": "resume"})
    assert res.status_code == 200
    assert res.get_json()["running"] is True

    # Manual
    res = client.post("/api/control", json={"action": "manual"})
    assert res.status_code == 200
    assert res.get_json()["auto_mode"] is False

    # Auto
    res = client.post("/api/control", json={"action": "auto"})
    assert res.status_code == 200
    assert res.get_json()["auto_mode"] is True


def test_control_speed_and_reset(test_client):
    client, engine = test_client

    # Speed
    res = client.post("/api/control", json={"action": "speed", "speed": 2.0})
    assert res.status_code == 200
    assert res.get_json()["speed"] == 2.0

    # Invalid speed
    res = client.post("/api/control", json={"action": "speed", "speed": 99.0})
    assert res.status_code == 400

    # Advance tick
    client.post("/api/tick")
    assert engine.tick > 0

    # Reset with seed
    res = client.post("/api/control", json={"action": "reset", "seed": 42})
    assert res.status_code == 200
    data = res.get_json()
    assert data["tick"] == 0
    assert data["seed"] == 42


def test_signal_override(test_client):
    client, _ = test_client

    # Attempt override while in Auto mode -> should fail
    res = client.post("/api/signal", json={"junction": "J1", "direction": "North"})
    assert res.status_code == 400
    assert "Switch to Manual mode" in res.get_json()["error"]

    # Switch to manual
    client.post("/api/control", json={"action": "manual"})

    # Valid override
    res = client.post("/api/signal", json={"junction": "J1", "direction": "West"})
    assert res.status_code == 200
    j1 = next(j for j in res.get_json()["intersections"] if j["id"] == "J1")
    assert j1["active_direction"] == "West"

    # Invalid junction
    res = client.post("/api/signal", json={"junction": "J99", "direction": "North"})
    assert res.status_code == 400


def test_traffic_injection_api(test_client):
    client, _ = test_client
    res = client.post("/api/traffic", json={"junction": "J1", "direction": "North", "amount": 10})
    assert res.status_code == 200

    # Out of range amount
    res = client.post("/api/traffic", json={"junction": "J1", "direction": "North", "amount": 100})
    assert res.status_code == 400


def test_settings_api(test_client):
    client, _ = test_client
    res = client.post("/api/settings", json={"min_green": 10, "max_green": 40})
    assert res.status_code == 200
    data = res.get_json()
    assert data["settings"]["min_green"] == 10
    assert data["settings"]["max_green"] == 40

    # min > max
    res = client.post("/api/settings", json={"min_green": 25, "max_green": 20})
    assert res.status_code == 400
