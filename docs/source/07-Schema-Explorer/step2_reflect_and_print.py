"""
Step 2: connect, reflect Snowflake's schema, print it in a compact text view.

This is the core of the POC: with **zero hand-written DDL**, SQLAlchemy
queries Snowflake's INFORMATION_SCHEMA, rebuilds the ``Table`` objects
(columns, types, primary keys, foreign keys), and we then run the result
through the project's extractor/encoder (lifted from a larger library
into this folder) to print a token-efficient schema view.

Reference for the SQLAlchemy + Snowflake pieces:
https://docs.snowflake.com/en/developer-guide/python-connector/sqlalchemy

Run with::

    .venv/bin/python docs/source/07-Schema-Explorer/step2_reflect_and_print.py
"""

import os
import sys
from pathlib import Path

# Make this folder's modules importable (constants.py, schema_3_extractor.py, ...).
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import MetaData, create_engine
from snowflake.sqlalchemy import URL

from constants import DbTypeEnum
from schema_2_encoder import encode_database_info
from schema_3_extractor import new_database_info, new_schema_info


WAREHOUSE = "LEARN_WH"
DATABASE = "LEARN_DB"
SCHEMA = "PLAYGROUND"
SCHEMA_PATH = f"{DATABASE}.{SCHEMA}"


def build_engine():
    # Pin the engine to the database we want to introspect. Snowflake's
    # SQLAlchemy reflector reads INFORMATION_SCHEMA off the *current* database,
    # so it has to be set at connection time (passing "DB.SCHEMA" as a single
    # ``schema=`` arg confuses the reflector into thinking the database is None).
    url = URL(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=WAREHOUSE,
        database=DATABASE,
        schema=SCHEMA,
        role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
    )
    return create_engine(url)


def main() -> None:
    engine = build_engine()
    try:
        # 1) Reflect — no DDL written here; SQLAlchemy + Snowflake-SQLAlchemy
        #    introspect INFORMATION_SCHEMA on the fly. The schema= here is the
        #    bare schema name; the database comes from the engine URL.
        metadata = MetaData(schema=SCHEMA)
        metadata.reflect(bind=engine)

        # snowflake-sqlalchemy's FK reflector can register the same Table
        # under both "name" and "SCHEMA.name", so we filter to the canonical
        # ones (schema == SCHEMA) for the preview.
        real_tables = [t for t in metadata.sorted_tables if t.schema == SCHEMA]
        print("=" * 72)
        print(f"Reflected {len(real_tables)} tables from {SCHEMA_PATH}")
        print("=" * 72)
        for table in real_tables:
            print(f"  {table.name}  ({len(table.c)} columns, {len(table.foreign_keys)} FKs)")

        # 2) Hand the reflected metadata to the extractor (from schema_3_extractor.py).
        #    It walks the Table objects and produces a pydantic SchemaInfo /
        #    DatabaseInfo tree — typed, serializable, easy to programmatically
        #    iterate (e.g. feed to an LLM).
        schema_info = new_schema_info(
            engine=engine,
            metadata=metadata,
            schema_name=SCHEMA,
        )
        database_info = new_database_info(
            name=DATABASE,
            db_type=DbTypeEnum.SNOWFLAKE,
            schemas=[schema_info],
        )

        # 3) Encode for LLM-friendly compact text view (from schema_2_encoder.py).
        print()
        print("=" * 72)
        print("Compact schema view (encoded for LLM token efficiency)")
        print("=" * 72)
        print(encode_database_info(database_info))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
