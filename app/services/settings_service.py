"""
Settings / Pipeline Configuration data-access service .

Handles database and configuration operations for:
- Pipeline status, Application settings, Entity management, Source credibility ,Model version history
"""

import json

from app import config
from app.db import get_session
from app.ingestion.preprocess import SOURCE_CREDIBILITY
from app.models import Entity, ModelVersion, PipelineRun

SECTOR_OPTIONS = ["Technology", "Finance", "Energy", "Healthcare", "Consumer",
                  "Industrials", "Materials", "Real Estate", "Utilities", "Other" ]
ENTITY_TYPE_OPTIONS = ["Company", "Index", "Sector", "Commodity"  ]


#! --- Pipeline status ---

def get_pipeline_status_by_stage() -> dict[str, dict]:
        """Get the most recent pipeline run for each pipeline stage."""
        stage_types = ["fetch", "preprocess", "sentiment", "ner", "aggregate", "alert"]
        result = {}
        with get_session() as session:
            # Check each pipeline stage separately
            for stage in stage_types:
                # Find the newest PipelineRun for this particular stage
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


#! --- Settings persistence ---

def get_current_settings() -> dict:
    # Return the current application settings from config.py
        return {
            "confidence_threshold": config.SENTIMENT_CONFIDENCE_THRESHOLD,
            "aggregation_window_hours": config.SIGNAL_WINDOW_HOURS,
            "default_alert_threshold": config.DEFAULT_ALERT_THRESHOLD,
        }


def save_settings(confidence_threshold: float, aggregation_window_hours: int,
                  default_alert_threshold: float) -> None:
    """
              Save application settings to app_settings.json..
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
        # Save the updated settings back to the JSON file
    with open(config.SETTINGS_FILE, "w") as f:
        json.dump(existing, f, indent=2)


#! --- Entity management ---

def get_all_entities() -> list[dict]:
    """ includes inactive entities, unlike other pages' pickers."""
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
    Add a new Entity to the database.
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
    """  Update an existing entity.
    The entity ID identifies which row should be changed."""
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
    """ Deactivate an entity instead of deleting it from the database"""
    with get_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            return False
        entity.is_active = False
    return True


#! --- Source management ---

def get_source_credibility_table() -> list[dict]:
        """
        Return the credibility score for each news source.
        
        """
        merged = dict(SOURCE_CREDIBILITY)
        # Apply any user-defined overrides.
        merged.update(config.SOURCE_CREDIBILITY_OVERRIDES)
        return [{"source_name": name, "credibility_score": score} for name, score in sorted(merged.items())]


def update_source_credibility(source_name: str, new_score: float) -> None:
        """
            Save a new credibility score for a news source.
        """
        existing = {}
        try:
            with open(config.SETTINGS_FILE) as f:
                existing = json.load(f)
        except FileNotFoundError:
            pass
        # Get existing source overrides.
        overrides = existing.get("source_credibility_overrides", {})
        overrides[source_name] = new_score
        existing["source_credibility_overrides"] = overrides
        # Save everything back to the JSON file
        with open(config.SETTINGS_FILE, "w") as f:
            json.dump(existing, f, indent=2)


# --- Model version log ---

def get_model_version_log() -> list[dict]:
        """ Return the history of model versions stored in the database."""
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
