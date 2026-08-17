"""
Alert Centre data-access service .

"""

from datetime import date, datetime, time

from app.db import get_session
from app.models import Alert, Entity, Signal, UserFeedback

ALERT_TYPE_OPTIONS = ["Strong Bullish", "Bullish", "Bearish", "Strong Bearish"]
STATUS_OPTIONS = ["All", "Active", "Acknowledged"]


def get_active_alerts() -> list[dict]:
    """Stands in for: GET /api/v1/alerts?is_acknowledged=false — newest first."""
    with get_session() as session:
        rows = (
            session.query(Alert, Entity.name)
            .join(Entity, Entity.entity_id == Alert.entity_id)
            .filter(Alert.is_acknowledged.is_(False))
            .order_by(Alert.created_at.desc())
            .all()
        )
        return [_alert_to_dict(a, name) for a, name in rows]


def get_all_alerts(
    search: str = "",
    alert_types: list[str] | None = None,
    entity_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str = "All",
) -> list[dict]:
    """Stands in for: GET /api/v1/alerts (with REQ-5's filter panel applied)."""
    with get_session() as session:
        query = session.query(Alert, Entity.name).join(Entity, Entity.entity_id == Alert.entity_id)

        if search:
            query = query.filter(Entity.name.ilike(f"%{search}%"))
        if alert_types:
            query = query.filter(Alert.alert_type.in_(alert_types))
            
        if entity_id:
            # Filter by a specific entity when an entity ID is provided.
            query = query.filter(Alert.entity_id == entity_id)
        if date_from:
            # Include alerts from the beginning of the selected date.
            query = query.filter(Alert.created_at >= datetime.combine(date_from, time.min))
        if date_to:
            # Include alerts until the end of the selected date.
            query = query.filter(Alert.created_at <= datetime.combine(date_to, time.max))
        if status == "Active":
            query = query.filter(Alert.is_acknowledged.is_(False))
        elif status == "Acknowledged":
            query = query.filter(Alert.is_acknowledged.is_(True))

        rows = query.order_by(Alert.created_at.desc()).all()
        return [_alert_to_dict(a, name) for a, name in rows]


def _alert_to_dict(alert: Alert, entity_name: str) -> dict:
    return {
        "alert_id": alert.alert_id,
        "signal_id": alert.signal_id,
        "entity_id": alert.entity_id,
        "entity_name": entity_name,
        "alert_type": alert.alert_type,
        "trigger_headline": alert.trigger_headline,
        "aggregate_score": alert.triggered_value,
        "threshold": alert.threshold_value,
        "created_at": alert.created_at,
        # Convert the database boolean into the status text displayed by the Alert Centre.
        "status": "Acknowledged" if alert.is_acknowledged else "Active",
    }


def acknowledge_alert(alert_id: int) -> bool:
    """Stands in for: PUT /api/v1/alerts/{alert_id}/acknowledge
    Marks one alert as acknowledged"""
    with get_session() as session:
         # Find the alert using its primary key.
        alert = session.get(Alert, alert_id)
        # Return False if the alert does not exist.
        if alert is None:
            return False
        alert.is_acknowledged = True
         # Store the time at which the alert was acknowledged.
        from datetime import datetime as _dt, timezone as _tz
        alert.acknowledged_at = _dt.now(_tz.utc)
    return True


def acknowledge_all_active() -> int:
    """Stands in for: PUT /api/v1/alerts/acknowledge-all. Returns count acknowledged
     Marks every currently active alert as acknowledged and returns the number of alerts updated.."""
    from datetime import datetime as _dt, timezone as _tz
    # Get the current UTC time once so all alerts receive the same acknowledgement timestamp.
    now = _dt.now(_tz.utc)
    with get_session() as session:
        # Find all alerts that have not yet been acknowledged.
        active = session.query(Alert).filter(Alert.is_acknowledged.is_(False)).all()
         # Update every active alert.
        for alert in active:
            alert.is_acknowledged = True
            alert.acknowledged_at = now
        return len(active)


def get_signal_for_alert(signal_id: int) -> dict | None:
    """This provides the data needed for the Alert Centre's "View Signal" action.."""
    with get_session() as session:
        signal = session.get(Signal, signal_id)
        # Return None if the signal does not exist.
        if signal is None:
            return None
        return {
            "signal_strength": signal.signal_strength,
            "aggregate_score": signal.aggregate_sentiment_score,
            "article_count": signal.article_count,
            "positive_count": signal.positive_count,
            "negative_count": signal.negative_count,
            "neutral_count": signal.neutral_count,
            "window_start": signal.window_start,
            "window_end": signal.window_end,
        }


def save_relevance_rating(alert_id: int, relevance_score: int) -> tuple[bool, str]:
    """
    Stands in for: POST /api/v1/feedback
    Saves or updates the user's star rating for an alert.
    If a rating already exists, it is updated instead of creating
    another feedback row
    """
    try:
             # Check whether this alert already has a feedback record.
        with get_session() as session:
            existing = session.query(UserFeedback).filter_by(alert_id=alert_id).first()
            # Ratings of 3 stars or more are treated as relevant.
            is_relevant = relevance_score >= 3
            if existing:
                 # Update the existing feedback instead of creating a second feedback record for the same alert.
                existing.relevance_score = relevance_score
                existing.is_relevant = is_relevant
            else:
                 # Create a new feedback record when no rating exists.
                session.add(UserFeedback(
                    alert_id=alert_id, relevance_score=relevance_score, is_relevant=is_relevant,
                ))
        return True, "Thanks for your feedback."
    except Exception:
        # Return a failure message if saving the rating fails.
        return False, "Failed to save your rating — please try again."


def get_existing_rating(alert_id: int) -> int | None:
    """    Retrieves the previously saved rating for an alert.This allows the star control to display the user's existing rating instead of starting empty each time."""
    with get_session() as session:
        fb = session.query(UserFeedback).filter_by(alert_id=alert_id).first()
        # Return the saved rating, or None if no rating exists.
        return fb.relevance_score if fb else None
