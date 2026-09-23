import logging
from datetime import date

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.db import get_history, get_last_refresh_date, get_latest, init_db
from app.fred_client import SERIES
from app.scheduler import refresh_all_series, start_scheduler
from app.yahoo_client import get_intraday_quotes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rate-tracker")

app = FastAPI(title="Rate Index Tracker")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

_scheduler = None


def _is_stale() -> bool:
    """
    True if we haven't successfully attempted a refresh yet today.
    Deliberately not based on any single series' published date,
    Treasury/Prime/Fed Funds post later in the day than SOFR, so
    using a series' own date as the freshness signal produces false
    negatives during the part of the day before those post.
    """
    last = get_last_refresh_date()
    return last != date.today().isoformat()


@app.on_event("startup")
def on_startup():
    global _scheduler
    init_db()
    try:
        if _is_stale():
            refresh_all_series()
    except Exception as exc:  # noqa: BLE001
        logger.error("Startup refresh failed, server will still start: %s", exc)

    try:
        _scheduler = start_scheduler()
    except Exception as exc:  # noqa: BLE001
        logger.error("Scheduler failed to start: %s", exc)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/rates")
def current_rates():
    """
    Latest value for every tracked series. Refreshes first if the
    data looks stale, this is what keeps the dashboard current even
    if the internal scheduler never fired because the service was
    asleep, or if a GitHub Actions ping hasn't run yet today.
    """
    if _is_stale():
        refresh_all_series()

    result = {}
    for series_id, meta in SERIES.items():
        latest = get_latest(series_id)
        result[series_id] = {**meta, **(latest or {})}
    return result


@app.get("/api/history/{series_id}")
def history(series_id: str, days: int | None = None):
    """days omitted or null returns full stored history (Max)."""
    if series_id not in SERIES:
        return {"error": f"unknown series_id: {series_id}"}
    return {
        "series_id": series_id,
        "meta": SERIES[series_id],
        "observations": get_history(series_id, days=days),
    }


@app.post("/api/refresh")
def manual_refresh():
    """Force a refresh outside the scheduled cron times. Also the
    endpoint an external scheduler (GitHub Actions, cron-job.org)
    should hit daily."""
    refresh_all_series()
    return {"status": "ok"}


@app.get("/api/intraday")
def intraday_rates():
    """
    Live, unofficial treasury quotes via Yahoo Finance. Not the same
    thing as the official FRED series, and expected to occasionally
    fail outright if Yahoo changes something, that's not a bug to
    chase, just re-hit this endpoint (the dashboard's refresh button
    does exactly that).
    """
    return get_intraday_quotes()
