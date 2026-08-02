"""
NewsAPI.org fetcher.

Docs: https://newsapi.org/docs/endpoints/everything
Free tier: 100 requests/day, articles delayed ~24h (not an issue for a
30-minute polling cycle aimed at same-day news).
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from app import config
from app.ingestion.base import BaseFetcher, RawArticle
from app.ingestion.sample_data import SAMPLE_NEWSAPI_RESPONSE

logger = logging.getLogger(__name__)

NEWSAPI_ENDPOINT = "https://newsapi.org/v2/everything"


class NewsAPIFetcher(BaseFetcher):
    source_api_name = "NewsAPI"

    def fetch(self, query: str, max_results: int = 20) -> list[RawArticle]:
        if not config.NEWSAPI_KEY:
            logger.warning(
                "NEWSAPI_KEY not set — using bundled sample data instead of "
                "a live call. Add the key to .env to fetch real articles."
            )
            payload = SAMPLE_NEWSAPI_RESPONSE
        else:
            payload = self._call_api(query, max_results)
            if payload is None:
                logger.warning("NewsAPI call failed — falling back to sample data.")
                payload = SAMPLE_NEWSAPI_RESPONSE

        return self._parse(payload, max_results)

    def _call_api(self, query: str, max_results: int) -> Optional[dict]:
        params = {
            "q": query,
            "apiKey": config.NEWSAPI_KEY,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(max_results, 100),  # NewsAPI hard cap per page
        }
        try:
            resp = requests.get(NEWSAPI_ENDPOINT, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "ok":
                logger.error("NewsAPI returned an error payload: %s", data)
                return None
            return data
        except requests.RequestException as exc:
            logger.error("NewsAPI request failed: %s", exc)
            return None

    def _parse(self, payload: dict, max_results: int) -> list[RawArticle]:
        out: list[RawArticle] = []
        for item in payload.get("articles", [])[:max_results]:
            out.append(
                RawArticle(
                    headline=item.get("title") or "",
                    body=item.get("content") or item.get("description"),
                    source_name=(item.get("source") or {}).get("name"),
                    source_url=item.get("url"),
                    source_api=self.source_api_name,
                    published_at=self._parse_datetime(item.get("publishedAt")),
                )
            )
        return out

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            # NewsAPI uses ISO 8601 with a trailing "Z"
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Could not parse publishedAt value: %s", value)
            return None
