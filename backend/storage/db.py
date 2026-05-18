"""SQLite bootstrap and connection helpers for the web backend."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection configured for dict-like row access."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def bootstrap(db_path: str | Path) -> None:
    """Create the web backend schema if it does not already exist."""
    with connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                path TEXT NOT NULL UNIQUE,
                category TEXT,
                value INTEGER,
                connection_info TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                challenge_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                executor TEXT NOT NULL,
                model_specs TEXT NOT NULL DEFAULT '[]',
                no_submit INTEGER NOT NULL DEFAULT 0,
                generate_writeup INTEGER NOT NULL DEFAULT 1,
                result_flag TEXT,
                summary TEXT,
                error_summary TEXT,
                cost_usd REAL,
                log_path TEXT,
                started_at TEXT,
                finished_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (challenge_id) REFERENCES challenges(id)
            );
            """
        )
        existing_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(runs)").fetchall()
        }
        run_columns = {
            "model_specs": "TEXT NOT NULL DEFAULT '[]'",
            "no_submit": "INTEGER NOT NULL DEFAULT 0",
            "generate_writeup": "INTEGER NOT NULL DEFAULT 1",
            "result_flag": "TEXT",
            "error_summary": "TEXT",
            "cost_usd": "REAL",
            "log_path": "TEXT",
            "writeup_path": "TEXT",
            "winning_agent": "TEXT",
            "agent_session_available": "INTEGER NOT NULL DEFAULT 0",
            "agent_skills": "TEXT NOT NULL DEFAULT '[]'",
            "started_at": "TEXT",
            "finished_at": "TEXT",
        }
        for column, definition in run_columns.items():
            if column not in existing_columns:
                connection.execute(f"ALTER TABLE runs ADD COLUMN {column} {definition}")
