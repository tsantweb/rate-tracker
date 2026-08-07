import logging

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.db import get_history, get_latest, init_db
from app.fred_client import SERIES
from app.scheduler import refresh_all_series, start_scheduler

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Rate Index Tracker")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

_scheduler = None


@app.on_event("startup")
def on_startup():
    global _scheduler
    init_db()
    # Populate immediately on first boot so the dashboard isn't empty,
    # then let the scheduler take over for daily refreshes.
    # Wrapped in try/except: a missing or bad FRED_API_KEY should not
    # take the whole server down, it should just leave the dashboard
    # showing "no data yet" until the key is fixed and refreshed.
    try:
        for series_id in SERIES:
            if get_latest(series_id) is None:
                refresh_all_series()
                break
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("rate-tracker").error(
            "Startup refresh failed, server will still start: %s", exc
        )

    try:
        _scheduler = start_scheduler()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("rate-tracker").error("Scheduler failed to start: %s", exc)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/rates")
def current_rates():
    """Latest value for every tracked series."""
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
    """Force a refresh outside the scheduled cron times."""
    refresh_all_series()
    return {"status": "ok"}
