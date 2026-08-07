# Rate Index Tracker

FastAPI app that pulls prime rate and SOFR data from FRED, stores it in SQLite, and shows it on a small dashboard with current values and a history chart.

## What it tracks

- Bank Prime Loan Rate (`DPRIME`)
- Overnight SOFR (`SOFR`)
- 30/90/180 day compounded SOFR averages (`SOFR30DAYAVG`, `SOFR90DAYAVG`, `SOFR180DAYAVG`)

These are free, backward looking series. They are not the same as CME Term SOFR (1m/3m/6m forward looking), which is licensed data. See `app/fred_client.py` for the full note on that distinction. To add CME Term SOFR, write a second client module against CME's REST API and add its series to the dashboard the same way `SERIES` is defined here.

## Local setup

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env, add your free key from https://fred.stlouisfed.org/docs/api/api_key.html
export $(cat .env | xargs)     # or use python-dotenv if you prefer

uvicorn app.main:app --reload
```

Visit http://localhost:8000. On first boot the app pulls the last year of data for each series and stores it in `rates.db`. After that it refreshes twice a day (10:00 and 16:00 server time) via a background scheduler, matched to when FRED/NY Fed typically post daily updates. You can also trigger a refresh manually:

```bash
curl -X POST http://localhost:8000/api/refresh
```

## Deploying

This is a plain FastAPI app with a Dockerfile, so it runs anywhere that runs a container or a Python process. A few options:

**Render / Railway / Fly.io**
Connect the repo, set the `FRED_API_KEY` environment variable in the platform's dashboard, deploy. All three have free or near free tiers that comfortably handle this workload.

**Any VPS (DigitalOcean, Linode, your own box)**
```bash
docker build -t rate-tracker .
docker run -d -p 8000:8000 -e FRED_API_KEY=your_key_here rate-tracker
```

**Behind a reverse proxy**
Point nginx/Caddy at port 8000, add TLS, done.

## Notes on the SQLite file

`rates.db` is created next to the app on first run. On most container platforms the filesystem is ephemeral (wiped on redeploy), which is fine here since the app re-seeds a year of history from FRED on startup if the database is empty. If you want data to persist across redeploys, mount a volume at the app's working directory, or point `DB_PATH` in `app/db.py` at a mounted path.

## Extending

- Add more FRED series by adding entries to `SERIES` in `app/fred_client.py`.
- Add Treasury yields, Fed Funds effective rate, or SONIA/EURIBOR the same way if you need them, FRED carries all of those under different series IDs.
- Swap SQLite for Postgres if you outgrow a single file, the `db.py` module is small enough to rewrite quickly.
