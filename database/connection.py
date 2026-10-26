"""SQLite connection factory, WAL mode initialization, and thread safety management.
"""

from contextlib import contextmanager
import os
import sqlite3
import threading
from typing import Generator, Optional
from config import BASE_DIR

DEFAULT_DB_PATH = os.path.join(BASE_DIR, "traffic_management.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")

_local = threading.local()


def get_db_path() -> str:
    """Returns the absolute path to the active SQLite database file."""
    return os.environ.get("TRAFFIC_DB_PATH", DEFAULT_DB_PATH)


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    """Row factory converting SQLite query results into clean Python dictionaries."""
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


def create_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Creates a configured SQLite connection with foreign keys and WAL mode."""
    target_path = db_path or get_db_path()
    conn = sqlite3.connect(target_path, timeout=10.0, check_same_thread=False)
    conn.row_factory = dict_factory
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


@contextmanager
def get_db_connection(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager providing a safe, isolated database connection with automatic commit/rollback."""
    conn = create_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Initializes the database tables, constraints, and indexes using schema.sql."""
    target_path = db_path or get_db_path()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with get_db_connection(target_path) as conn:
        conn.executescript(schema_sql)


def reset_db(db_path: Optional[str] = None) -> None:
    """Clears all records from the database and re-applies the initial schema."""
    target_path = db_path or get_db_path()
    with get_db_connection(target_path) as conn:
        # Disable foreign keys temporarily for clean wipe
        conn.execute("PRAGMA foreign_keys = OFF;")
        tables = [
            "baseline_comparisons",
            "lane_metrics",
            "signal_phase_logs",
            "audit_event_logs",
            "intersection_snapshots",
            "simulation_sessions",
        ]
        for t in tables:
            conn.execute(f"DROP TABLE IF EXISTS {t};")
        conn.execute("PRAGMA foreign_keys = ON;")

    init_db(target_path)

