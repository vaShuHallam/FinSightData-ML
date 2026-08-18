"""
Seed the entities table with a starter set to track.

This needs to run once before ingestion — every downstream table
(signals, alerts, watchlist, article_entities) references entities, so
there's nothing for them to link to until it does.

It's safe to run again later, too. Entities are matched by their unique
name, so anything that's already there gets skipped instead of
duplicated — re-running won't leave you with two rows for the same
company.

Want to track something new? Add it to STARTER_ENTITIES below.
entity_type has to be one of: Company, Index, Sector, Commodity —
nothing else is recognized. ticker_symbol and exchange can be left as
None for anything that isn't a company (indices, sectors, commodities).
Usage:
    python seed_entities.py
"""

from Dashboard.db import get_session
from Dashboard.models import Entity, EntityType

# (name, ticker, entity_type, sector, exchange)
STARTER_ENTITIES = [
    # --- Companies ---
    ("Apple Inc.",            "AAPL", EntityType.COMPANY,   "Technology",        "NASDAQ"),
    ("Microsoft Corporation", "MSFT", EntityType.COMPANY,   "Technology",        "NASDAQ"),
    ("NVIDIA Corporation",    "NVDA", EntityType.COMPANY,   "Technology",        "NASDAQ"),
    ("Amazon.com Inc.",       "AMZN", EntityType.COMPANY,   "Consumer Cyclical", "NASDAQ"),
    ("Tesla Inc.",            "TSLA", EntityType.COMPANY,   "Automotive",        "NASDAQ"),
    ("JPMorgan Chase & Co.",  "JPM",  EntityType.COMPANY,   "Finance",           "NYSE"),
    ("Barclays PLC",          "BARC", EntityType.COMPANY,   "Finance",           "LSE"),
    # --- Indices ---
    ("S&P 500",               None,   EntityType.INDEX,     None,                None),
    ("NASDAQ Composite",      None,   EntityType.INDEX,     None,                None),
    ("FTSE 100",              None,   EntityType.INDEX,     None,                None),
    # --- Sectors ---
    ("Technology",            None,   EntityType.SECTOR,    None,                None),
    ("Energy",                None,   EntityType.SECTOR,    None,                None),
    # --- Commodities ---
    ("Gold",                  None,   EntityType.COMMODITY, None,                None),
    ("Crude Oil",             None,   EntityType.COMMODITY, None,                None),
]


def seed() -> None:
    with get_session() as session:
        existing = {name for (name,) in session.query(Entity.name).all()}

        to_add = []
        for name, ticker, etype, sector, exchange in STARTER_ENTITIES:
            if name in existing:
                continue
            to_add.append(
                Entity(
                    name=name,
                    ticker_symbol=ticker,
                    entity_type=etype.value,
                    sector=sector,
                    exchange=exchange,
                )
            )

        session.add_all(to_add)
        print(f"Added {len(to_add)} new entities "
              f"({len(existing)} already present, skipped).")

    # Report the full current list
    with get_session() as session:
        rows = (
            session.query(Entity)
            .order_by(Entity.entity_type, Entity.name)
            .all()
        )
        print(f"\nEntities now in the database ({len(rows)} total):")
        for e in rows:
            tag = f" [{e.ticker_symbol}]" if e.ticker_symbol else ""
            print(f"  - {e.entity_type:<10} {e.name}{tag}")


if __name__ == "__main__":
    seed()
