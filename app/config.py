"""
FinSight AI — configuration.

All settings come from environment variables (loaded from a local .env file in
development). Nothing secret is hard-coded — this satisfies NFR REQ-6 (API keys
and connection strings live in environment secrets, never in the codebase).
"""

import os

try:
    # Optional: auto-load a local .env during development.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv not installed — env vars must be set another way
    pass


# Default to a local SQLite file. In production, set DATABASE_URL to the
# Postgres connection string, e.g.:
#   postgresql+psycopg2://user:password@host:5432/finsight
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///finsight.db")

# Echo SQL to stdout when debugging (set SQL_ECHO=1).
SQL_ECHO: bool = os.getenv("SQL_ECHO", "0") in ("1", "true", "True")

# Convenience flag used by the engine factory.
IS_SQLITE: bool = DATABASE_URL.startswith("sqlite")