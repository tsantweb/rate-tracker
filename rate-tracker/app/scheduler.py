import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.db import upsert_observations
from app.fred_client import FredClient, SERIES

logger = logging.getLogger("rate-tracker")


def refresh_all_series():
    try:
        client = FredClient()
    except Exception as exc:  # noqa: BLE001
        logger.error("Cannot refresh, FredClient init failed: %s", exc)
        return

    for series_id in SERIES:
        try:
            obs = client.get_series(series_id, limit=365)
            upsert_observations(series_id, obs)
            logger.info("Refreshed %s: %s observations", series_id, len(obs))
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to refresh %s: %s", series_id, exc)


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    # FRED/NY Fed publish daily series in the morning ET. Pulling at
    # 10:00 and again at 16:00 covers late postings and revisions.
    scheduler.add_job(refresh_all_series, "cron", hour=10, minute=0)
    scheduler.add_job(refresh_all_series, "cron", hour=16, minute=0)
    scheduler.start()
    return scheduler
