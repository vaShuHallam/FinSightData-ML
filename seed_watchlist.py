"""
Seed the watchlist table with a starter set of entries.

Needed before running alerts (app/alerts/pipeline.py) — alerts only fire for
entities that have an active watchlist entry. Safe to run repeatedly:
entries that already exist (matched by session_id + entity name) are
skipped, not duplicated.

Edit STARTER_WATCHLIST below to track whatever you like and at whatever
sensitivity. Entity names must already exist in the entities table (run
seed_entities.py first if you haven't). alert_threshold is how large a
move (in aggregate_sentiment_score, -1.0 to 1.0) is needed before an alert
fires — lower = more sensitive/more alerts, higher = only major moves.

Usage:
    python seed_watchlist.py
"""

from Dashboard.db import get_session
from Dashboard.models import Entity, Watchlist

# A single demo session — in the real dashboard this would be the logged-in
# user's session_id, generated per browser session per the BRD.
SESSION_ID = "demo-user"

# (entity_name, alert_threshold, window_size_hours)
STARTER_WATCHLIST = [
    ("Apple Inc.",            0.50, 6),
    ("Tesla Inc.",            0.50, 6),
    ("Microsoft Corporation", 0.50, 6),
    ("NVIDIA Corporation",    0.50, 6),
    ("Amazon.com Inc.",       0.50, 6),
]


def seed() -> None:
    with get_session() as session:
        name_to_id = {
            name: eid for name, eid in session.query(Entity.name, Entity.entity_id).all()
        }
        existing = {
            entity_id
            for (entity_id,) in session.query(Watchlist.entity_id)
            .filter(Watchlist.session_id == SESSION_ID)
            .all()
        }

        added = skipped_missing = skipped_existing = 0

        for name, threshold, window_hours in STARTER_WATCHLIST:
            entity_id = name_to_id.get(name)
            if entity_id is None:
                print(f"  Skipping '{name}' — not found in entities table "
                      f"(run seed_entities.py first, or check the name).")
                skipped_missing += 1
                continue

            if entity_id in existing:
                skipped_existing += 1
                continue

            session.add(
                Watchlist(
                    session_id=SESSION_ID,
                    entity_id=entity_id,
                    alert_threshold=threshold,
                    window_size_hours=window_hours,
                )
            )
            added += 1

        print(f"\nAdded {added} new watchlist entries "
              f"({skipped_existing} already present, {skipped_missing} entity name not found).")

    # Report the full current watchlist for this session
    with get_session() as session:
        rows = (
            session.query(Entity.name, Watchlist.alert_threshold, Watchlist.window_size_hours)
            .join(Watchlist, Watchlist.entity_id == Entity.entity_id)
            .filter(Watchlist.session_id == SESSION_ID)
            .order_by(Entity.name)
            .all()
        )
        print(f"\nWatchlist for session '{SESSION_ID}' ({len(rows)} entries):")
        for name, threshold, window_hours in rows:
            print(f"  - {name:<25} threshold={threshold:.2f}  window={window_hours}h")


if __name__ == "__main__":
    seed()