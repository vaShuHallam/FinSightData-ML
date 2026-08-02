"""
FinSight AI — database models (SQLAlchemy 2.0 typed declarative style).

Implements REQ-1 of the BRD: the ten core tables and their relationships.

Design notes
------------
* Primary/foreign keys are declared as BigInteger in Postgres but fall back to
  INTEGER on SQLite via ``with_variant``. SQLite only auto-increments an
  ``INTEGER PRIMARY KEY`` (its rowid alias), so this keeps auto-increment IDs
  working identically on both the dev (SQLite) and prod (Postgres) databases.
* The BRD lists several score/weight fields as "Decimal (0.0–1.0)". We store
  them as ``Float`` (double precision). FinBERT emits floats and we do weighted
  arithmetic on them downstream, so Float avoids Decimal/float mixing bugs while
  still satisfying the business meaning. Switch to ``Numeric(p, s)`` later if you
  want fixed-precision storage.
* Categorical fields (sentiment_label, entity_type, signal_strength, ...) are
  stored as plain strings for portability (no Postgres ENUM types to migrate).
  The allowed values live in the ``str`` Enums below — use them in application
  code for validation and to avoid typos.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


# --------------------------------------------------------------------------- #
# Base + reusable helpers
# --------------------------------------------------------------------------- #
class Base(DeclarativeBase):
    """Declarative base for all FinSight models."""


def bigint():
    """BIGINT on Postgres, INTEGER (auto-incrementing rowid) on SQLite."""
    return BigInteger().with_variant(Integer, "sqlite")


class CreatedAtMixin:
    """Adds a server-set created_at timestamp."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    """Adds created_at (inherited) + an auto-updating updated_at timestamp."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# --------------------------------------------------------------------------- #
# Controlled vocabularies (stored as strings; used for validation in app code)
# --------------------------------------------------------------------------- #
class SourceAPI(str, enum.Enum):
    NEWSAPI = "NewsAPI"
    ALPHAVANTAGE = "AlphaVantage"
    REDDIT = "Reddit"


class EntityType(str, enum.Enum):
    COMPANY = "Company"
    INDEX = "Index"
    SECTOR = "Sector"
    COMMODITY = "Commodity"


