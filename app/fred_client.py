"""
Thin client for the FRED (Federal Reserve Economic Data) API.

Free API key: https://fred.stlouisfed.org/docs/api/api_key.html
Docs: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
"""

import os
import requests

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Series we track. Add or remove as needed.
# NOTE: These are free, backward looking / spot rates from FRED.
# They are NOT the same as CME Term SOFR (1m/3m/6m forward looking),
# which is licensed data. SOFR30DAYAVG/90/180 are compounded averages
# of realized SOFR, the closest free proxy, not a substitute for
# actual loan document Term SOFR.
SERIES = {
    "DPRIME": {
        "label": "Bank Prime Loan Rate",
        "short": "Prime",
    },
    "SOFR": {
        "label": "Secured Overnight Financing Rate (Overnight)",
        "short": "SOFR (O/N)",
    },
    "SOFR30DAYAVG": {
        "label": "30-Day Average SOFR (compounded)",
        "short": "SOFR 30D Avg",
    },
    "SOFR90DAYAVG": {
        "label": "90-Day Average SOFR (compounded)",
        "short": "SOFR 90D Avg",
    },
    "SOFR180DAYAVG": {
        "label": "180-Day Average SOFR (compounded)",
        "short": "SOFR 180D Avg",
    },
    "DFF": {
        "label": "Federal Funds Effective Rate",
        "short": "Fed Funds",
    },
    "DGS1": {
        "label": "1-Year Treasury Constant Maturity",
        "short": "1Y Treasury",
    },
    "DGS5": {
        "label": "5-Year Treasury Constant Maturity",
        "short": "5Y Treasury",
    },
    "DGS7": {
        "label": "7-Year Treasury Constant Maturity",
        "short": "7Y Treasury",
    },
    "DGS10": {
        "label": "10-Year Treasury Constant Maturity",
        "short": "10Y Treasury",
    },
    "DGS30": {
        "label": "30-Year Treasury Constant Maturity",
        "short": "30Y Treasury",
    },
    "MORTGAGE30US": {
        "label": "Freddie Mac 30-Year Fixed Rate Mortgage Average (weekly)",
        "short": "30Y Fixed Mtg",
    },
}


class FredClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "FRED_API_KEY is not set. Get a free key at "
                "https://fred.stlouisfed.org/docs/api/api_key.html "
                "and set it as an environment variable."
            )

    def get_series(self, series_id: str, limit: int = 180) -> list[dict]:
        """
        Returns a list of {date, value} dicts, most recent last.
        FRED marks missing observations as '.', those are dropped.
        """
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        resp = requests.get(FRED_BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        observations = [
            {"date": obs["date"], "value": float(obs["value"])}
            for obs in data.get("observations", [])
            if obs.get("value") not in (None, ".")
        ]
        observations.reverse()  # oldest first
        return observations

    def get_all_current(self) -> dict:
        """
        Returns the latest value for every tracked series.
        """
        results = {}
        for series_id, meta in SERIES.items():
            obs = self.get_series(series_id, limit=1)
            if obs:
                results[series_id] = {
                    **meta,
                    "date": obs[-1]["date"],
                    "value": obs[-1]["value"],
                }
        return results
