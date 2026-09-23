"""
Unofficial, intraday treasury yield quotes via Yahoo Finance.

This is NOT the official Treasury constant maturity yield (that's
FRED/DGS*, published once daily after close). This is a live market
quote that moves throughout the trading day. Use it as a directional
signal, not as the rate you'd actually cite.

Built on yfinance (1.x), an unofficial library against a reverse
engineered Yahoo endpoint, not a published API. Current versions
handle Yahoo's cookie/crumb authentication and browser impersonation
internally, no manual session setup needed here. It can still break
without notice if Yahoo changes something on their end, that's
expected, not a bug to chase.
"""

import logging

import yfinance as yf

logger = logging.getLogger("rate-tracker")

# Yahoo's index tickers for treasury yields. Historically these were
# sometimes scaled 10x (the old CBOE index convention), current Yahoo
# quote pages show the plain percentage. We normalize defensively
# below rather than hardcode an assumption that could silently break.
TICKERS = {
    "^IRX": {"label": "13-Week Treasury Bill (intraday)", "short": "3M T-Bill"},
    "^FVX": {"label": "5-Year Treasury (intraday)", "short": "5Y Treasury"},
    "^TNX": {"label": "10-Year Treasury (intraday)", "short": "10Y Treasury"},
    "^TYX": {"label": "30-Year Treasury (intraday)", "short": "30Y Treasury"},
    "ZQ=F": {
        "label": "30-Day Fed Funds Futures, implied rate (intraday)",
        "short": "Fed Funds Implied",
        "is_price_quote": True,
    },
}


def _normalize(value: float) -> float:
    """Treasury yields are always in a 0-15% range in practice. If
    Yahoo hands back the old 10x scaled index value instead of the
    plain percentage, this brings it back into range."""
    if value > 20:
        return value / 10
    return value


def get_intraday_quotes() -> dict:
    """
    Returns {ticker: {label, short, value, as_of}} for each tracked
    ticker. Any ticker that fails to fetch is simply omitted, not
    treated as a fatal error, since this whole feature is expected
    to occasionally break.
    """
    results = {}
    for ticker, meta in TICKERS.items():
        try:
            info = yf.Ticker(ticker).fast_info
            price = info.get("last_price") or info.get("lastPrice")
            if price is None:
                raise ValueError("no last_price in fast_info")
            price = float(price)

            if meta.get("is_price_quote"):
                # Fed Funds futures (and Treasury note/bond futures)
                # quote as 100 minus the implied rate, not the rate
                # itself. Convert here so the dashboard always shows
                # a rate, consistent with every other card.
                value = 100 - price
            else:
                value = _normalize(price)

            results[ticker] = {
                **{k: v for k, v in meta.items() if k != "is_price_quote"},
                "value": round(value, 3),
            }
        except Exception as exc:  # noqa: BLE001
            logger.error("Intraday fetch failed for %s: %s", ticker, exc)
    return results
