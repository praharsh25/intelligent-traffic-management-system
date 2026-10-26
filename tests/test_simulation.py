"""Unit tests for the autonomous simulation engine."""

from core.simulation_engine import SimulationEngine


def test_simulation_engine_initialization():
    engine = SimulationEngine(seed=42, autostart=False)
    try:
        assert len(engine.junctions) == 4
        assert engine.running is True
        assert engine.auto_mode is True
        assert engine.tick == 0
        assert engine.current_seed == 42
        for j in engine.junctions.values():
            assert len(j.lanes) == 4
            assert j.active_direction in ["North", "East", "South", "West"]
            assert j.lanes[j.active_direction].signal == "GREEN"
    finally:
        engine.stop_worker()


def test_deterministic_simulation_with_seed():
    """Verify that two independently initialized engines with the same seed produce identical trajectories."""
    engine1 = SimulationEngine(seed=12345, autostart=False)
    engine2 = SimulationEngine(seed=12345, autostart=False)

    try:
        # Check initial state matching
        for jid in engine1.junctions:
            for d in ["North", "East", "South", "West"]:
                assert engine1.junctions[jid].lanes[d].vehicles == engine2.junctions[jid].lanes[d].vehicles
                assert engine1.junctions[jid].lanes[d].waiting == engine2.junctions[jid].lanes[d].waiting

        # Step both 15 times
        for _ in range(15):
            engine1.step()
            engine2.step()

        # Check identical state after 15 steps
        assert engine1.tick == engine2.tick == 15
        for jid in engine1.junctions:
            for d in ["North", "East", "South", "West"]:
                assert engine1.junctions[jid].lanes[d].vehicles == engine2.junctions[jid].lanes[d].vehicles
                assert engine1.junctions[jid].lanes[d].waiting == engine2.junctions[jid].lanes[d].waiting
                assert engine1.junctions[jid].lanes[d].signal == engine2.junctions[jid].lanes[d].signal
    finally:
        engine1.stop_worker()
        engine2.stop_worker()


def test_engine_pause_resume_reset():
    engine = SimulationEngine(seed=77, autostart=False)
    try:
        engine.running = False
        assert engine.running is False

        engine.running = True
        assert engine.running is True

        # Advance 5 steps
        for _ in range(5):
            engine.step()
        assert engine.tick == 5

        # Reset with new seed
        engine.reset(seed=88)
        assert engine.tick == 0
        assert engine.current_seed == 88
        assert engine.running is True
    finally:
        engine.stop_worker()


def test_traffic_injection():
    engine = SimulationEngine(seed=55, autostart=False)
    try:
        lane = engine.junctions["J1"].lanes["North"]
        before = lane.vehicles
        success = engine.inject_traffic("J1", "North", 10)
        assert success is True
        assert lane.vehicles == before + 10
    finally:
        engine.stop_worker()


def test_manual_override():
    engine = SimulationEngine(seed=55, autostart=False)
    try:
        engine.auto_mode = False
        j = engine.junctions["J1"]
        target = "West" if j.active_direction != "West" else "East"

        success = engine.manual_override("J1", target)
        assert success is True
        assert j.active_direction == target
        assert j.lanes[target].signal == "GREEN"
        assert j.lanes[target].green_remaining == 15
    finally:
        engine.stop_worker()


def test_set_speed():
    engine = SimulationEngine(seed=55, autostart=False)
    try:
        assert engine.set_speed(2.0) is True
        assert engine.speed == 2.0
        assert engine.set_speed(999.0) is False  # not in allowed speeds
    finally:
        engine.stop_worker()
