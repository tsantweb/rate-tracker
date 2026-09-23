"""
Minimal SQLite storage. One row per (series, date). Safe to re-run,
inserts are idempotent via INSERT OR REPLACE.
"""

import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta

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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )


def upsert_observations(series_id: str, observations: list[dict]):
    with get_conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO rates (series_id, date, value) VALUES (?, ?, ?)",
            [(series_id, obs["date"], obs["value"]) for obs in observations],
        )


def get_last_refresh_date() -> str | None:
    """
    The date (server local, YYYY-MM-DD) we last attempted a refresh.
    This is deliberately separate from any series' actual published
    date, source publish lags (Treasury/Prime post later in the day
    than SOFR) shouldn't be confused with our own app being stale.
    """
    with get_conn() as conn:
        cur = conn.execute("SELECT value FROM meta WHERE key = 'last_refresh_date'")
        row = cur.fetchone()
    return row[0] if row else None


def set_last_refresh_date(date_str: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_refresh_date', ?)",
            (date_str,),
        )


def get_history(series_id: str, days: int | None = None) -> list[dict]:
    """
    Full history if days is None, otherwise everything from `days`
    calendar days ago through today. Filtering by date rather than
    row count so weekly series (MORTGAGE30US) and daily series behave
    consistently for a given lookback window.
    """
    with get_conn() as conn:
        if days is not None:
            cutoff = (date.today() - timedelta(days=days)).isoformat()
            cur = conn.execute(
                "SELECT date, value FROM rates WHERE series_id = ? AND date >= ? ORDER BY date ASC",
                (series_id, cutoff),
            )
        else:
            cur = conn.execute(
                "SELECT date, value FROM rates WHERE series_id = ? ORDER BY date ASC",
                (series_id,),
            )
        rows = cur.fetchall()
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
