-- SQLite Database Schema for Intelligent Traffic Management System
-- Enforces foreign keys, indexing for fast analytical queries, and timestamping

PRAGMA foreign_keys = ON;

-- 1. Simulation Sessions
CREATE TABLE IF NOT EXISTS simulation_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    ended_at TEXT,
    control_mode TEXT NOT NULL DEFAULT 'adaptive',
    scenario TEXT NOT NULL DEFAULT 'medium',
    seed INTEGER,
    arrival_multiplier REAL NOT NULL DEFAULT 1.0,
    min_green INTEGER NOT NULL DEFAULT 8,
    max_green INTEGER NOT NULL DEFAULT 35,
    is_baseline_run INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

-- 2. Intersection Snapshots (time-series header per intersection)
CREATE TABLE IF NOT EXISTS intersection_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES simulation_sessions(session_id) ON DELETE CASCADE,
    tick INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    junction_id TEXT NOT NULL,
    active_direction TEXT NOT NULL,
    current_phase TEXT NOT NULL,
    phase_remaining INTEGER NOT NULL,
    total_vehicles INTEGER NOT NULL,
    total_passed INTEGER NOT NULL,
    avg_wait_seconds REAL NOT NULL,
    congestion_level TEXT NOT NULL,
    emergency_active INTEGER NOT NULL DEFAULT 0
);

-- 3. Lane Approach Metrics (granular directional details)
CREATE TABLE IF NOT EXISTS lane_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES intersection_snapshots(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES simulation_sessions(session_id) ON DELETE CASCADE,
    junction_id TEXT NOT NULL,
    direction TEXT NOT NULL,
    vehicles INTEGER NOT NULL,
    waiting INTEGER NOT NULL,
    waiting_seconds REAL NOT NULL,
    signal TEXT NOT NULL,
    green_remaining INTEGER NOT NULL,
    total_passed INTEGER NOT NULL,
    cycles_without_green INTEGER NOT NULL,
    priority_score REAL NOT NULL,
    is_emergency INTEGER NOT NULL DEFAULT 0
);

-- 4. Signal Phase Logs (transition audit trail)
CREATE TABLE IF NOT EXISTS signal_phase_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES simulation_sessions(session_id) ON DELETE CASCADE,
    tick INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    junction_id TEXT NOT NULL,
    from_phase TEXT NOT NULL,
    to_phase TEXT NOT NULL,
    active_direction TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL,
    reason TEXT NOT NULL
);

-- 5. Audit Event Logs
CREATE TABLE IF NOT EXISTS audit_event_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES simulation_sessions(session_id) ON DELETE CASCADE,
    tick INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    junction_id TEXT
);

-- 6. Baseline Comparisons (Fixed-Time vs Adaptive Benchmarks)
CREATE TABLE IF NOT EXISTS baseline_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_id TEXT NOT NULL UNIQUE,
    timestamp TEXT NOT NULL,
    duration_ticks INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    scenario TEXT NOT NULL,
    fixed_session_id TEXT NOT NULL REFERENCES simulation_sessions(session_id),
    adaptive_session_id TEXT NOT NULL REFERENCES simulation_sessions(session_id),
    fixed_avg_wait REAL NOT NULL,
    adaptive_avg_wait REAL NOT NULL,
    wait_reduction_pct REAL NOT NULL,
    fixed_throughput INTEGER NOT NULL,
    adaptive_throughput INTEGER NOT NULL,
    throughput_increase_pct REAL NOT NULL,
    fixed_avg_queue REAL NOT NULL,
    adaptive_avg_queue REAL NOT NULL
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_snapshots_sess_junc ON intersection_snapshots(session_id, junction_id, tick);
CREATE INDEX IF NOT EXISTS idx_snapshots_time ON intersection_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_lane_metrics_lookup ON lane_metrics(session_id, junction_id, direction);
CREATE INDEX IF NOT EXISTS idx_signal_logs_lookup ON signal_phase_logs(session_id, junction_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_lookup ON audit_event_logs(session_id, timestamp);
