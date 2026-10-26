"""Autonomous Simulation Engine for Intelligent Traffic Management System.

Runs a server-side background simulation worker thread, maintains deterministic
pseudo-random state when seeded, enforces thread safety via RLock, and provides
lifecycle controls (start, pause, resume, reset, speed multiplier, single step).
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
    ):
        self.lock = threading.RLock()
        self.tick_interval = tick_interval
        self.speed = speed
        self.initial_seed = seed
        self.current_seed = seed
        self.rng = random.Random(seed) if seed is not None else random.Random()

        self.running: bool = True
        self.auto_mode: bool = True
        self.tick: int = 0
        self.last_updated: str = datetime.now().isoformat(timespec="seconds")

        self.settings: Dict[str, int] = {
            "min_green": TIMING_BOUNDS["default_min_green"],
            "max_green": TIMING_BOUNDS["default_max_green"],
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
            f"Traffic simulation initialized (Seed: {self.current_seed if self.current_seed is not None else 'Dynamic'}).",
            kind="success",
        )

        if autostart:
            self.start_worker()

    def _create_junction(self, item: Dict[str, str], idx: int) -> Junction:
        """Creates a junction with deterministic initial queues."""
        j = Junction(id=item["id"], name=item["name"], location=item["location"])
        for d in DIRECTIONS:
            j.lanes[d] = LaneState(
                vehicles=self.rng.randint(4, 22),
                waiting=self.rng.randint(1, 8),
                signal="RED",
                green_remaining=0,
                total_passed=self.rng.randint(10, 90),
                cycles_without_green=0,
            )
        active = DIRECTIONS[idx % len(DIRECTIONS)]
        j.active_direction = active
        j.lanes[active].signal = "GREEN"
        j.lanes[active].green_remaining = self.rng.randint(8, 20)
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

    def add_event(self, message: str, kind: str = "info", junction: Optional[str] = None) -> None:
        """Records a timestamped audit event."""
        with self.lock:
            evt = SimulationEvent(message=message, kind=kind, junction=junction)
            self.events.insert(0, evt)
            limit = SIMULATION_DEFAULTS["event_history_limit"]
            if len(self.events) > limit:
                del self.events[limit:]

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

    def step(self) -> None:
        """Advances the simulation by one atomic discrete time step."""
        with self.lock:
            self.tick += 1
            max_capacity = SIMULATION_DEFAULTS["max_lane_capacity"]

            for j in self.junctions.values():
                for d, lane in j.lanes.items():
                    # Synthetic vehicle arrivals according to stochastic distribution
                    arrivals = self.rng.choices([0, 1, 2, 3], weights=[25, 45, 23, 7])[0]
                    lane.vehicles = min(max_capacity, lane.vehicles + arrivals)

                    if d != j.active_direction:
                        # Non-green lanes accumulate waiting count and increment starvation counter
                        if lane.vehicles > 0:
                            lane.waiting = min(max_capacity, lane.waiting + 1)
                    else:
                        # Green lane discharges queued vehicles
                        cleared = min(lane.vehicles, self.rng.randint(2, 6))
                        lane.vehicles -= cleared
                        lane.total_passed += cleared
                        lane.waiting = max(0, lane.waiting - self.rng.randint(1, 4))
                        lane.cycles_without_green = 0

                active_lane = j.lanes[j.active_direction]
                active_lane.green_remaining = max(0, active_lane.green_remaining - 1)

                # Adaptive green phase transition trigger
                if self.auto_mode and self.running and active_lane.green_remaining <= 0:
                    for d, l in j.lanes.items():
                        if d != j.active_direction:
                            l.cycles_without_green += 1

                    next_dir, duration = self.optimizer.plan_next_phase(
                        junction=j,
                        min_green=self.settings["min_green"],
                        max_green=self.settings["max_green"],
                        rng=self.rng,
                    )

                    for l in j.lanes.values():
                        l.signal = "RED"
                        l.green_remaining = 0

                    j.lanes[next_dir].signal = "GREEN"
                    j.lanes[next_dir].green_remaining = duration
                    j.lanes[next_dir].cycles_without_green = 0
                    j.active_direction = next_dir
                    j.cycle += 1

                    self.add_event(
                        f"{j.name}: green signal moved to {next_dir} ({duration}s).",
                        kind="signal",
                        junction=j.id,
                    )

                j.update_totals()

            self.last_updated = datetime.now().isoformat(timespec="seconds")

    def manual_override(self, junction_id: str, direction: str) -> bool:
        """Manually forces a green signal on a specific junction approach."""
        with self.lock:
            if self.auto_mode:
                return False
            if junction_id not in self.junctions or direction not in DIRECTIONS:
                return False

            j = self.junctions[junction_id]
            override_dur = TIMING_BOUNDS["manual_green_duration"]

            for d, lane in j.lanes.items():
                if d == direction:
                    lane.signal = "GREEN"
                    lane.green_remaining = override_dur
                    lane.cycles_without_green = 0
                else:
                    lane.signal = "RED"
                    lane.green_remaining = 0
                    lane.cycles_without_green += 1

            j.active_direction = direction
            j.cycle += 1
            self.add_event(
                f"Manual override: {j.name} set to {direction} GREEN for {override_dur}s.",
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
            lane.waiting = min(max_capacity, lane.waiting + max(1, amount // 3))
            self.junctions[junction_id].update_totals()
            self.add_event(
                f"{amount} simulated vehicles added to {self.junctions[junction_id].name} — {direction} lane.",
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
                f"Adaptive timing updated: minimum {min_green}s, maximum {max_green}s.",
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
                "is_simulated": True,
                "last_updated": self.last_updated,
                "settings": dict(self.settings),
                "intersections": j_list,
                "events": [e.to_dict() for e in self.events[:20]],
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

            # Sleep interval calculated from speed multiplier
            sleep_total = max(0.05, self.tick_interval / max(0.1, self.speed))
            elapsed = time.time() - start_time
            remaining = max(0.01, sleep_total - elapsed)

            # Responsive sleep in short slices so speed changes and pause/stop respond immediately
            slice_duration = 0.05
            while remaining > 0 and not self._stop_event.is_set():
                sleep_slice = min(slice_duration, remaining)
                time.sleep(sleep_slice)
                remaining -= sleep_slice
