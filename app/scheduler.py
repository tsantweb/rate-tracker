import logging
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler

from app.db import set_last_refresh_date, upsert_observations
from app.fred_client import FredClient, SERIES

logger = logging.getLogger("rate-tracker")


def refresh_all_series():
    try:
        client = FredClient()
    except Exception as exc:  # noqa: BLE001
        logger.error("Cannot refresh, FredClient init failed: %s", exc)
        return

    any_success = False
    for series_id in SERIES:
        try:
            obs = client.get_series(series_id, limit=365)
            upsert_observations(series_id, obs)
            any_success = True
            logger.info("Refreshed %s: %s observations", series_id, len(obs))
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to refresh %s: %s", series_id, exc)

    if any_success:
        # Record that we attempted a refresh today, independent of
        # what publish date the fetched observations actually carry.
        # Treasury/Prime/Fed Funds post later in the day than SOFR,
        # so a data date lagging by a day is often just the source,
        # not us failing to try.
        set_last_refresh_date(date.today().isoformat())


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    # FRED/NY Fed publish daily series in the morning ET. Pulling at
    # 10:00 and again at 16:00 covers late postings and revisions.
    # NOTE: this only fires if the process is actually running at
    # that time. On Render's free tier the service sleeps after
    # inactivity, so this alone is not reliable, see the freshness
    # check on /api/rates and the external GitHub Actions ping.
    scheduler.add_job(refresh_all_series, "cron", hour=10, minute=0)
    scheduler.add_job(refresh_all_series, "cron", hour=16, minute=0)
    scheduler.start()
    return scheduler
