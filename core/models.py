"""Data models representing traffic simulation entities: lanes, junctions, and events.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from config import CONGESTION_THRESHOLDS, DIRECTIONS


@dataclass
class LaneState:
    """Represents a single lane direction in an intersection."""
    vehicles: int = 0
    waiting: int = 0
    signal: str = "RED"  # "RED" | "GREEN"
    green_remaining: int = 0
    total_passed: int = 0
    cycles_without_green: int = 0

    def to_dict(self) -> Dict:
        return {
            "vehicles": self.vehicles,
            "waiting": self.waiting,
            "signal": self.signal,
            "green_remaining": self.green_remaining,
            "total_passed": self.total_passed,
            "cycles_without_green": self.cycles_without_green,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "LaneState":
        return cls(
            vehicles=int(data.get("vehicles", 0)),
            waiting=int(data.get("waiting", 0)),
            signal=str(data.get("signal", "RED")),
            green_remaining=int(data.get("green_remaining", 0)),
            total_passed=int(data.get("total_passed", 0)),
            cycles_without_green=int(data.get("cycles_without_green", 0)),
        )


@dataclass
class Junction:
    """Represents a multi-approach intersection with North, East, South, West lanes."""
    id: str
    name: str
    location: str
    lanes: Dict[str, LaneState] = field(default_factory=dict)
    active_direction: str = "North"
    cycle: int = 1
    total_vehicles: int = 0
    total_passed: int = 0
    congestion: str = "Low"

    def __post_init__(self):
        if not self.lanes:
            for d in DIRECTIONS:
                self.lanes[d] = LaneState()
        self.update_totals()

    def update_totals(self) -> None:
        """Recalculates total queued vehicles, cumulative cleared count, and congestion status."""
        self.total_vehicles = sum(l.vehicles for l in self.lanes.values())
        self.total_passed = sum(l.total_passed for l in self.lanes.values())
        low = CONGESTION_THRESHOLDS["low_cutoff"]
        moderate = CONGESTION_THRESHOLDS["moderate_cutoff"]
        if self.total_vehicles < low:
            self.congestion = "Low"
        elif self.total_vehicles < moderate:
            self.congestion = "Moderate"
        else:
            self.congestion = "Heavy"

    def to_dict(self) -> Dict:
        """Serializes junction state for API JSON responses."""
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "active_direction": self.active_direction,
            "cycle": self.cycle,
            "total_vehicles": self.total_vehicles,
            "total_passed": self.total_passed,
            "congestion": self.congestion,
            "lanes": {d: self.lanes[d].to_dict() for d in DIRECTIONS if d in self.lanes},
        }


@dataclass
class SimulationEvent:
    """Represents an audit event in the traffic control center."""
    message: str
    kind: str = "info"  # "info" | "success" | "warning" | "signal" | "error"
    junction: Optional[str] = None
    time: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))

    def to_dict(self) -> Dict:
        return {
            "time": self.time,
            "message": self.message,
            "kind": self.kind,
            "junction": self.junction,
        }
