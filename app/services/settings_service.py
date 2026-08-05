"""
Settings / Pipeline Configuration data-access service (REQ-9).

Same design decision as the other services: internal equivalents of the
BRD's REST endpoints, called directly by Streamlit.
"""

import json

from app import config
from app.db import get_session
from app.ingestion.preprocess import SOURCE_CREDIBILITY
from app.models import Entity, ModelVersion, PipelineRun

SECTOR_OPTIONS = ["Technology", "Finance", "Energy", "Healthcare", "Consumer",
                  "Industrials", "Materials", "Real Estate", "Utilities", "Other"]
ENTITY_TYPE_OPTIONS = ["Company", "Index", "Sector", "Commodity"]


# --- Pipeline status ---

def get_pipeline_status_by_stage() -> dict[str, dict]:
    """Stands in for: GET /api/v1/pipeline/status — latest run per stage type."""
    stage_types = ["fetch", "preprocess", "sentiment", "ner", "aggregate", "alert"]
    result = {}
    with get_session() as session:
        for stage in stage_types:
            run = (
                session.query(PipelineRun)
                .filter(PipelineRun.run_type == stage)
                .order_by(PipelineRun.run_id.desc())
                .first()
            )
            result[stage] = {
                "status": run.status if run else "never run",
                "completed_at": run.completed_at if run else None,
                "articles_processed": run.articles_processed if run else 0,
            } if run else {"status": "never run", "completed_at": None, "articles_processed": 0}
    return result


# --- Settings persistence ---

def get_current_settings() -> dict:
    return {
        "confidence_threshold": config.SENTIMENT_CONFIDENCE_THRESHOLD,
        "aggregation_window_hours": config.SIGNAL_WINDOW_HOURS,
        "default_alert_threshold": config.DEFAULT_ALERT_THRESHOLD,
    }


def save_settings(confidence_threshold: float, aggregation_window_hours: int,
                  default_alert_threshold: float) -> None:
    """
    Stands in for: PUT /api/v1/settings

    Writes to app_settings.json — see config.py's module docstring for why
    this exists instead of a database table, and the important caveat that
    changes apply on next process start, not instantly.
    """
    existing = {}
    try:
        with open(config.SETTINGS_FILE) as f:
            existing = json.load(f)
    except FileNotFoundError:
        pass

    existing.update({
        "confidence_threshold": confidence_threshold,
        "aggregation_window_hours": aggregation_window_hours,
        "default_alert_threshold": default_alert_threshold,
    })
    with open(config.SETTINGS_FILE, "w") as f:
        json.dump(existing, f, indent=2)


# --- Entity management ---

def get_all_entities() -> list[dict]:
    """Stands in for: GET /api/v1/entities — includes inactive entities, unlike other pages' pickers."""
    with get_session() as session:
        entities = session.query(Entity).order_by(Entity.name).all()
        return [
            {
                "entity_id": e.entity_id, "name": e.name, "ticker_symbol": e.ticker_symbol,
                "entity_type": e.entity_type, "sector": e.sector, "exchange": e.exchange,
                "is_active": e.is_active,
            }
            for e in entities
        ]


def add_entity(name: str, ticker_symbol: str | None, entity_type: str,
              sector: str, exchange: str | None, is_active: bool) -> tuple[bool, str]:
    """
    Stands in for: POST /api/v1/entities

    Returns (success, message) using the BRD's exact three status-alert
    strings for the Add Entity Form.
    """
    try:
        with get_session() as session:
            existing = session.query(Entity).filter_by(name=name).first()
            if existing is not None:
                return False, "Entity name already exists."

            session.add(Entity(
                name=name, ticker_symbol=ticker_symbol or None, entity_type=entity_type,
                sector=sector, exchange=exchange or None, is_active=is_active,
            ))
        return True, "Entity added successfully."
    except Exception:
        return False, "Failed to save — please try again."


def update_entity(entity_id: int, name: str, ticker_symbol: str | None, entity_type: str,
                  sector: str, exchange: str | None, is_active: bool) -> tuple[bool, str]:
    """Stands in for: PUT /api/v1/entities/{entity_id}"""
    try:
        with get_session() as session:
            entity = session.get(Entity, entity_id)
            if entity is None:
                return False, "Entity not found."

            duplicate = session.query(Entity).filter(
                Entity.name == name, Entity.entity_id != entity_id
            ).first()
            if duplicate is not None:
                return False, "Entity name already exists."

            entity.name = name
            entity.ticker_symbol = ticker_symbol or None
            entity.entity_type = entity_type
            entity.sector = sector
            entity.exchange = exchange or None
            entity.is_active = is_active
        return True, "Entity updated successfully."
    except Exception:
        return False, "Failed to save — please try again."


def deactivate_entity(entity_id: int) -> bool:
    """Stands in for: PUT /api/v1/entities/{entity_id}/deactivate"""
    with get_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            return False
        entity.is_active = False
    return True


# --- Source management ---

def get_source_credibility_table() -> list[dict]:
    """
    Stands in for: GET /api/v1/sources

    Merges the hardcoded baseline table (app/ingestion/preprocess.py) with
    any saved overrides — overrides win. There's no "sources" table in the
    schema; credibility is a per-source constant applied at ingestion time.
    """
    merged = dict(SOURCE_CREDIBILITY)
    merged.update(config.SOURCE_CREDIBILITY_OVERRIDES)
    return [{"source_name": name, "credibility_score": score} for name, score in sorted(merged.items())]


def update_source_credibility(source_name: str, new_score: float) -> None:
    """
    Stands in for: PUT /api/v1/sources/{source_name}

    IMPORTANT: this only affects articles fetched AFTER this change.
    source_credibility_score is stored per-article at ingestion time, not
    looked up dynamically — already-ingested articles keep whatever score
    they were given when fetched.
    """
    existing = {}
    try:
        with open(config.SETTINGS_FILE) as f:
            existing = json.load(f)
    except FileNotFoundError:
        pass

    overrides = existing.get("source_credibility_overrides", {})
    overrides[source_name] = new_score
    existing["source_credibility_overrides"] = overrides

    with open(config.SETTINGS_FILE, "w") as f:
        json.dump(existing, f, indent=2)


# --- Model version log ---

def get_model_version_log() -> list[dict]:
    """Stands in for: GET /api/v1/model-versions"""
    with get_session() as session:
        versions = session.query(ModelVersion).order_by(ModelVersion.version_id).all()
        return [
            {
                "version_label": v.version_label, "model_name": v.model_name,
                "confidence_threshold": v.confidence_threshold, "macro_f1_score": v.macro_f1_score,
                "entity_precision": v.entity_precision, "entity_recall": v.entity_recall,
                "deployed_at": v.deployed_at,
            }
            for v in versions
        ]
