"""
Watchlist Management data-access service (REQ-3).

Same design decision as the other services: internal equivalents of the
BRD's REST endpoints, called directly by Streamlit.
"""

from app.db import get_session
from app.models import Entity, Watchlist

WINDOW_SIZE_OPTIONS = [6, 12, 24]
DEFAULT_ALERT_THRESHOLD = 0.60


def get_watchlist(session_id: str) -> list[dict]:
    """Stands in for: GET /api/v1/watchlist?session_id="""
    with get_session() as session:
        rows = (
            session.query(Watchlist, Entity.name)
            .join(Entity, Entity.entity_id == Watchlist.entity_id)
            .filter(Watchlist.session_id == session_id, Watchlist.is_active.is_(True))
            .order_by(Entity.name)
            .all()
        )
        return [
            {
                "watchlist_id": w.watchlist_id,
                "entity_id": w.entity_id,
                "entity_name": name,
                "alert_threshold": w.alert_threshold,
                "window_size_hours": w.window_size_hours,
            }
            for w, name in rows
        ]


def add_watchlist_entry(
    entity_id: int, session_id: str, alert_threshold: float, window_size_hours: int
) -> tuple[bool, str]:
    """
    Stands in for: POST /api/v1/watchlist

    Returns (success, message) using the BRD's exact three status-alert
    strings: success, already-exists, or a generic save failure.
    """
    try:
        with get_session() as session:
            existing = (
                session.query(Watchlist)
                .filter(Watchlist.entity_id == entity_id, Watchlist.session_id == session_id)
                .first()
            )
            if existing is not None:
                return False, "Entity already on watchlist."

            session.add(
                Watchlist(
                    session_id=session_id, entity_id=entity_id,
                    alert_threshold=alert_threshold, window_size_hours=window_size_hours,
                )
            )
        return True, "Entity added to your watchlist."
    except Exception:
        return False, "Failed to save — please try again."


def update_alert_threshold(watchlist_id: int, new_threshold: float) -> bool:
    """Stands in for: PUT /api/v1/watchlist/{watchlist_id} (threshold-only update)."""
    try:
        with get_session() as session:
            entry = session.get(Watchlist, watchlist_id)
            if entry is None:
                return False
            entry.alert_threshold = new_threshold
        return True
    except Exception:
        return False


def remove_watchlist_entry(watchlist_id: int) -> bool:
    """Stands in for: DELETE /api/v1/watchlist/{watchlist_id}"""
    try:
        with get_session() as session:
            entry = session.get(Watchlist, watchlist_id)
            if entry is None:
                return False
            session.delete(entry)
        return True
    except Exception:
        return False
