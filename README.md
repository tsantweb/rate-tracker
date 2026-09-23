# Rate Index Tracker

FastAPI app that pulls prime rate, SOFR, and Treasury data from FRED, stores it in SQLite, and shows it on a dashboard with current values and a history chart.

## What it tracks

Prime, overnight SOFR, 30/90/180 day compounded SOFR averages, Fed Funds effective rate, 1/5/7/10/30-Year Treasury, and the Freddie Mac 30-Year Fixed Mortgage Average. See `app/fred_client.py` for the full list and series IDs.

These are free, backward looking / spot series from FRED. They are not the same as CME Term SOFR (1m/3m/6m forward looking), which is licensed data.

## Keeping data fresh

Three layers, since Render's free tier sleeps after inactivity and an internal scheduler alone isn't reliable there:

1. `/api/rates` checks whether the newest data point is more than 2 days old, and refreshes automatically before responding if so. This means a dashboard visit always shows current data even if nothing else fired.
2. The internal APScheduler (`app/scheduler.py`) refreshes at 10:00 and 16:00 server time, works fine if you're running this somewhere that doesn't sleep (a VPS, a paid Render instance).
3. `.github/workflows/daily-refresh.yml` pings `/api/refresh` once a day via GitHub Actions, which is free and doesn't sleep, so the data stays current even if nobody opens the dashboard that day. Update the URL in that file if your Render URL changes. You can also trigger it manually from the repo's Actions tab.

## Local setup

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env, add your free key from https://fred.stlouisfed.org/docs/api/api_key.html
export $(cat .env | xargs)

uvicorn app.main:app --reload
```

Visit http://localhost:8000.

## Deploying

Plain FastAPI app with a Dockerfile, runs anywhere that runs a container or a Python process.

**Render**
Connect the repo, choose Docker as the environment explicitly when creating the service, set `FRED_API_KEY` as an environment variable.

**Any VPS**
```bash
docker build -t rate-tracker .
docker run -d -p 8000:8000 -e FRED_API_KEY=your_key_here rate-tracker
```

## Notes on the SQLite file

`rates.db` is created next to the app on first run. On most container platforms the filesystem is ephemeral, wiped on redeploy, which is fine since the app re-seeds a year of history from FRED on startup if the database is empty or stale.

## Extending

Add more FRED series by adding entries to `SERIES` in `app/fred_client.py`. Swap SQLite for Postgres if you outgrow a single file.
