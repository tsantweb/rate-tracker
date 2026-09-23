import logging
from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.db import get_history, get_latest, init_db
from app.fred_client import SERIES
from app.scheduler import refresh_all_series, start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rate-tracker")

app = FastAPI(title="Rate Index Tracker")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

_scheduler = None

# How stale the newest data point can be before we force a refresh
# on the next request. 2 days covers weekends without over triggering,
# daily FRED series post same day, MORTGAGE30US is weekly so it will
# always look "stale" by this measure, that's expected and harmless,
# it just means that one series gets checked every request.
MAX_STALE_DAYS = 2


def _is_stale() -> bool:
    latest = get_latest("DPRIME")  # daily series, good freshness proxy
    if latest is None:
        return True
    try:
        latest_date = date.fromisoformat(latest["date"])
    except ValueError:
        return True
    return (date.today() - latest_date) > timedelta(days=MAX_STALE_DAYS)


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
def history(series_id: str, limit: int = 180):
    if series_id not in SERIES:
        return {"error": f"unknown series_id: {series_id}"}
    return {
        "series_id": series_id,
        "meta": SERIES[series_id],
        "observations": get_history(series_id, limit=limit),
    }


@app.post("/api/refresh")
def manual_refresh():
    """Force a refresh outside the scheduled cron times. Also the
    endpoint an external scheduler (GitHub Actions, cron-job.org)
    should hit daily."""
    refresh_all_series()
    return {"status": "ok"}
