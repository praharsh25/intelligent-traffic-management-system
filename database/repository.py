"""Data Access Object (DAO) and Repository for persisting and retrieving simulation telemetry.
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from database.connection import get_db_connection

logger = logging.getLogger("traffic_system.repository")


class TrafficRepository:
    """Provides validated SQL access methods for simulation sessions, telemetry, and event history."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    # Session Management
    def create_session(
        self,
        session_id: str,
        control_mode: str = "adaptive",
        scenario: str = "medium",
        seed: Optional[int] = None,
        arrival_multiplier: float = 1.0,
        min_green: int = 8,
        max_green: int = 35,
        is_baseline_run: int = 0,
        notes: Optional[str] = None,
    ) -> None:
        """Inserts a new simulation session record."""
        now = datetime.now().isoformat(timespec="seconds")
        query = """
            INSERT INTO simulation_sessions (
                session_id, created_at, control_mode, scenario, seed,
                arrival_multiplier, min_green, max_green, is_baseline_run, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with get_db_connection(self.db_path) as conn:
                conn.execute(
                    query,
                    (
                        session_id, now, control_mode, scenario, seed,
                        arrival_multiplier, min_green, max_green, is_baseline_run, notes
                    )
                )
        except Exception as e:
            logger.error(f"Failed to create simulation session {session_id}: {e}", exc_info=True)

    def close_session(self, session_id: str) -> None:
        """Marks a simulation session as concluded with ended_at timestamp."""
        now = datetime.now().isoformat(timespec="seconds")
        query = "UPDATE simulation_sessions SET ended_at = ? WHERE session_id = ?"
        try:
            with get_db_connection(self.db_path) as conn:
                conn.execute(query, (now, session_id))
        except Exception as e:
            logger.error(f"Failed to close session {session_id}: {e}", exc_info=True)

    def get_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves historical simulation sessions ordered by creation date."""
        query = """
            SELECT s.*,
                   COUNT(DISTINCT sn.id) as total_snapshots,
                   MAX(sn.tick) as max_tick,
                   MAX(sn.total_passed) as cumulative_passed
            FROM simulation_sessions s
            LEFT JOIN intersection_snapshots sn ON s.session_id = sn.session_id
            GROUP BY s.session_id
            ORDER BY s.created_at DESC
            LIMIT ?
        """
        with get_db_connection(self.db_path) as conn:
            return conn.execute(query, (limit,)).fetchall()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves details of a specific simulation session."""
        query = "SELECT * FROM simulation_sessions WHERE session_id = ?"
        with get_db_connection(self.db_path) as conn:
            return conn.execute(query, (session_id,)).fetchone()

    # Telemetry Snapshots
    def record_step_snapshot(
        self,
        session_id: str,
        tick: int,
        timestamp: str,
        junction_id: str,
        active_direction: str,
        current_phase: str,
        phase_remaining: int,
        total_vehicles: int,
        total_passed: int,
        avg_wait_seconds: float,
        congestion_level: str,
        emergency_active: bool,
        lanes_dict: Dict[str, Dict[str, Any]],
    ) -> None:
        """Persists an intersection snapshot and its granular lane approach readings."""
        query_snap = """
            INSERT INTO intersection_snapshots (
                session_id, tick, timestamp, junction_id, active_direction,
                current_phase, phase_remaining, total_vehicles, total_passed,
                avg_wait_seconds, congestion_level, emergency_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        query_lane = """
            INSERT INTO lane_metrics (
                snapshot_id, session_id, junction_id, direction, vehicles,
                waiting, waiting_seconds, signal, green_remaining, total_passed,
                cycles_without_green, priority_score, is_emergency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with get_db_connection(self.db_path) as conn:
                cur = conn.execute(
                    query_snap,
                    (
                        session_id, tick, timestamp, junction_id, active_direction,
                        current_phase, phase_remaining, total_vehicles, total_passed,
                        avg_wait_seconds, congestion_level, 1 if emergency_active else 0
                    )
                )
                snap_id = cur.lastrowid

                # Batch insert lane metrics
                lane_rows = [
                    (
                        snap_id, session_id, junction_id, direction,
                        l.get("vehicles", 0), l.get("waiting", 0), l.get("waiting_seconds", 0.0),
                        l.get("signal", "RED"), l.get("green_remaining", 0), l.get("total_passed", 0),
                        l.get("cycles_without_green", 0), l.get("priority_score", 0.0),
                        1 if l.get("is_emergency") else 0
                    )
                    for direction, l in lanes_dict.items()
                ]
                conn.executemany(query_lane, lane_rows)
        except Exception as e:
            logger.error(f"Failed to record step snapshot at tick {tick}: {e}", exc_info=True)

    # Signal Phase Transitions
    def record_signal_phase_log(
        self,
        session_id: str,
        tick: int,
        timestamp: str,
        junction_id: str,
        from_phase: str,
        to_phase: str,
        active_direction: str,
        duration_seconds: int,
        reason: str,
    ) -> None:
        """Logs an explicit signal phase transition event."""
        query = """
            INSERT INTO signal_phase_logs (
                session_id, tick, timestamp, junction_id, from_phase,
                to_phase, active_direction, duration_seconds, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with get_db_connection(self.db_path) as conn:
                conn.execute(
                    query,
                    (
                        session_id, tick, timestamp, junction_id, from_phase,
                        to_phase, active_direction, duration_seconds, reason
                    )
                )
        except Exception as e:
            logger.error(f"Failed to log signal phase transition: {e}", exc_info=True)

    # Audit Events
    def record_audit_event(
        self,
        session_id: str,
        tick: int,
        timestamp: str,
        kind: str,
        message: str,
        junction_id: Optional[str] = None,
    ) -> None:
        """Records an audit event to SQLite."""
        query = """
            INSERT INTO audit_event_logs (
                session_id, tick, timestamp, kind, message, junction_id
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        try:
            with get_db_connection(self.db_path) as conn:
                conn.execute(query, (session_id, tick, timestamp, kind, message, junction_id))
        except Exception as e:
            logger.error(f"Failed to record audit event: {e}", exc_info=True)

    # Filtered Query Methods
    def get_snapshots(
        self,
        session_id: Optional[str] = None,
        junction_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Queries historical intersection snapshots with filtering."""
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
        query = f"""
            SELECT * FROM intersection_snapshots
            {where}
            ORDER BY id DESC
            LIMIT ?
        """
        params.append(limit)

        with get_db_connection(self.db_path) as conn:
            return conn.execute(query, params).fetchall()

    def get_signal_logs(
        self,
        session_id: Optional[str] = None,
        junction_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieves signal transition logs with optional filters."""
        clauses = []
        params = []
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if junction_id:
            clauses.append("junction_id = ?")
            params.append(junction_id)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        query = f"SELECT * FROM signal_phase_logs {where} ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with get_db_connection(self.db_path) as conn:
            return conn.execute(query, params).fetchall()

    def get_audit_events(
        self,
        session_id: Optional[str] = None,
        kind: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieves audit events with optional filters."""
        clauses = []
        params = []
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        query = f"SELECT * FROM audit_event_logs {where} ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with get_db_connection(self.db_path) as conn:
            return conn.execute(query, params).fetchall()

    # Baseline Comparisons
    def save_baseline_comparison(self, data: Dict[str, Any]) -> None:
        """Stores comparative benchmark results between fixed-time and adaptive controllers."""
        query = """
            INSERT INTO baseline_comparisons (
                comparison_id, timestamp, duration_ticks, seed, scenario,
                fixed_session_id, adaptive_session_id, fixed_avg_wait,
                adaptive_avg_wait, wait_reduction_pct, fixed_throughput,
                adaptive_throughput, throughput_increase_pct, fixed_avg_queue,
                adaptive_avg_queue
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with get_db_connection(self.db_path) as conn:
                conn.execute(
                    query,
                    (
                        data["comparison_id"], data["timestamp"], data["duration_ticks"],
                        data["seed"], data["scenario"], data["fixed_session_id"],
                        data["adaptive_session_id"], data["fixed_avg_wait"],
                        data["adaptive_avg_wait"], data["wait_reduction_pct"],
                        data["fixed_throughput"], data["adaptive_throughput"],
                        data["throughput_increase_pct"], data["fixed_avg_queue"],
                        data["adaptive_avg_queue"]
                    )
                )
        except Exception as e:
            logger.error(f"Failed to save baseline comparison: {e}", exc_info=True)

    def get_baseline_comparisons(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves recent baseline comparisons."""
        query = "SELECT * FROM baseline_comparisons ORDER BY id DESC LIMIT ?"
        with get_db_connection(self.db_path) as conn:
            return conn.execute(query, (limit,)).fetchall()
