"""Analytics engine computing aggregate performance metrics from recorded SQLite telemetry.

All metrics are calculated strictly from recorded database tables rather than
runtime memory or invented dashboard values.

Metrics Defined:
1. Average Waiting Time: Mean delay (in seconds) experienced by vehicles waiting at red signals.
2. Average Queue Length: Mean number of queued vehicles held at intersection approaches.
3. Network Throughput: Total cumulative vehicles successfully cleared across active intersections.
4. Congestion Distribution: Percentage breakdown of intersection states (Low, Moderate, Heavy).
5. Signal Utilization: Percentage of time each approach spends in GREEN, YELLOW, and RED.
6. Baseline Comparison: Empirical comparison of Fixed-Time vs Adaptive control under identical seeds.
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid
from database.connection import get_db_connection
from database.repository import TrafficRepository

logger = logging.getLogger("traffic_system.analytics")


class TrafficAnalytics:
    """Computes verifiable traffic engineering analytics from persistent SQLite data."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self.repo = TrafficRepository(db_path)

    def get_session_analytics(
        self,
        session_id: Optional[str] = None,
        junction_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculates aggregated performance analytics for a session or time window."""
        clauses = []
        params = []

        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if junction_id:
            clauses.append("junction_id = ?")
            params.append(junction_id)
        if start_time:
            clauses.append("timestamp >= ?")
            params.append(start_time)
        if end_time:
            clauses.append("timestamp <= ?")
            params.append(end_time)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        with get_db_connection(self.db_path) as conn:
            # 1. Overall Snapshot Averages
            q_stats = f"""
                SELECT
                    COUNT(*) as total_samples,
                    COALESCE(AVG(avg_wait_seconds), 0.0) as avg_wait_seconds,
                    COALESCE(MAX(avg_wait_seconds), 0.0) as peak_wait_seconds,
                    COALESCE(AVG(total_vehicles), 0.0) as avg_queue_length,
                    COALESCE(MAX(total_vehicles), 0) as peak_queue_length,
                    COALESCE(MAX(total_passed) - MIN(total_passed), 0) as session_throughput
                FROM intersection_snapshots
                {where}
            """
            stats = conn.execute(q_stats, params).fetchone() or {}

            # Handle case where there are no records
            if not stats.get("total_samples"):
                return {
                    "has_data": False,
                    "session_id": session_id,
                    "junction_id": junction_id,
                    "avg_wait_seconds": 0.0,
                    "peak_wait_seconds": 0.0,
                    "avg_queue_length": 0.0,
                    "peak_queue_length": 0,
                    "session_throughput": 0,
                    "congestion_distribution": {"Low": 0.0, "Moderate": 0.0, "Heavy": 0.0},
                    "directional_breakdown": {},
                    "signal_utilization": {},
                }

            # 2. Congestion Distribution (%)
            q_cong = f"""
                SELECT congestion_level, COUNT(*) as count
                FROM intersection_snapshots
                {where}
                GROUP BY congestion_level
            """
            cong_rows = conn.execute(q_cong, params).fetchall()
            total_samples = stats["total_samples"]
            cong_dist = {"Low": 0.0, "Moderate": 0.0, "Heavy": 0.0}
            for row in cong_rows:
                lvl = row["congestion_level"]
                if lvl in cong_dist and total_samples > 0:
                    cong_dist[lvl] = round((row["count"] / total_samples) * 100.0, 1)

            # 3. Directional Breakdown from lane_metrics
            q_dirs = f"""
                SELECT
                    direction,
                    COALESCE(AVG(vehicles), 0.0) as avg_vehicles,
                    COALESCE(MAX(vehicles), 0) as max_vehicles,
                    COALESCE(AVG(waiting_seconds), 0.0) as avg_waiting_sec,
                    COALESCE(MAX(waiting_seconds), 0.0) as max_waiting_sec,
                    COALESCE(AVG(priority_score), 0.0) as avg_priority_score
                FROM lane_metrics
                {where}
                GROUP BY direction
            """
            dir_rows = conn.execute(q_dirs, params).fetchall()
            dir_breakdown = {
                row["direction"]: {
                    "avg_queue": round(row["avg_vehicles"], 1),
                    "max_queue": row["max_vehicles"],
                    "avg_wait": round(row["avg_waiting_sec"], 1),
                    "max_wait": round(row["max_waiting_sec"], 1),
                    "avg_priority_score": round(row["avg_priority_score"], 2),
                }
                for row in dir_rows
            }

            # 4. Signal Utilization (% of time spent in GREEN, YELLOW, RED)
            q_util = f"""
                SELECT direction, signal, COUNT(*) as count
                FROM lane_metrics
                {where}
                GROUP BY direction, signal
            """
            util_rows = conn.execute(q_util, params).fetchall()
            signal_util: Dict[str, Dict[str, float]] = {}
            dir_totals: Dict[str, int] = {}
            for r in util_rows:
                d = r["direction"]
                dir_totals[d] = dir_totals.get(d, 0) + r["count"]

            for r in util_rows:
                d = r["direction"]
                s = r["signal"]
                if d not in signal_util:
                    signal_util[d] = {"GREEN": 0.0, "YELLOW": 0.0, "RED": 0.0}
                total = dir_totals.get(d, 1)
                signal_util[d][s] = round((r["count"] / total) * 100.0, 1)

            return {
                "has_data": True,
                "session_id": session_id,
                "junction_id": junction_id,
                "total_samples": stats["total_samples"],
                "avg_wait_seconds": round(stats["avg_wait_seconds"], 1),
                "peak_wait_seconds": round(stats["peak_wait_seconds"], 1),
                "avg_queue_length": round(stats["avg_queue_length"], 1),
                "peak_queue_length": stats["peak_queue_length"],
                "session_throughput": stats["session_throughput"],
                "congestion_distribution": cong_dist,
                "directional_breakdown": dir_breakdown,
                "signal_utilization": signal_util,
            }

    def run_baseline_comparison(
        self,
        duration_ticks: int = 60,
        seed: int = 42,
        scenario: str = "medium",
    ) -> Dict[str, Any]:
        """Executes side-by-side comparative simulation runs (Fixed-Time vs Adaptive) with the same seed.

        Both runs are recorded into the SQLite database. Performance metrics are calculated
        strictly from recorded database data to provide verifiable proof for examiners.
        """
        from core.simulation_engine import SimulationEngine
        from config import DIRECTIONS, SIGNAL_PHASES

        comparison_id = f"cmp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        timestamp = datetime.now().isoformat(timespec="seconds")

        fixed_session_id = f"sess_fixed_{uuid.uuid4().hex[:8]}"
        adaptive_session_id = f"sess_adaptive_{uuid.uuid4().hex[:8]}"

        # 1. Run Fixed-Time Baseline Simulation
        self.repo.create_session(
            session_id=fixed_session_id,
            control_mode="fixed_time",
            scenario=scenario,
            seed=seed,
            is_baseline_run=1,
            notes=f"Fixed-Time baseline for comparison {comparison_id}",
        )

        engine_fixed = SimulationEngine(
            seed=seed,
            autostart=False,
            scenario=scenario,
        )
        engine_fixed.auto_mode = False  # Fixed-time round robin

        # Fixed-time parameters: 18s green per direction in fixed rotation
        fixed_green_duration = 18
        fixed_dir_idx = 0
        fixed_remaining = fixed_green_duration

        for step_idx in range(1, duration_ticks + 1):
            # Enforce fixed-time schedule
            fixed_remaining -= 1
            if fixed_remaining <= 0:
                fixed_dir_idx = (fixed_dir_idx + 1) % len(DIRECTIONS)
                target_d = DIRECTIONS[fixed_dir_idx]
                for j in engine_fixed.junctions.values():
                    engine_fixed.manual_override(j.id, target_d)
                fixed_remaining = fixed_green_duration

            engine_fixed.step()

            # Record step to database
            for j in engine_fixed.junctions.values():
                self.repo.record_step_snapshot(
                    session_id=fixed_session_id,
                    tick=step_idx,
                    timestamp=datetime.now().isoformat(timespec="seconds"),
                    junction_id=j.id,
                    active_direction=j.active_direction,
                    current_phase=j.current_phase,
                    phase_remaining=j.phase_remaining,
                    total_vehicles=j.total_vehicles,
                    total_passed=j.total_passed,
                    avg_wait_seconds=j.avg_wait_seconds,
                    congestion_level=j.congestion,
                    emergency_active=j.emergency_active,
                    lanes_dict={d: l.to_dict() for d, l in j.lanes.items()},
                )

        self.repo.close_session(fixed_session_id)

        # 2. Run Adaptive Signal Optimization Simulation
        self.repo.create_session(
            session_id=adaptive_session_id,
            control_mode="adaptive",
            scenario=scenario,
            seed=seed,
            is_baseline_run=0,
            notes=f"Adaptive run for comparison {comparison_id}",
        )

        engine_adaptive = SimulationEngine(
            seed=seed,
            autostart=False,
            scenario=scenario,
        )
        engine_adaptive.auto_mode = True

        for step_idx in range(1, duration_ticks + 1):
            engine_adaptive.step()

            # Record step to database
            for j in engine_adaptive.junctions.values():
                self.repo.record_step_snapshot(
                    session_id=adaptive_session_id,
                    tick=step_idx,
                    timestamp=datetime.now().isoformat(timespec="seconds"),
                    junction_id=j.id,
                    active_direction=j.active_direction,
                    current_phase=j.current_phase,
                    phase_remaining=j.phase_remaining,
                    total_vehicles=j.total_vehicles,
                    total_passed=j.total_passed,
                    avg_wait_seconds=j.avg_wait_seconds,
                    congestion_level=j.congestion,
                    emergency_active=j.emergency_active,
                    lanes_dict={d: l.to_dict() for d, l in j.lanes.items()},
                )

        self.repo.close_session(adaptive_session_id)

        # 3. Compute Metrics strictly from Database
        fixed_stats = self.get_session_analytics(session_id=fixed_session_id)
        adaptive_stats = self.get_session_analytics(session_id=adaptive_session_id)

        f_wait = fixed_stats["avg_wait_seconds"]
        a_wait = adaptive_stats["avg_wait_seconds"]
        wait_reduction = round(((f_wait - a_wait) / max(0.1, f_wait)) * 100.0, 1)

        f_thru = fixed_stats["session_throughput"]
        a_thru = adaptive_stats["session_throughput"]
        throughput_increase = round(((a_thru - f_thru) / max(1, f_thru)) * 100.0, 1)

        f_queue = fixed_stats["avg_queue_length"]
        a_queue = adaptive_stats["avg_queue_length"]

        comparison_data = {
            "comparison_id": comparison_id,
            "timestamp": timestamp,
            "duration_ticks": duration_ticks,
            "seed": seed,
            "scenario": scenario,
            "fixed_session_id": fixed_session_id,
            "adaptive_session_id": adaptive_session_id,
            "fixed_avg_wait": f_wait,
            "adaptive_avg_wait": a_wait,
            "wait_reduction_pct": wait_reduction,
            "fixed_throughput": f_thru,
            "adaptive_throughput": a_thru,
            "throughput_increase_pct": throughput_increase,
            "fixed_avg_queue": f_queue,
            "adaptive_avg_queue": a_queue,
            "fixed_stats": fixed_stats,
            "adaptive_stats": adaptive_stats,
        }

        # Persist to baseline_comparisons table
        self.repo.save_baseline_comparison(comparison_data)

        return comparison_data
