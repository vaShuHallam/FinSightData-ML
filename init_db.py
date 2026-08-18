"""
Create the FinSight AI database schema.

Usage:
    python init_db.py          # create all tables
    python init_db.py --reset  # drop everything, then recreate (dev only)
"""

import sys

from sqlalchemy import inspect

from Dashboard.db import drop_db, engine, init_db

if __name__ == "__main__":
    if "--reset" in sys.argv:
        print("Dropping all tables...")
        drop_db()

    print("Creating tables...")
    init_db()

    tables = sorted(inspect(engine).get_table_names())
    print(f"\nDone. {len(tables)} tables present:")
    for name in tables:
        print(f"  - {name}")
