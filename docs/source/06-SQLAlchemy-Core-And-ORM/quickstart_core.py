"""
Snowflake + SQLAlchemy **Core** style — end-to-end quickstart.

Same warehouse / db / schema / table / insert / select / cleanup as
``05-CRUD-With-Python-Connector``, but the table is described as a
``Table`` object and the queries are built with the SQL Expression
Language — no raw SQL strings for table operations.

Bootstrap DDL (CREATE WAREHOUSE / DATABASE / SCHEMA) still goes through
``text()`` because those objects aren't part of SQLAlchemy's typical
schema metadata.

Run with::

    .venv/bin/python docs/source/06-SQLAlchemy-Core-And-ORM/quickstart_core.py
"""

import os
from datetime import date

from sqlalchemy import (
    Column,
    Date,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
    select,
    text,
)
from snowflake.sqlalchemy import URL


WAREHOUSE = "LEARN_WH"
DATABASE = "LEARN_DB"
SCHEMA = "PLAYGROUND"
TABLE = "BOOKS_CORE"


def build_engine():
    # Pin warehouse at the URL level — otherwise every connection from the
    # pool falls back to DEFAULT_WAREHOUSE (COMPUTE_WH on trial) instead of
    # our X-Small auto-suspend LEARN_WH.
    url = URL(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=WAREHOUSE,
        role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
    )
    return create_engine(url)


def main() -> None:
    engine = build_engine()

    metadata = MetaData()
    books = Table(
        TABLE,
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("title", String, nullable=False),
        Column("rating", Integer),
        Column("read_at", Date),
        Column("notes", String),
        schema=f"{DATABASE}.{SCHEMA}",
    )

    try:
        # 1) Bootstrap — DDL for warehouse / db / schema goes through text().
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    CREATE WAREHOUSE IF NOT EXISTS {WAREHOUSE}
                        WAREHOUSE_SIZE = 'XSMALL'
                        AUTO_SUSPEND   = 60
                        AUTO_RESUME    = TRUE
                        INITIALLY_SUSPENDED = TRUE
                    """
                )
            )
            conn.execute(text(f"USE WAREHOUSE {WAREHOUSE}"))
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {DATABASE}"))
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DATABASE}.{SCHEMA}"))
        print(f"[1/5] warehouse {WAREHOUSE} / database {DATABASE}.{SCHEMA} ready")

        # 2) Table — created from the SQLAlchemy MetaData (Core).
        metadata.create_all(engine, checkfirst=True)
        print(f"[2/5] table {TABLE} ready")

        # 3) Insert — Core expression: insert(books) + list of dicts.
        rows = [
            {"title": "Designing Data-Intensive Applications", "rating": 5, "read_at": date(2026, 4, 12), "notes": "Must read"},
            {"title": "The Pragmatic Programmer",              "rating": 4, "read_at": date(2026, 5, 3),  "notes": "Classic"},
            {"title": "Database Internals",                    "rating": 5, "read_at": date(2026, 5, 20), "notes": "Deep dive"},
        ]
        with engine.begin() as conn:
            conn.execute(insert(books), rows)
        print(f"[3/5] inserted {len(rows)} rows")

        # 4) Select — Core expression: select() with column refs + ORDER BY.
        stmt = (
            select(books.c.id, books.c.title, books.c.rating)
            .order_by(books.c.rating.desc(), books.c.id)
        )
        with engine.connect() as conn:
            print("[4/5] query result:")
            print(f"     {'id':>3}  {'title':<40}  {'rating':>6}")
            for row in conn.execute(stmt):
                print(f"     {row.id:>3}  {row.title:<40}  {row.rating:>6}")

        # 5) Cleanup — back to raw DDL.
        with engine.begin() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {DATABASE}"))
        print(f"[5/5] dropped database {DATABASE}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
