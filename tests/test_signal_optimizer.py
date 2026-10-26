"""Unit tests for adaptive signal optimization algorithms, scoring, bounds, and conflict prevention."""

import random
from core.models import Junction, LaneState
from core.signal_optimizer import SignalOptimizer
from config import DIRECTIONS, SIGNAL_PHASES


def test_green_duration_bounds():
    opt = SignalOptimizer()
    min_g = 8
    max_g = 35

    # Small/zero queue score should allocate min_green
    assert opt.calculate_green_duration(target_score=0.0, total_scores=1.0, min_green=min_g, max_green=max_g) == min_g
    assert opt.calculate_green_duration(target_score=0.01, total_scores=0.04, min_green=min_g, max_green=max_g) == min_g

    # Moderate score
    mid_dur = opt.calculate_green_duration(target_score=0.5, total_scores=1.0, min_green=min_g, max_green=max_g)
    assert min_g <= mid_dur <= max_g

    # Heavy score should clamp to max_green
    assert opt.calculate_green_duration(target_score=2.5, total_scores=3.0, min_green=min_g, max_green=max_g) == max_g


def test_pressure_score_ranking_and_starvation():
    opt = SignalOptimizer()
    rng = random.Random(42)

    empty_lane = LaneState(vehicles=0, waiting=0, waiting_seconds=0)
    busy_lane = LaneState(vehicles=25, waiting=10, waiting_seconds=20)
    starving_lane = LaneState(vehicles=10, waiting=5, waiting_seconds=60, cycles_without_green=5)

    score_empty = opt.calculate_lane_score(empty_lane, rng)
    score_busy = opt.calculate_lane_score(busy_lane, rng)
    score_starving = opt.calculate_lane_score(starving_lane, rng)

    assert score_busy > score_empty
    # Starving lane receives significant non-linear penalty boost
    assert score_starving > score_empty
    assert starving_lane.priority_score > 0.3


def test_emergency_priority_score_override():
    opt = SignalOptimizer()
    rng = random.Random(42)

    normal_lane = LaneState(vehicles=30, waiting=15, waiting_seconds=40)
    emerg_lane = LaneState(vehicles=5, waiting=2, waiting_seconds=5, is_emergency=True)

    score_normal = opt.calculate_lane_score(normal_lane, rng)
    score_emerg = opt.calculate_lane_score(emerg_lane, rng)

    assert score_emerg == 999.0
    assert score_emerg > score_normal


def test_choose_next_direction_prioritizes_highest_pressure():
    opt = SignalOptimizer()
    rng = random.Random(123)

    j = Junction(id="J1", name="Test", location="A × B")
    j.active_direction = "North"
    j.lanes["North"].vehicles = 5
    j.lanes["East"].vehicles = 2
    j.lanes["South"].vehicles = 35  # Heaviest queue
    j.lanes["West"].vehicles = 4

    next_dir = opt.choose_next_direction(j, rng)
    assert next_dir == "South"


def test_choose_next_direction_emergency_override():
    opt = SignalOptimizer()
    rng = random.Random(123)

    j = Junction(id="J1", name="Test", location="A × B")
    j.active_direction = "North"
    j.lanes["North"].vehicles = 30
    j.lanes["East"].vehicles = 25
    j.lanes["South"].vehicles = 25
    j.lanes["West"].vehicles = 2
    j.lanes["West"].is_emergency = True  # West has ambulance

    next_dir = opt.choose_next_direction(j, rng)
    assert next_dir == "West"


def test_conflict_prevention_check():
    opt = SignalOptimizer()
    j = Junction(id="J1", name="Test", location="A × B")

    # Safe state: exactly 1 green, others red
    j.lanes["North"].signal = SIGNAL_PHASES["GREEN"]
    j.lanes["East"].signal = SIGNAL_PHASES["RED"]
    j.lanes["South"].signal = SIGNAL_PHASES["RED"]
    j.lanes["West"].signal = SIGNAL_PHASES["RED"]
    assert opt.verify_conflict_free(j) is True

    # Safe state: all red (clearance interval)
    for d in DIRECTIONS:
        j.lanes[d].signal = SIGNAL_PHASES["RED"]
    assert opt.verify_conflict_free(j) is True

    # Dangerous conflict: two conflicting approaches GREEN
    j.lanes["North"].signal = SIGNAL_PHASES["GREEN"]
    j.lanes["East"].signal = SIGNAL_PHASES["GREEN"]
    assert opt.verify_conflict_free(j) is False

    # Dangerous conflict: one GREEN and one YELLOW simultaneously
    j.lanes["North"].signal = SIGNAL_PHASES["GREEN"]
    j.lanes["East"].signal = SIGNAL_PHASES["YELLOW"]
    assert opt.verify_conflict_free(j) is False
