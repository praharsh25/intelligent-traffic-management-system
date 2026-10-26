"""Unit tests for adaptive signal optimization algorithms."""

import random
from core.models import Junction, LaneState
from core.signal_optimizer import SignalOptimizer


def test_green_duration_bounds():
    opt = SignalOptimizer()
    min_g = 8
    max_g = 35

    # Small queue should return minimum
    assert opt.calculate_green_duration(queue=0, min_green=min_g, max_green=max_g) == 8
    assert opt.calculate_green_duration(queue=4, min_green=min_g, max_green=max_g) == 9

    # Moderate queue
    mid_dur = opt.calculate_green_duration(queue=20, min_green=min_g, max_green=max_g)
    assert 8 <= mid_dur <= 35
    assert mid_dur == 8 + int(20 * 0.45)  # 17

    # Large queue should clamp to max_green
    assert opt.calculate_green_duration(queue=150, min_green=min_g, max_green=max_g) == 35


def test_pressure_score_ranking():
    opt = SignalOptimizer()
    rng = random.Random(42)

    empty_lane = LaneState(vehicles=0, waiting=0)
    busy_lane = LaneState(vehicles=25, waiting=10)
    starving_lane = LaneState(vehicles=10, waiting=5, cycles_without_green=4)

    score_empty = opt.calculate_lane_score(empty_lane, rng)
    score_busy = opt.calculate_lane_score(busy_lane, rng)
    score_starving = opt.calculate_lane_score(starving_lane, rng)

    assert score_busy > score_empty
    assert score_starving > score_empty


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


def test_plan_next_phase_returns_direction_and_duration():
    opt = SignalOptimizer()
    rng = random.Random(999)

    j = Junction(id="J1", name="Test", location="A × B")
    j.active_direction = "North"
    j.lanes["East"].vehicles = 20

    nxt, duration = opt.plan_next_phase(j, min_green=8, max_green=35, rng=rng)
    assert nxt in ["North", "East", "South", "West"]
    assert 8 <= duration <= 35
