"""
Alpha Vantage NEWS_SENTIMENT fetcher.

Docs: https://www.alphavantage.co/documentation/#news-sentiment
Free tier: 25 requests/day (stricter than NewsAPI's 100/day — budget
accordingly if running both sources on the same schedule).

IMPORTANT — verify this against a live response before relying on it:
this endpoint's schema was confirmed via search results and well-established
public documentation, but couldn't be pulled fresh in full during
development (the build sandbox can't reach alphavantage.co — same class of
restriction that blocked NewsAPI's live calls in that same environment, and
the docs page itself was too long to fully load in one pass). The field
names below (title, summary, source, time_published, url,
overall_sentiment_score, overall_sentiment_label) reflect the endpoint's
long-stable public shape, but the parsing is written defensively — using
.get() with safe defaults — specifically so a renamed or missing field
degrades gracefully (skips that item, logs a warning) rather than crashing
the whole ingestion run. Run this against your real ALPHAVANTAGE_KEY and
check the output looks sane before trusting it for the annotation batch.

Query semantics differ from NewsAPIFetcher: `query` here is treated as a
comma-separated list of TICKER SYMBOLS (e.g. "AAPL,TSLA,MSFT"), matching
Alpha Vantage's `tickers` parameter — not a free-text search string. This
is a deliberate, documented deviation from NewsAPIFetcher's query semantics,
kept under the same BaseFetcher interface for pipeline compatibility.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from app import config
from app.ingestion.alphavantage_sample_data import SAMPLE_ALPHAVANTAGE_RESPONSE
from app.ingestion.base import BaseFetcher, RawArticle

logger = logging.getLogger(__name__)

ALPHAVANTAGE_ENDPOINT = "https://www.alphavantage.co/query"


class AlphaVantageFetcher(BaseFetcher):
    source_api_name = "AlphaVantage"

    def fetch(self, query: str, max_results: int = 20) -> list[RawArticle]:
        """`query` is treated as comma-separated ticker symbols — see module docstring."""
        if not config.ALPHAVANTAGE_KEY:
            logger.warning(
                "ALPHAVANTAGE_KEY not set — using bundled sample data instead of "
                "a live call. Add the key to .env to fetch real articles."
            )
            payload = SAMPLE_ALPHAVANTAGE_RESPONSE
        else:
            payload = self._call_api(query, max_results)
            if payload is None:
                logger.warning("Alpha Vantage call failed — falling back to sample data.")
                payload = SAMPLE_ALPHAVANTAGE_RESPONSE

        return self._parse(payload, max_results)

    def _call_api(self, tickers: str, max_results: int) -> Optional[dict]:
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": tickers,
            "apikey": config.ALPHAVANTAGE_KEY,
            "limit": min(max_results, 200),
        }
        try:
            resp = requests.get(ALPHAVANTAGE_ENDPOINT, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            # Alpha Vantage returns HTTP 200 even for errors/rate limits — the
            # actual problem shows up as one of these keys instead.
            if "Error Message" in data or "Note" in data or "Information" in data:
                logger.error("Alpha Vantage returned an error/notice payload: %s", data)
                return None
            if "feed" not in data:
                logger.error("Alpha Vantage response missing expected 'feed' key: %s", data)
                return None
            return data
        except requests.RequestException as exc:
            logger.error("Alpha Vantage request failed: %s", exc)
            return None

    def _parse(self, payload: dict, max_results: int) -> list[RawArticle]:
        out: list[RawArticle] = []
        for item in payload.get("feed", [])[:max_results]:
            headline = item.get("title")
            if not headline:
                continue  # skip anything without even a headline — nothing useful to store
            out.append(
                RawArticle(
                    headline=headline,
                    body=item.get("summary"),
                    source_name=item.get("source"),
                    source_url=item.get("url"),
                    source_api=self.source_api_name,
                    published_at=self._parse_datetime(item.get("time_published")),
                )
            )
        return out

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Alpha Vantage uses 'YYYYMMDDTHHMMSS' (e.g. '20260728T091500'), always UTC."""
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            logger.warning("Could not parse time_published value: %s", value)
            return None
