"""Autonomous Simulation Engine for Intelligent Traffic Management System.

CLASSROOM SIMULATION NOTICE:
This module runs a 100% software-based traffic simulation for educational and demonstration
purposes. All vehicles, queue dynamics, sensor readings, and signal phases are synthetic.

Features:
- Four configurable simulated intersections with 4 approaches (North, East, South, West).
- Explicit 4-phase state machine: GREEN -> YELLOW (3s) -> ALL_RED (1s) -> GREEN.
- Multi-scenario support: Low, Medium, High, Peak Hour (Tidal), and Emergency Preemption.
- Safe conflict prevention: at no point can conflicting directions hold GREEN or YELLOW.
- Safe manual override and seamless restoration of automated adaptive control.
- Deterministic pseudo-randomness when seeded for repeatable viva exam demonstrations.
"""

from datetime import datetime
import logging
import random
import threading
import time
from typing import Any, Dict, List, Optional

from config import (
    DEFAULT_JUNCTIONS,
    DIRECTIONS,
    SAFETY_INTERVALS,
    SCENARIOS,
    SIGNAL_PHASES,
    SIMULATION_DEFAULTS,
    TIMING_BOUNDS,
)
from core.models import Junction, LaneState, SimulationEvent
from core.signal_optimizer import SignalOptimizer

logger = logging.getLogger("traffic_system.engine")


