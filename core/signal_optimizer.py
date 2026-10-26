"""Adaptive Traffic Signal Optimization Module.

Calculates pressure scores based on vehicle queues, waiting times,
and lane starvation counters, determining optimal green phase sequences
and dynamic phase durations within safety bounds.
"""

import random
from typing import Dict, Tuple
from config import DIRECTIONS
from core.models import Junction, LaneState


class SignalOptimizer:
    """Implements dynamic traffic signal optimization algorithms."""

    def __init__(self, vehicle_weight: float = 1.4, waiting_weight: float = 2.2, starvation_weight: float = 3.5):
        self.vehicle_weight = vehicle_weight
        self.waiting_weight = waiting_weight
        self.starvation_weight = starvation_weight

    def calculate_lane_score(self, lane: LaneState, rng: random.Random) -> float:
        """Computes the urgency/pressure score for a single lane approach."""
        base_pressure = (
            lane.vehicles * self.vehicle_weight +
            lane.waiting * self.waiting_weight +
            lane.cycles_without_green * self.starvation_weight
        )
        # Small stochastic perturbation to break ties
        noise = rng.random() * 2.5
        return base_pressure + noise

    def choose_next_direction(self, junction: Junction, rng: random.Random) -> str:
        """Selects the next lane to receive the green signal.

        Evaluates queue pressure across all candidate lanes, prioritizes starving
        lanes, and falls back to round-robin if pressure difference is negligible.
        """
        current_dir = junction.active_direction
        candidates = [d for d in DIRECTIONS if d != current_dir]

        scores: Dict[str, float] = {
            d: self.calculate_lane_score(junction.lanes[d], rng)
            for d in DIRECTIONS
        }

        # Candidate with highest pressure
        best_candidate = max(candidates, key=lambda d: scores[d])

        # Hysteresis threshold: only deviate from current if best candidate has significantly higher pressure
        current_score = scores[current_dir]
        if scores[best_candidate] < current_score + 2.0:
            # Predictable round-robin progression when traffic is balanced
            idx = DIRECTIONS.index(current_dir)
            return DIRECTIONS[(idx + 1) % len(DIRECTIONS)]

        return best_candidate

    def calculate_green_duration(self, queue: int, min_green: int, max_green: int) -> int:
        """Computes adaptive green duration based on estimated queue pressure."""
        proportional_extension = int(queue * 0.45)
        raw_duration = min_green + proportional_extension
        return max(min_green, min(max_green, raw_duration))

    def plan_next_phase(
        self,
        junction: Junction,
        min_green: int,
        max_green: int,
        rng: random.Random,
    ) -> Tuple[str, int]:
        """Plans the next active direction and green duration."""
        next_direction = self.choose_next_direction(junction, rng)
        target_lane = junction.lanes[next_direction]
        queue_size = target_lane.vehicles + target_lane.waiting
        duration = self.calculate_green_duration(queue_size, min_green, max_green)
        return next_direction, duration
