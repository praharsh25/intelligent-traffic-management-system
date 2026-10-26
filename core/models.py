"""Data models representing traffic simulation entities: lanes, junctions, and events.
Supports explicit signal phases (RED, YELLOW, ALL_RED, GREEN) and emergency priority flags.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
from config import CONGESTION_THRESHOLDS, DIRECTIONS, SIGNAL_PHASES


@dataclass
class LaneState:
    """Represents a single lane approach in an intersection."""
    vehicles: int = 0
    waiting: int = 0
    waiting_seconds: float = 0.0
    signal: str = SIGNAL_PHASES["RED"]  # "RED" | "YELLOW" | "GREEN"
    green_remaining: int = 0
    total_passed: int = 0
    cycles_without_green: int = 0
    priority_score: float = 0.0
    is_emergency: bool = False

    def to_dict(self) -> Dict:
        return {
            "vehicles": max(0, self.vehicles),
            "waiting": max(0, self.waiting),
            "waiting_seconds": round(max(0.0, self.waiting_seconds), 1),
            "signal": self.signal,
            "green_remaining": max(0, self.green_remaining),
            "total_passed": max(0, self.total_passed),
            "cycles_without_green": self.cycles_without_green,
            "priority_score": round(self.priority_score, 2),
            "is_emergency": self.is_emergency,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "LaneState":
        return cls(
            vehicles=max(0, int(data.get("vehicles", 0))),
            waiting=max(0, int(data.get("waiting", 0))),
            waiting_seconds=max(0.0, float(data.get("waiting_seconds", 0.0))),
            signal=str(data.get("signal", SIGNAL_PHASES["RED"])),
            green_remaining=max(0, int(data.get("green_remaining", 0))),
            total_passed=max(0, int(data.get("total_passed", 0))),
            cycles_without_green=max(0, int(data.get("cycles_without_green", 0))),
            priority_score=float(data.get("priority_score", 0.0)),
            is_emergency=bool(data.get("is_emergency", False)),
        )


@dataclass
class Junction:
    """Represents a multi-approach intersection with explicit signal phases and safety clearance."""
    id: str
    name: str
    location: str
    lanes: Dict[str, LaneState] = field(default_factory=dict)
    active_direction: str = "North"
    current_phase: str = SIGNAL_PHASES["GREEN"]  # "GREEN" | "YELLOW" | "ALL_RED"
    phase_remaining: int = 0
    next_direction: Optional[str] = None
    cycle: int = 1
    total_vehicles: int = 0
    total_passed: int = 0
    avg_wait_seconds: float = 0.0
    congestion: str = "Low"
    emergency_active: bool = False
    emergency_direction: Optional[str] = None

    def __post_init__(self):
        if not self.lanes:
            for d in DIRECTIONS:
                self.lanes[d] = LaneState()
        self.update_totals()

    def update_totals(self) -> None:
        """Recalculates total queued vehicles, cumulative cleared count, and congestion status."""
        self.total_vehicles = sum(max(0, l.vehicles) for l in self.lanes.values())
        self.total_passed = sum(max(0, l.total_passed) for l in self.lanes.values())
        
        total_waiting_sec = sum(l.waiting_seconds for l in self.lanes.values())
        if self.total_vehicles > 0:
            self.avg_wait_seconds = round(total_waiting_sec / self.total_vehicles, 1)
        else:
            self.avg_wait_seconds = 0.0

        low = CONGESTION_THRESHOLDS["low_cutoff"]
        moderate = CONGESTION_THRESHOLDS["moderate_cutoff"]
        if self.total_vehicles < low:
            self.congestion = "Low"
        elif self.total_vehicles < moderate:
            self.congestion = "Moderate"
        else:
            self.congestion = "Heavy"

        # Check if any lane has an active emergency vehicle
        self.emergency_active = any(l.is_emergency for l in self.lanes.values())
        if self.emergency_active:
            for d, l in self.lanes.items():
                if l.is_emergency:
                    self.emergency_direction = d
                    break
        else:
            self.emergency_direction = None

    def to_dict(self) -> Dict:
        """Serializes junction state for API JSON responses."""
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "active_direction": self.active_direction,
            "current_phase": self.current_phase,
            "phase_remaining": max(0, self.phase_remaining),
            "next_direction": self.next_direction,
            "cycle": self.cycle,
            "total_vehicles": self.total_vehicles,
            "total_passed": self.total_passed,
            "avg_wait_seconds": self.avg_wait_seconds,
            "congestion": self.congestion,
            "emergency_active": self.emergency_active,
            "emergency_direction": self.emergency_direction,
            "lanes": {d: self.lanes[d].to_dict() for d in DIRECTIONS if d in self.lanes},
        }


@dataclass
class SimulationEvent:
    """Represents an audit event in the traffic control center."""
    message: str
    kind: str = "info"  # "info" | "success" | "warning" | "signal" | "emergency" | "error"
    junction: Optional[str] = None
    time: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))

    def to_dict(self) -> Dict:
        return {
            "time": self.time,
            "message": self.message,
            "kind": self.kind,
            "junction": self.junction,
        }