class SimulationEngine:
    """Core simulation engine driving vehicle queues, signal phases, and network metrics."""

    def __init__(
        self,
        seed: Optional[int] = None,
        autostart: bool = True,
        tick_interval: float = SIMULATION_DEFAULTS["tick_interval_seconds"],
        speed: float = SIMULATION_DEFAULTS["default_speed"],
        scenario: str = SIMULATION_DEFAULTS["default_scenario"],
    ):
        self.lock = threading.RLock()
        self.tick_interval = tick_interval
        self.speed = speed
        self.initial_seed = seed
        self.current_seed = seed
        self.rng = random.Random(seed) if seed is not None else random.Random()

        # Operational state
        self.running: bool = True
        self.auto_mode: bool = True
        self.tick: int = 0
        self.last_updated: str = datetime.now().isoformat(timespec="seconds")

        # Scenario & Flow parameters
        self.scenario: str = scenario if scenario in SCENARIOS else "medium"
        self.arrival_multiplier: float = SCENARIOS[self.scenario]["multiplier"]

        self.settings: Dict[str, int] = {
            "min_green": TIMING_BOUNDS["default_min_green"],
            "max_green": TIMING_BOUNDS["default_max_green"],
            "yellow_duration": SAFETY_INTERVALS["yellow_duration"],
            "all_red_duration": SAFETY_INTERVALS["all_red_duration"],
        }

        self.optimizer = SignalOptimizer()
        self.events: List[SimulationEvent] = []
        self.junctions: Dict[str, Junction] = {}

        # Worker thread management
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # Initialize network state
        self._init_network()
        self.add_event(
            f"Traffic simulation initialized (Scenario: {SCENARIOS[self.scenario]['name']}, "
            f"Seed: {self.current_seed if self.current_seed is not None else 'Dynamic'}).",
            kind="success",
        )

        if autostart:
            self.start_worker()

    def _create_junction(self, item: Dict[str, str], idx: int) -> Junction:
        """Creates a junction with realistic initial queues and explicit signal phases."""
        j = Junction(id=item["id"], name=item["name"], location=item["location"])
        for d in DIRECTIONS:
            init_v = self.rng.randint(4, 20)
            j.lanes[d] = LaneState(
                vehicles=init_v,
                waiting=self.rng.randint(1, max(1, init_v // 2)),
                waiting_seconds=float(self.rng.randint(5, 30)),
                signal=SIGNAL_PHASES["RED"],
                green_remaining=0,
                total_passed=self.rng.randint(15, 80),
                cycles_without_green=0,
                priority_score=0.0,
                is_emergency=False,
            )

        active = DIRECTIONS[idx % len(DIRECTIONS)]
        j.active_direction = active
        j.current_phase = SIGNAL_PHASES["GREEN"]
        initial_green = self.rng.randint(10, 22)
        j.phase_remaining = initial_green
        j.lanes[active].signal = SIGNAL_PHASES["GREEN"]
        j.lanes[active].green_remaining = initial_green
        j.cycle = 1
        j.update_totals()
        return j

    def _init_network(self) -> None:
        """Instantiates all configured intersections."""
        with self.lock:
            self.junctions = {
                item["id"]: self._create_junction(item, idx)
                for idx, item in enumerate(DEFAULT_JUNCTIONS)
            }
            # Initial score calculation
            for j in self.junctions.values():
                self.optimizer.update_all_scores(j, self.rng)

    def add_event(self, message: str, kind: str = "info", junction: Optional[str] = None) -> None:
        """Records a timestamped audit event."""
        with self.lock:
            evt = SimulationEvent(message=message, kind=kind, junction=junction)
            self.events.insert(0, evt)
            limit = SIMULATION_DEFAULTS["event_history_limit"]
            if len(self.events) > limit:
                del self.events[limit:]

    def set_scenario(
        self,
        scenario_name: str,
        target_junction: Optional[str] = None,
        target_direction: Optional[str] = None,
    ) -> bool:
        """Switches the active traffic scenario (low, medium, high, peak_hour, emergency)."""
        with self.lock:
            if scenario_name not in SCENARIOS:
                return False

            self.scenario = scenario_name
            self.arrival_multiplier = SCENARIOS[scenario_name]["multiplier"]

            if scenario_name == "emergency":
                jid = target_junction if target_junction in self.junctions else "J1"
                d = target_direction if target_direction in DIRECTIONS else "North"
                self.trigger_emergency(jid, d)
            else:
                # Clear existing emergencies if switching to a normal scenario
                for j in self.junctions.values():
                    for l in j.lanes.values():
                        l.is_emergency = False
                    j.update_totals()

                self.add_event(
                    f"Traffic scenario updated to '{SCENARIOS[scenario_name]['name']}' "
                    f"({SCENARIOS[scenario_name]['description']}).",
                    kind="info",
                )
            return True

    def trigger_emergency(self, junction_id: str, direction: str) -> bool:
        """Simulates an approaching emergency vehicle (ambulance/fire engine) on a specific lane."""
        with self.lock:
            if junction_id not in self.junctions or direction not in DIRECTIONS:
                return False

            j = self.junctions[junction_id]
            lane = j.lanes[direction]
            lane.is_emergency = True
            # Add emergency vehicle to queue if empty
            lane.vehicles = max(1, lane.vehicles)
            j.update_totals()

            self.add_event(
                f"🚨 EMERGENCY PREEMPTION: Emergency vehicle detected approaching {j.name} ({direction} lane). "
                f"Initiating priority corridor clearance.",
                kind="emergency",
                junction=junction_id,
            )

            # If another direction has green, truncate remaining green to trigger immediate yellow clearance
            if j.active_direction != direction and j.current_phase == SIGNAL_PHASES["GREEN"]:
                if j.phase_remaining > 2:
                    j.phase_remaining = 1  # will trigger yellow next second

            return True

    def set_arrival_multiplier(self, multiplier: float) -> bool:
        """Sets a custom arrival rate multiplier."""
        with self.lock:
            min_r, max_r = SIMULATION_DEFAULTS["arrival_rate_range"]
            if not (min_r <= multiplier <= max_r):
                return False
            self.arrival_multiplier = round(multiplier, 2)
            self.add_event(f"Traffic arrival rate multiplier set to {self.arrival_multiplier}x.", kind="info")
            return True

    def reset(self, seed: Optional[int] = None) -> None:
        """Resets the simulation to initial conditions with optional new seed."""
        with self.lock:
            if seed is not None:
                self.current_seed = seed
                self.rng = random.Random(seed)
            elif self.initial_seed is not None:
                self.current_seed = self.initial_seed
                self.rng = random.Random(self.initial_seed)
            else:
                self.current_seed = None
                self.rng = random.Random()

            self.tick = 0
            self.running = True
            self.auto_mode = True
            self._init_network()
            self.events.clear()
            seed_label = f"Seed {self.current_seed}" if self.current_seed is not None else "Dynamic Seed"
            self.add_event(f"Simulation reset to initial conditions ({seed_label}).", "success")
            self.last_updated = datetime.now().isoformat(timespec="seconds")

    def _generate_arrivals(self, direction: str, is_active: bool) -> int:
        """Generates stochastic vehicle arrivals based on active scenario and directional bias."""
        weights = SCENARIOS[self.scenario]["arrival_weights"]
        base_arrivals = self.rng.choices([0, 1, 2, 3], weights=weights)[0]

        # Tidal peak-hour bias: heavier arrivals on North-South arterial corridor
        if self.scenario == "peak_hour" and direction in ["North", "South"]:
            if self.rng.random() < 0.60:
                base_arrivals += 1

        # Apply user/scenario multiplier
        adjusted = int(round(base_arrivals * self.arrival_multiplier))
        return max(0, min(4, adjusted))

    def step(self) -> None:
        """Advances the simulation by one atomic discrete time step (1 second)."""
        with self.lock:
            self.tick += 1
            max_capacity = SIMULATION_DEFAULTS["max_lane_capacity"]
            yellow_dur = self.settings.get("yellow_duration", SAFETY_INTERVALS["yellow_duration"])
            all_red_dur = self.settings.get("all_red_duration", SAFETY_INTERVALS["all_red_duration"])

            for j in self.junctions.values():
                active_dir = j.active_direction
                phase = j.current_phase

                # 1. Update vehicle queues and arrivals on each lane
                for d, lane in j.lanes.items():
                    # Generate arrivals
                    arrivals = self._generate_arrivals(d, d == active_dir)
                    lane.vehicles = min(max_capacity, lane.vehicles + arrivals)

                    # Manage waiting times and departure dynamics based on current phase
                    if phase == SIGNAL_PHASES["GREEN"] and d == active_dir:
                        # Green lane: discharge queued vehicles
                        departures = min(lane.vehicles, self.rng.randint(2, 5))
                        lane.vehicles = max(0, lane.vehicles - departures)
                        lane.total_passed += departures
                        # Relieve waiting counter
                        lane.waiting = max(0, lane.waiting - departures)
                        lane.waiting_seconds = max(0.0, lane.waiting_seconds - (departures * 3.0))
                        lane.cycles_without_green = 0
                        # Clear emergency flag once cleared
                        if lane.is_emergency and lane.vehicles <= 2:
                            lane.is_emergency = False
                            self.add_event(
                                f"Emergency vehicle successfully cleared {j.name} ({d} approach).",
                                kind="success",
                                junction=j.id,
                            )
                    elif phase == SIGNAL_PHASES["YELLOW"] and d == active_dir:
                        # Yellow phase: minor late clearance (0 to 1 vehicle)
                        if lane.vehicles > 0 and self.rng.random() < 0.4:
                            lane.vehicles -= 1
                            lane.total_passed += 1
                    else:
                        # Red lanes / clearance: stopped vehicles accumulate waiting time
                        if lane.vehicles > 0:
                            lane.waiting = min(lane.vehicles, lane.waiting + 1)
                            lane.waiting_seconds += 1.0

                # 2. Update phase countdown and handle transitions
                j.phase_remaining = max(0, j.phase_remaining - 1)
                active_lane = j.lanes[active_dir]
                if phase == SIGNAL_PHASES["GREEN"]:
                    active_lane.green_remaining = j.phase_remaining

                # Invariant safety assertion: ensure conflict-free state
                assert self.optimizer.verify_conflict_free(j), f"Safety violation detected at junction {j.id}!"

                # 3. Explicit Phase State Machine Transitions (in auto_mode)
                if self.auto_mode and self.running:
                    if phase == SIGNAL_PHASES["GREEN"] and j.phase_remaining <= 0:
                        # Green phase expired -> Plan next direction
                        next_dir, planned_green = self.optimizer.plan_next_phase(
                            junction=j,
                            min_green=self.settings["min_green"],
                            max_green=self.settings["max_green"],
                            rng=self.rng,
                        )

                        # If next direction is the same as current (high demand on same lane and others zero)
                        if next_dir == active_dir and not any(l.is_emergency for l in j.lanes.values()):
                            j.phase_remaining = planned_green
                            active_lane.green_remaining = planned_green
                            j.cycle += 1
                        else:
                            # Transition GREEN -> YELLOW (amber clearance)
                            j.current_phase = SIGNAL_PHASES["YELLOW"]
                            j.phase_remaining = yellow_dur
                            j.next_direction = next_dir
                            active_lane.signal = SIGNAL_PHASES["YELLOW"]
                            active_lane.green_remaining = 0
                            self.add_event(
                                f"{j.name}: transition to YELLOW for {active_dir} ({yellow_dur}s).",
                                kind="signal",
                                junction=j.id,
                            )

                    elif phase == SIGNAL_PHASES["YELLOW"] and j.phase_remaining <= 0:
                        # Yellow expired -> Transition YELLOW -> ALL_RED (safety box clearance)
                        j.current_phase = SIGNAL_PHASES["ALL_RED"]
                        j.phase_remaining = all_red_dur
                        active_lane.signal = SIGNAL_PHASES["RED"]
                        active_lane.green_remaining = 0
                        # All lanes are now strictly RED
                        for l in j.lanes.values():
                            l.signal = SIGNAL_PHASES["RED"]

                    elif phase == SIGNAL_PHASES["ALL_RED"] and j.phase_remaining <= 0:
                        # All-Red clearance expired -> Transition ALL_RED -> GREEN on next_direction
                        nxt = j.next_direction or active_dir
                        for d, l in j.lanes.items():
                            l.signal = SIGNAL_PHASES["RED"]
                            l.green_remaining = 0
                            if d != nxt:
                                l.cycles_without_green += 1

                        # Calculate fresh duration for next direction
                        _, duration = self.optimizer.plan_next_phase(
                            junction=j,
                            min_green=self.settings["min_green"],
                            max_green=self.settings["max_green"],
                            rng=self.rng,
                        )

                        j.active_direction = nxt
                        j.current_phase = SIGNAL_PHASES["GREEN"]
                        j.phase_remaining = duration
                        j.next_direction = None
                        j.cycle += 1

                        new_green_lane = j.lanes[nxt]
                        new_green_lane.signal = SIGNAL_PHASES["GREEN"]
                        new_green_lane.green_remaining = duration
                        new_green_lane.cycles_without_green = 0

                        self.add_event(
                            f"{j.name}: green signal allocated to {nxt} ({duration}s).",
                            kind="signal",
                            junction=j.id,
                        )

                # 4. Refresh scores and junction summaries
                self.optimizer.update_all_scores(j, self.rng)
                j.update_totals()

            self.last_updated = datetime.now().isoformat(timespec="seconds")

    def manual_override(self, junction_id: str, direction: str) -> bool:
        """Manually commands a specific lane to receive the green signal safely."""
        with self.lock:
            if self.auto_mode:
                return False
            if junction_id not in self.junctions or direction not in DIRECTIONS:
                return False

            j = self.junctions[junction_id]
            override_dur = TIMING_BOUNDS["manual_green_duration"]

            # Safely set only the target direction to GREEN; all others strictly RED
            for d, lane in j.lanes.items():
                if d == direction:
                    lane.signal = SIGNAL_PHASES["GREEN"]
                    lane.green_remaining = override_dur
                    lane.cycles_without_green = 0
                else:
                    lane.signal = SIGNAL_PHASES["RED"]
                    lane.green_remaining = 0
                    lane.cycles_without_green += 1

            j.active_direction = direction
            j.current_phase = SIGNAL_PHASES["GREEN"]
            j.phase_remaining = override_dur
            j.next_direction = None
            j.cycle += 1
            self.optimizer.update_all_scores(j, self.rng)
            j.update_totals()

            self.add_event(
                f"Manual override: {j.name} commanded {direction} GREEN for {override_dur}s.",
                kind="warning",
                junction=j.id,
            )
            return True

    def inject_traffic(self, junction_id: str, direction: str, amount: int) -> bool:
        """Simulates an external burst of vehicles on a specific lane approach."""
        with self.lock:
            if junction_id not in self.junctions or direction not in DIRECTIONS:
                return False
            max_capacity = SIMULATION_DEFAULTS["max_lane_capacity"]
            lane = self.junctions[junction_id].lanes[direction]
            lane.vehicles = min(max_capacity, lane.vehicles + amount)
            lane.waiting = min(lane.vehicles, lane.waiting + max(1, amount // 2))
            lane.waiting_seconds += float(amount * 2.0)
            self.junctions[junction_id].update_totals()
            self.optimizer.update_all_scores(self.junctions[junction_id], self.rng)
            self.add_event(
                f"{amount} simulated vehicles injected into {self.junctions[junction_id].name} — {direction} approach.",
                kind="info",
                junction=junction_id,
            )
            return True

    def update_settings(self, min_green: int, max_green: int) -> None:
        """Updates adaptive signal duration boundaries."""
        with self.lock:
            self.settings["min_green"] = min_green
            self.settings["max_green"] = max_green
            self.add_event(
                f"Adaptive timing rules updated: minimum {min_green}s, maximum {max_green}s.",
                kind="success",
            )

    def set_speed(self, speed: float) -> bool:
        """Sets simulation speed multiplier."""
        with self.lock:
            if speed not in SIMULATION_DEFAULTS["allowed_speeds"]:
                return False
            self.speed = speed
            self.add_event(f"Simulation speed set to {speed}x.", kind="info")
            return True

    def snapshot(self) -> Dict[str, Any]:
        """Produces a JSON-serializable snapshot of the entire traffic network state."""
        with self.lock:
            j_list = [j.to_dict() for j in self.junctions.values()]
            total_vehicles = sum(j["total_vehicles"] for j in j_list)
            total_passed = sum(j["total_passed"] for j in j_list)
            heavy_count = sum(1 for j in j_list if j["congestion"] == "Heavy")

            return {
                "running": self.running,
                "auto_mode": self.auto_mode,
                "tick": self.tick,
                "speed": self.speed,
                "seed": self.current_seed,
                "scenario": self.scenario,
                "scenario_info": SCENARIOS.get(self.scenario, {}),
                "arrival_multiplier": self.arrival_multiplier,
                "is_simulated": True,
                "simulation_disclaimer": "100% Software-Based IoT Simulation. Classroom & Academic Use Only.",
                "last_updated": self.last_updated,
                "settings": dict(self.settings),
                "intersections": j_list,
                "events": [e.to_dict() for e in self.events[:25]],
                "summary": {
                    "vehicles": total_vehicles,
                    "passed": total_passed,
                    "heavy": heavy_count,
                    "junctions": len(self.junctions),
                },
            }

    # Background Thread Lifecycle
    def start_worker(self) -> None:
        """Starts the background worker thread if not already running."""
        with self.lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="TrafficSimulationWorker",
                daemon=True,
            )
            self._worker_thread.start()
            logger.info("Simulation worker thread started.")

    def stop_worker(self) -> None:
        """Signals worker thread to stop cleanly."""
        self._stop_event.set()
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.5)
            logger.info("Simulation worker thread stopped.")

    def _worker_loop(self) -> None:
        """Autonomous loop running ticks at the configured speed interval."""
        while not self._stop_event.is_set():
            start_time = time.time()
            if self.running:
                try:
                    self.step()
                except Exception as err:
                    logger.error(f"Error in simulation step: {err}", exc_info=True)

            sleep_total = max(0.05, self.tick_interval / max(0.1, self.speed))
            elapsed = time.time() - start_time
            remaining = max(0.01, sleep_total - elapsed)

            slice_duration = 0.05
            while remaining > 0 and not self._stop_event.is_set():
                sleep_slice = min(slice_duration, remaining)
                time.sleep(sleep_slice)
                remaining -= sleep_slice
