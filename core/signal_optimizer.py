"""Adaptive Traffic Signal Optimization Module.

CLASSROOM SIMULATION NOTICE:
This module implements an educational, software-based adaptive traffic signal
algorithm for academic demonstration. It is NOT certified for controlling physical
traffic signal controllers or real-world intersection hardware.

MATHEMATICAL FORMULATION & PRIORITY SCORING:
For each lane approach d in an intersection:
  1. Normalized Queue Density:
     rho_d = min(1.0, vehicles_d / MAX_LANE_CAPACITY)  [Unitless: 0.0 to 1.0]
  2. Normalized Waiting Factor:
     omega_d = min(1.0, waiting_seconds_d / MAX_WAIT_THRESHOLD)  [Unitless: 0.0 to 1.0]
  3. Starvation Escalation Penalty:
     sigma_d = (cycles_without_green_d / STARVATION_THRESHOLD)^1.5 if cycles >= 3 else 0.0
  4. Emergency Priority Override:
     If is_emergency == True, priority score = 999.0
  5. Composite Priority Score:
     P_d = w_q * rho_d + w_w * omega_d + w_s * sigma_d + epsilon_d
     where w_q = 0.45, w_w = 0.35, w_s = 0.20 (sum = 1.0), and epsilon is a tie-breaker.

DYNAMIC GREEN DURATION ALLOCATION:
  T_green = clamp(T_min, T_max, T_min + round((T_max - T_min) * (P_target / sum(P_all))))
  Clearance Intervals:
  - Yellow Interval: 3 seconds (NEMA TS2 clearance)
  - All-Red Interval: 1 second (Intersection box conflict clearance)

CONFLICT PREVENTION:
  Conflicting approaches (North/South vs East/West) cannot receive GREEN or YELLOW
  concurrently. Exactly one approach (or protected phase) holds active green/yellow,
  while all conflicting approaches are strictly held at RED.
"""

import random
from typing import Dict, List, Tuple
from config import DIRECTIONS, SCORING_WEIGHTS, SIMULATION_DEFAULTS, TIMING_BOUNDS
from core.models import Junction, LaneState