class SentimentLabel(str, enum.Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class SignalStrength(str, enum.Enum):
    STRONG_BULLISH = "Strong Bullish"
    BULLISH = "Bullish"
    NEUTRAL = "Neutral"
    BEARISH = "Bearish"
    STRONG_BEARISH = "Strong Bearish"


class AlertType(str, enum.Enum):
    STRONG_BULLISH = "Strong Bullish"
    BULLISH = "Bullish"
    BEARISH = "Bearish"
    STRONG_BEARISH = "Strong Bearish"


class PipelineRunType(str, enum.Enum):
    FETCH = "fetch"
    PREPROCESS = "preprocess"
    SENTIMENT = "sentiment"
    NER = "ner"
    AGGREGATE = "aggregate"
    ALERT = "alert"


class PipelineStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# --------------------------------------------------------------------------- #
# 1. articles
# --------------------------------------------------------------------------- #
class Article(TimestampMixin, Base):
    __tablename__ = "articles"

    article_id: Mapped[int] = mapped_column(bigint(), primary_key=True, autoincrement=True)
    headline: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    source_name: Mapped[Optional[str]] = mapped_column(String(255))
    source_url: Mapped[Optional[str]] = mapped_column(String(1024))
    source_api: Mapped[Optional[str]] = mapped_column(String(50))  # SourceAPI
    # Credibility + recency are assigned during preprocessing (Stage 2).
    source_credibility_score: Mapped[Optional[float]] = mapped_column(Float)  # 0.0–1.0
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    recency_weight: Mapped[Optional[float]] = mapped_column(Float)  # 0.0–1.0
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_hash: Mapped[Optional[str]] = mapped_column(String(32))  # MD5(headline + source)

    # Relationships
    sentiment_results: Mapped[list["SentimentResult"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    article_entities: Mapped[list["ArticleEntity"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_articles_content_hash", "content_hash"),
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_is_processed", "is_processed"),
    )


# --------------------------------------------------------------------------- #
# 2. entities
# --------------------------------------------------------------------------- #
class Entity(TimestampMixin, Base):
    __tablename__ = "entities"

    entity_id: Mapped[int] = mapped_column(bigint(), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ticker_symbol: Mapped[Optional[str]] = mapped_column(String(32))  # null for indices/sectors
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # EntityType
    sector: Mapped[Optional[str]] = mapped_column(String(100))
    exchange: Mapped[Optional[str]] = mapped_column(String(50))  # null for indices/sectors
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    article_entities: Mapped[list["ArticleEntity"]] = relationship(back_populates="entity")
    sentiment_results: Mapped[list["SentimentResult"]] = relationship(back_populates="entity")
    signals: Mapped[list["Signal"]] = relationship(back_populates="entity")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="entity")
    watchlist_entries: Mapped[list["Watchlist"]] = relationship(back_populates="entity")

    __table_args__ = (
        UniqueConstraint("name", name="uq_entities_name"),  # supports "name already exists"
        Index("ix_entities_ticker_symbol", "ticker_symbol"),
    )


# --------------------------------------------------------------------------- #
# 3. article_entities (junction: which entities appear in which articles)
# --------------------------------------------------------------------------- #
class ArticleEntity(CreatedAtMixin, Base):
    __tablename__ = "article_entities"

    id: Mapped[int] = mapped_column(bigint(), primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        bigint(), ForeignKey("articles.article_id", ondelete="CASCADE"), nullable=False
    )
    entity_id: Mapped[int] = mapped_column(
        bigint(), ForeignKey("entities.entity_id"), nullable=False
    )
    mention_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    article: Mapped["Article"] = relationship(back_populates="article_entities")
    entity: Mapped["Entity"] = relationship(back_populates="article_entities")

    __table_args__ = (
        UniqueConstraint("article_id", "entity_id", name="uq_article_entity"),
    )


# --------------------------------------------------------------------------- #
# 4. sentiment_results (FinBERT output)
# --------------------------------------------------------------------------- #
class SentimentResult(CreatedAtMixin, Base):
    __tablename__ = "sentiment_results"

    result_id: Mapped[int] = mapped_column(bigint(), primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        bigint(), ForeignKey("articles.article_id", ondelete="CASCADE"), nullable=False
    )
    # Nullable: null when the result is sentence-level rather than entity-specific.
    entity_id: Mapped[Optional[int]] = mapped_column(
        bigint(), ForeignKey("entities.entity_id")
    )
    sentiment_label: Mapped[str] = mapped_column(String(20), nullable=False)  # SentimentLabel
    positive_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0–1.0
    negative_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0–1.0
    neutral_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0–1.0
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)  # max class prob
    # Soft reference to model_versions.version_label (kept as a string per the BRD).
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)
    is_abstained: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    article: Mapped["Article"] = relationship(back_populates="sentiment_results")
    entity: Mapped[Optional["Entity"]] = relationship(back_populates="sentiment_results")

    __table_args__ = (
        Index("ix_sentiment_article_id", "article_id"),
        Index("ix_sentiment_entity_id", "entity_id"),
        Index("ix_sentiment_model_version", "model_version"),
    )


# --------------------------------------------------------------------------- #
# 5. signals (aggregated entity sentiment over a time window)
# --------------------------------------------------------------------------- #
class Signal(CreatedAtMixin, Base):
    __tablename__ = "signals"

    signal_id: Mapped[int] = mapped_column(bigint(), primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        bigint(), ForeignKey("entities.entity_id"), nullable=False
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_size_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregate_sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)  # -1.0–1.0
    article_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    positive_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    negative_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    neutral_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    signal_strength: Mapped[str] = mapped_column(String(20), nullable=False)  # SignalStrength

    # Relationships
    entity: Mapped["Entity"] = relationship(back_populates="signals")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="signal")

    __table_args__ = (
        Index("ix_signals_entity_window", "entity_id", "window_end"),
    )


# --------------------------------------------------------------------------- #
# 6. alerts (a signal that crossed a threshold)
# --------------------------------------------------------------------------- #
class Alert(CreatedAtMixin, Base):
    __tablename__ = "alerts"

    alert_id: Mapped[int] = mapped_column(bigint(), primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        bigint(), ForeignKey("entities.entity_id"), nullable=False
    )
    signal_id: Mapped[int] = mapped_column(
        bigint(), ForeignKey("signals.signal_id"), nullable=False
    )
    alert_type: Mapped[str] = mapped_column(String(20), nullable=False)  # AlertType
    trigger_headline: Mapped[Optional[str]] = mapped_column(String(512))
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    triggered_value: Mapped[float] = mapped_column(Float, nullable=False)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    entity: Mapped["Entity"] = relationship(back_populates="alerts")
    signal: Mapped["Signal"] = relationship(back_populates="alerts")
    feedback: Mapped[Optional["UserFeedback"]] = relationship(
        back_populates="alert", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_alerts_entity_id", "entity_id"),
        Index("ix_alerts_signal_id", "signal_id"),
        Index("ix_alerts_is_acknowledged", "is_acknowledged"),
    )


# --------------------------------------------------------------------------- #
# 7. watchlist (per-session entity monitoring config)
# --------------------------------------------------------------------------- #
class Watchlist(TimestampMixin, Base):
    __tablename__ = "watchlist"

    watchlist_id: Mapped[int] = mapped_column(bigint(), primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[int] = mapped_column(
        bigint(), ForeignKey("entities.entity_id"), nullable=False
    )
    alert_threshold: Mapped[float] = mapped_column(Float, default=0.60, nullable=False)
    window_size_hours: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    entity: Mapped["Entity"] = relationship(back_populates="watchlist_entries")

    __table_args__ = (
        # One entry per (session, entity) — supports "Entity already on watchlist".
        UniqueConstraint("session_id", "entity_id", name="uq_watchlist_session_entity"),
        Index("ix_watchlist_session_id", "session_id"),
    )


# --------------------------------------------------------------------------- #
# 8. user_feedback (the relevance-learning signal — one per alert)
# --------------------------------------------------------------------------- #
class UserFeedback(CreatedAtMixin, Base):
    __tablename__ = "user_feedback"

    feedback_id: Mapped[int] = mapped_column(bigint(), primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(
        bigint(), ForeignKey("alerts.alert_id", ondelete="CASCADE"), nullable=False
    )
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–5
    is_relevant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    feedback_note: Mapped[Optional[str]] = mapped_column(String(1024))

    # Relationships
    alert: Mapped["Alert"] = relationship(back_populates="feedback")

    __table_args__ = (
        # One feedback row per alert (one-to-one).
        UniqueConstraint("alert_id", name="uq_feedback_alert"),
    )


# --------------------------------------------------------------------------- #
# 9. pipeline_runs (audit log of each pipeline stage execution)
# --------------------------------------------------------------------------- #
class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    run_id: Mapped[int] = mapped_column(bigint(), primary_key=True, autoincrement=True)
    run_type: Mapped[str] = mapped_column(String(20), nullable=False)  # PipelineRunType
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # PipelineStatus
    articles_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_detail: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_pipeline_runs_type_status", "run_type", "status"),
    )


# --------------------------------------------------------------------------- #
# 10. model_versions (v1 / v2 config + post-evaluation metrics)
# --------------------------------------------------------------------------- #
class ModelVersion(CreatedAtMixin, Base):
    __tablename__ = "model_versions"

    version_id: Mapped[int] = mapped_column(bigint(), primary_key=True, autoincrement=True)
    version_label: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. v1, v2
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. ProsusAI/finbert
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    parameters: Mapped[Optional[str]] = mapped_column(Text)  # JSON string of config
    # Populated after evaluation (Stage 4) — null until then.
    macro_f1_score: Mapped[Optional[float]] = mapped_column(Float)
    entity_precision: Mapped[Optional[float]] = mapped_column(Float)
    entity_recall: Mapped[Optional[float]] = mapped_column(Float)
    deployed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("version_label", name="uq_model_versions_label"),
    )
