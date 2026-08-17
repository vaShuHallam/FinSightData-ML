"""Validation helpers for normalized ingestion records.

Validation is intentionally pure and independent of the database so fetchers and
the ingestion pipeline can share the same rules and tests can exercise edge cases
without requiring an API call.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from app.ingestion.base import RawArticle


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating one normalized RawArticle."""

    valid: bool
    errors: tuple[str, ...] = ()


def _valid_http_url(value: Optional[str]) -> bool:
    if not value:
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_raw_article(article: RawArticle) -> ValidationResult:
    """Validate the minimum fields required for safe downstream processing.

    The body is optional because some news providers legitimately return a
    headline/metadata record without article text. A non-empty headline and
    source are mandatory, while source_url must be an absolute HTTP(S) URL.
    """
    errors: list[str] = []

    if not article.headline or not article.headline.strip():
        errors.append("missing_headline")

    if not article.source_name or not article.source_name.strip():
        errors.append("missing_source")

    if not _valid_http_url(article.source_url):
        errors.append("invalid_source_url")

    if not article.source_api or not article.source_api.strip():
        errors.append("missing_source_api")

    if article.published_at is not None and not isinstance(article.published_at, datetime):
        errors.append("invalid_published_at")

    if article.body is not None and not article.body.strip():
        errors.append("empty_body")

    return ValidationResult(valid=not errors, errors=tuple(errors))


def filter_valid_articles(
    raw_articles: list[RawArticle],
) -> tuple[list[RawArticle], int, dict[str, int]]:
    """Return valid records plus invalid count and aggregated error reasons."""
    valid_articles: list[RawArticle] = []
    invalid_count = 0
    error_counts: dict[str, int] = {}

    for article in raw_articles:
        result = validate_raw_article(article)
        if result.valid:
            valid_articles.append(article)
            continue

        invalid_count += 1
        for error in result.errors:
            error_counts[error] = error_counts.get(error, 0) + 1

    return valid_articles, invalid_count, error_counts