class SignalOptimizer:
    """Calculates transparent priority scores and dynamically allocates green signal time."""

    def __init__(
        self,
        weight_queue: float = SCORING_WEIGHTS["queue_density"],
        weight_wait: float = SCORING_WEIGHTS["waiting_time"],
        weight_starve: float = SCORING_WEIGHTS["starvation"],
        max_wait_threshold: float = SCORING_WEIGHTS["max_wait_threshold"],
        starvation_threshold: int = SCORING_WEIGHTS["starvation_cycle_threshold"],
        max_capacity: int = SIMULATION_DEFAULTS["max_lane_capacity"],
    ):
        self.w_q = weight_queue
        self.w_w = weight_wait
        self.w_s = weight_starve
        self.max_wait = max_wait_threshold
        self.starve_thresh = starvation_threshold
        self.max_cap = max_capacity

    def calculate_lane_score(self, lane: LaneState, rng: random.Random) -> float:
        """Calculates normalized priority score for a single lane approach.
        
        Returns a transparent float score typically between 0.00 and 1.50+
        (or 999.0 for emergency vehicles).
        """
        # Absolute preemption for emergency vehicles
        if lane.is_emergency:
            lane.priority_score = 999.0
            return 999.0

        # 1. Normalized queue density (0.0 to 1.0)
        rho = min(1.0, max(0, lane.vehicles) / max(1, self.max_cap))

        # 2. Normalized waiting time (0.0 to 1.0)
        omega = min(1.0, max(0.0, lane.waiting_seconds) / max(1.0, self.max_wait))

        # 3. Non-linear starvation escalation for waiting lanes
        if lane.cycles_without_green >= self.starve_thresh:
            ratio = lane.cycles_without_green / self.starve_thresh
            sigma = min(2.0, (ratio ** 1.5))
        else:
            sigma = 0.0

        # 4. Stochastic or deterministic tie-breaker (0.000 to 0.015)
        epsilon = rng.random() * 0.015

        # 5. Composite score
        score = (self.w_q * rho) + (self.w_w * omega) + (self.w_s * sigma) + epsilon
        lane.priority_score = round(score, 3)
        return lane.priority_score

    def update_all_scores(self, junction: Junction, rng: random.Random) -> Dict[str, float]:
        """Calculates and updates priority scores for all approaches at an intersection."""
        scores = {}
        for d in DIRECTIONS:
            scores[d] = self.calculate_lane_score(junction.lanes[d], rng)
        return scores

    def choose_next_direction(self, junction: Junction, rng: random.Random) -> str:
        """Selects the optimal next lane to receive the green signal.

        Evaluates queue density, waiting time, starvation, and emergency status.
        """
        scores = self.update_all_scores(junction, rng)
        current_dir = junction.active_direction

        # Emergency vehicle immediate preemption check
        for d in DIRECTIONS:
            if junction.lanes[d].is_emergency:
                return d

        candidates = [d for d in DIRECTIONS if d != current_dir]

        # Highest priority candidate among waiting directions
        best_candidate = max(candidates, key=lambda d: scores[d])

        # Hysteresis: only switch if candidate score exceeds current by a margin,
        # or if current lane is empty
        current_vehicles = junction.lanes[current_dir].vehicles
        current_score = scores[current_dir]

        if current_vehicles <= 0:
            return best_candidate

        # If candidate has significantly higher demand or is starving
        switch_threshold = 0.15
        if scores[best_candidate] > (current_score + switch_threshold):
            return best_candidate

        # Predictable round-robin progression when all demands are low and balanced
        if all(scores[d] < 0.10 for d in DIRECTIONS):
            idx = DIRECTIONS.index(current_dir)
            return DIRECTIONS[(idx + 1) % len(DIRECTIONS)]

        return best_candidate

    def calculate_green_duration(
        self,
        target_score: float,
        total_scores: float,
        min_green: int,
        max_green: int,
    ) -> int:
        """Allocates green time proportionally based on priority demand score.

        Enforces minimum green (prevents short switching) and maximum green
        (prevents lane starvation).
        """
        # Ensure bounds are valid
        min_green = max(TIMING_BOUNDS["min_green_range"][0], min(TIMING_BOUNDS["min_green_range"][1], min_green))
        max_green = max(min_green, min(TIMING_BOUNDS["max_green_range"][1], max_green))

        if total_scores <= 0.05 or target_score <= 0.01:
            return min_green

        # Proportional share of the dynamic timing window (max_green - min_green)
        proportional_share = target_score / max(0.01, total_scores)
        dynamic_window = max_green - min_green
        allocated = min_green + int(round(dynamic_window * min(1.0, proportional_share * 1.5)))

        return max(min_green, min(max_green, allocated))

    def plan_next_phase(
        self,
        junction: Junction,
        min_green: int,
        max_green: int,
        rng: random.Random,
    ) -> Tuple[str, int]:
        """Plans the next active direction and allocated green duration."""
        scores = self.update_all_scores(junction, rng)
        next_dir = self.choose_next_direction(junction, rng)
        total_scores = sum(scores.values())
        target_score = scores[next_dir]

        duration = self.calculate_green_duration(
            target_score=target_score,
            total_scores=total_scores,
            min_green=min_green,
            max_green=max_green,
        )
        return next_dir, duration

    def verify_conflict_free(self, junction: Junction) -> bool:
        """Safety invariant check: asserts no conflicting directions have GREEN or YELLOW simultaneously.
        
        Returns True if the intersection state is valid and conflict-free.
        """
        active_lights = [
            d for d, lane in junction.lanes.items()
            if lane.signal in ["GREEN", "YELLOW"]
        ]
        # At most one direction may hold GREEN or YELLOW at any instant
        return len(active_lights) <= 1
