"""Unit tests for the autonomous simulation engine, phase transitions, and queues."""

from config import DIRECTIONS, SAFETY_INTERVALS, SIGNAL_PHASES
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
            assert j.active_direction in DIRECTIONS
            assert j.lanes[j.active_direction].signal == SIGNAL_PHASES["GREEN"]
            assert j.current_phase == SIGNAL_PHASES["GREEN"]
            # Safety check
            assert engine.optimizer.verify_conflict_free(j) is True
    finally:
        engine.stop_worker()


def test_queue_counts_never_negative():
    """Verify queue counts and waiting times remain strictly non-negative under extreme conditions."""
    engine = SimulationEngine(seed=999, autostart=False)
    try:
        # Force lanes to zero vehicles
        for j in engine.junctions.values():
            for lane in j.lanes.values():
                lane.vehicles = 0
                lane.waiting = 0
                lane.waiting_seconds = 0.0

        # Step 30 times
        for _ in range(30):
            engine.step()
            for j in engine.junctions.values():
                for lane in j.lanes.values():
                    assert lane.vehicles >= 0
                    assert lane.waiting >= 0
                    assert lane.waiting_seconds >= 0.0
                    assert lane.total_passed >= 0
    finally:
        engine.stop_worker()


def test_deterministic_simulation_with_seed():
    """Verify that two independently initialized engines with the same seed produce identical trajectories."""
    engine1 = SimulationEngine(seed=12345, autostart=False)
    engine2 = SimulationEngine(seed=12345, autostart=False)

    try:
        for _ in range(25):
            engine1.step()
            engine2.step()

        assert engine1.tick == engine2.tick == 25
        for jid in engine1.junctions:
            j1 = engine1.junctions[jid]
            j2 = engine2.junctions[jid]
            assert j1.current_phase == j2.current_phase
            assert j1.active_direction == j2.active_direction
            for d in DIRECTIONS:
                assert j1.lanes[d].vehicles == j2.lanes[d].vehicles
                assert j1.lanes[d].signal == j2.lanes[d].signal
                assert j1.lanes[d].total_passed == j2.lanes[d].total_passed
    finally:
        engine1.stop_worker()
        engine2.stop_worker()


def test_explicit_phase_transitions_green_yellow_allred():
    """Verify that a junction transitions cleanly through GREEN -> YELLOW -> ALL_RED -> GREEN."""
    engine = SimulationEngine(seed=42, autostart=False)
    try:
        j = engine.junctions["J1"]
        # Fast forward green phase to expiration
        j.phase_remaining = 1
        j.current_phase = SIGNAL_PHASES["GREEN"]
        orig_active = j.active_direction

        # Next step should trigger YELLOW transition
        engine.step()
        assert j.current_phase == SIGNAL_PHASES["YELLOW"]
        assert j.lanes[orig_active].signal == SIGNAL_PHASES["YELLOW"]
        assert j.phase_remaining == SAFETY_INTERVALS["yellow_duration"]

        # Step through the remaining yellow seconds
        for _ in range(SAFETY_INTERVALS["yellow_duration"]):
            engine.step()

        # Should now be in ALL_RED clearance
        assert j.current_phase == SIGNAL_PHASES["ALL_RED"]
        for d in DIRECTIONS:
            assert j.lanes[d].signal == SIGNAL_PHASES["RED"]
        assert j.phase_remaining == SAFETY_INTERVALS["all_red_duration"]

        # Step through ALL_RED clearance
        for _ in range(SAFETY_INTERVALS["all_red_duration"]):
            engine.step()

        # Should now be back in GREEN on the new direction
        assert j.current_phase == SIGNAL_PHASES["GREEN"]
        assert j.lanes[j.active_direction].signal == SIGNAL_PHASES["GREEN"]
        assert j.phase_remaining >= engine.settings["min_green"]
    finally:
        engine.stop_worker()


def test_scenarios_and_arrival_rates():
    engine = SimulationEngine(seed=55, autostart=False)
    try:
        assert engine.set_scenario("high") is True
        assert engine.scenario == "high"
        assert engine.arrival_multiplier > 1.0

        assert engine.set_scenario("invalid_scen") is False

        assert engine.set_arrival_multiplier(2.5) is True
        assert engine.arrival_multiplier == 2.5
        assert engine.set_arrival_multiplier(99.0) is False  # exceeds max
    finally:
        engine.stop_worker()


def test_emergency_preemption_lifecycle():
    engine = SimulationEngine(seed=88, autostart=False)
    try:
        j = engine.junctions["J1"]
        j.current_phase = SIGNAL_PHASES["GREEN"]
        j.active_direction = "North"
        j.phase_remaining = 20

        # Trigger emergency on South
        assert engine.trigger_emergency("J1", "South") is True
        assert j.lanes["South"].is_emergency is True

        # Preemption should shorten current green to trigger yellow transition immediately
        assert j.phase_remaining <= 1
        engine.step()
        # Should now be in YELLOW clearance
        assert j.current_phase == SIGNAL_PHASES["YELLOW"]
    finally:
        engine.stop_worker()


def test_manual_override_and_safe_restore():
    engine = SimulationEngine(seed=55, autostart=False)
    try:
        # Cannot manual override in auto mode
        assert engine.manual_override("J1", "East") is False

        # Switch to manual
        engine.auto_mode = False
        assert engine.manual_override("J1", "East") is True
        j = engine.junctions["J1"]
        assert j.active_direction == "East"
        assert j.lanes["East"].signal == SIGNAL_PHASES["GREEN"]
        for d in ["North", "South", "West"]:
            assert j.lanes[d].signal == SIGNAL_PHASES["RED"]

        # Restore auto mode
        engine.auto_mode = True
        assert engine.auto_mode is True
    finally:
        engine.stop_worker()
