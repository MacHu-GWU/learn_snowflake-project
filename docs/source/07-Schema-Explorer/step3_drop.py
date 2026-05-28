"""
Step 3: drop the database to clean up. Run when you're done with the POC.

step1 deliberately leaves ``LEARN_DB`` around so step2 has something to
reflect. Use this script to actually delete it. The warehouse is kept
intact — it auto-suspends after 60 seconds and re-runs of step1 are then
faster.

Run with::

    .venv/bin/python docs/source/07-Schema-Explorer/step3_drop.py
"""

import os

from sqlalchemy import create_engine, text
from snowflake.sqlalchemy import URL


DATABASE = "LEARN_DB"
WAREHOUSE = "LEARN_WH"


def main() -> None:
    url = URL(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=WAREHOUSE,
        role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
    )
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {DATABASE}"))
        print(f"dropped database {DATABASE}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
