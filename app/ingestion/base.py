"""
Base interface for news source fetchers.

Every source (NewsAPI, Alpha Vantage, Reddit) implements this same contract so
the rest of the pipeline (saving, preprocessing) doesn't care which API the
articles came from. Add a new source by subclassing BaseFetcher and
implementing fetch().
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RawArticle:
    """
    A single article in a normalized shape, regardless of source.

    Every fetcher's fetch() method returns a list of these. This is the only
    shape the rest of the ingestion pipeline needs to know about.
    """

    headline: str
    body: Optional[str]
    source_name: Optional[str]
    source_url: Optional[str]
    source_api: str          # "NewsAPI" | "AlphaVantage" | "Reddit"
    published_at: Optional[datetime]


class BaseFetcher(ABC):
    """Common contract for all news source adapters."""

    #: Value stored in articles.source_api — must match app.models.SourceAPI
    source_api_name: str = "Unknown"

    @abstractmethod
    def fetch(self, query: str, max_results: int = 20) -> list[RawArticle]:
        """
        Fetch recent articles matching `query`.

        Implementations should never raise on a missing/invalid API key —
        they should fall back to sample data and log a warning, so the
        pipeline stays runnable while keys are being set up.
        """
        raise NotImplementedError
