"""
Snowflake Python Connector — End-to-End Quickstart.

This script does in Python what docs 03 + 04 do via the CLI:

1. Connects to Snowflake using credentials from environment variables
   (loaded by mise from ``.env``). The ``SNOWFLAKE_PASSWORD`` value is
   a Programmatic Access Token (PAT), not a real password.
2. Creates a minimal warehouse / database / schema / table.
3. Bulk-inserts a few rows using parameterized queries.
4. Reads them back and prints the result.
5. Drops the database to clean up.

Run with::

    .venv/bin/python docs/source/05-CRUD-With-Python-Connector/snowflake_quickstart.py
"""

import os
import snowflake.connector


WAREHOUSE = "LEARN_WH"
DATABASE = "LEARN_DB"
SCHEMA = "PLAYGROUND"
TABLE = "BOOKS"


def get_connection() -> snowflake.connector.SnowflakeConnection:
    # Pin warehouse at connect time. Without this, the session falls back to
    # the user's DEFAULT_WAREHOUSE (trial default is COMPUTE_WH), so the
    # XSMALL + auto-suspend LEARN_WH we create below silently goes unused.
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=WAREHOUSE,
        role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
    )


def main() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1) Warehouse — XSMALL + auto-suspend keeps the bill near zero.
            cur.execute(
                f"""
                CREATE WAREHOUSE IF NOT EXISTS {WAREHOUSE}
                    WAREHOUSE_SIZE = 'XSMALL'
                    AUTO_SUSPEND   = 60
                    AUTO_RESUME    = TRUE
                    INITIALLY_SUSPENDED = TRUE
                """
            )
            cur.execute(f"USE WAREHOUSE {WAREHOUSE}")
            print(f"[1/5] warehouse {WAREHOUSE} ready")

            # 2) Database + 3) Schema.
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {DATABASE}")
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {DATABASE}.{SCHEMA}")
            print(f"[2/5] database {DATABASE}.{SCHEMA} ready")

            # 4) Table — TRANSIENT keeps storage cheap for learning.
            cur.execute(
                f"""
                CREATE OR REPLACE TRANSIENT TABLE {DATABASE}.{SCHEMA}.{TABLE} (
                    id      INT AUTOINCREMENT START 1 INCREMENT 1,
                    title   STRING NOT NULL,
                    rating  INT,
                    read_at DATE,
                    notes   STRING
                )
                """
            )
            print(f"[3/5] table {TABLE} ready")

            # 5) Bulk insert via parameter binding (the safe / idiomatic way).
            rows = [
                ("Designing Data-Intensive Applications", 5, "2026-04-12", "Must read"),
                ("The Pragmatic Programmer",              4, "2026-05-03", "Classic"),
                ("Database Internals",                    5, "2026-05-20", "Deep dive"),
            ]
            cur.executemany(
                f"""
                INSERT INTO {DATABASE}.{SCHEMA}.{TABLE} (title, rating, read_at, notes)
                VALUES (%s, %s, %s, %s)
                """,
                rows,
            )
            print(f"[4/5] inserted {len(rows)} rows")

            # 6) Query + iterate.
            cur.execute(
                f"""
                SELECT id, title, rating
                  FROM {DATABASE}.{SCHEMA}.{TABLE}
                 ORDER BY rating DESC, id
                """
            )
            print(f"[5/5] query result:")
            print(f"     {'id':>3}  {'title':<40}  {'rating':>6}")
            for row_id, title, rating in cur:
                print(f"     {row_id:>3}  {title:<40}  {rating:>6}")

            # Cleanup. Drop the DB only; leave LEARN_WH so re-runs are faster.
            cur.execute(f"DROP DATABASE IF EXISTS {DATABASE}")
            print(f"[cleanup] dropped database {DATABASE}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
