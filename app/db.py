"""
Minimal SQLite storage. One row per (series, date). Safe to re-run,
inserts are idempotent via INSERT OR REPLACE.
"""

import sqlite3
from contextlib import contextmanager

DB_PATH = "rates.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rates (
                series_id TEXT NOT NULL,
                date TEXT NOT NULL,
                value REAL NOT NULL,
                PRIMARY KEY (series_id, date)
            )
            """
        )


def upsert_observations(series_id: str, observations: list[dict]):
    with get_conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO rates (series_id, date, value) VALUES (?, ?, ?)",
            [(series_id, obs["date"], obs["value"]) for obs in observations],
        )


def get_history(series_id: str, limit: int = 180) -> list[dict]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT date, value FROM rates WHERE series_id = ? ORDER BY date DESC LIMIT ?",
            (series_id, limit),
        )
        rows = cur.fetchall()
    rows.reverse()
    return [{"date": d, "value": v} for d, v in rows]


def get_latest(series_id: str) -> dict | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT date, value FROM rates WHERE series_id = ? ORDER BY date DESC LIMIT 1",
            (series_id,),
        )
        row = cur.fetchone()
    if row:
        return {"date": row[0], "value": row[1]}
    return None
