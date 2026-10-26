"""Unit tests for traffic data models (LaneState, Junction, SimulationEvent)."""

from core.models import Junction, LaneState, SimulationEvent
from config import DIRECTIONS


def test_lane_state_defaults_and_serialization():
    lane = LaneState(vehicles=15, waiting=4, signal="GREEN", green_remaining=12, total_passed=45)
    data = lane.to_dict()
    assert data["vehicles"] == 15
    assert data["waiting"] == 4
    assert data["signal"] == "GREEN"
    assert data["green_remaining"] == 12
    assert data["total_passed"] == 45
    assert data["cycles_without_green"] == 0

    reconstructed = LaneState.from_dict(data)
    assert reconstructed.vehicles == lane.vehicles
    assert reconstructed.waiting == lane.waiting
    assert reconstructed.signal == lane.signal


def test_junction_initialization_and_totals():
    j = Junction(id="J1", name="Test Square", location="A St × B Ave")
    for d in DIRECTIONS:
        assert d in j.lanes
        assert isinstance(j.lanes[d], LaneState)

    # Populate lane counts
    j.lanes["North"].vehicles = 10
    j.lanes["North"].total_passed = 5
    j.lanes["East"].vehicles = 5
    j.lanes["East"].total_passed = 10
    j.update_totals()

    assert j.total_vehicles == 15
    assert j.total_passed == 15
    assert j.congestion == "Low"  # < 28 is Low

    # Push to moderate
    j.lanes["South"].vehicles = 20
    j.update_totals()
    assert j.total_vehicles == 35
    assert j.congestion == "Moderate"  # 28-57 is Moderate

    # Push to heavy
    j.lanes["West"].vehicles = 30
    j.update_totals()
    assert j.total_vehicles == 65
    assert j.congestion == "Heavy"  # >= 58 is Heavy


def test_junction_serialization():
    j = Junction(id="J2", name="Market", location="M St")
    d = j.to_dict()
    assert d["id"] == "J2"
    assert d["name"] == "Market"
    assert "lanes" in d
    assert len(d["lanes"]) == 4


def test_simulation_event_to_dict():
    evt = SimulationEvent(message="Phase changed", kind="signal", junction="J1")
    d = evt.to_dict()
    assert d["message"] == "Phase changed"
    assert d["kind"] == "signal"
    assert d["junction"] == "J1"
    assert "time" in d

