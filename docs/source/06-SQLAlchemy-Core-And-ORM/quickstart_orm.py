"""
Snowflake + SQLAlchemy **ORM** style — end-to-end quickstart.

Same warehouse / db / schema / table / insert / select / cleanup as
``quickstart_core.py``, but the table is described as a Python class
that inherits from a ``DeclarativeBase``, and rows are inserted /
queried as Python objects through a ``Session``.

Bootstrap and teardown DDL still go through ``text()`` because
warehouses and databases aren't part of SQLAlchemy's typed schema.

Run with::

    .venv/bin/python docs/source/06-SQLAlchemy-Core-And-ORM/quickstart_orm.py
"""

import os
from datetime import date

from sqlalchemy import Date, Integer, String, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from snowflake.sqlalchemy import URL


WAREHOUSE = "LEARN_WH"
DATABASE = "LEARN_DB"
SCHEMA = "PLAYGROUND"


class Base(DeclarativeBase):
    pass


# Note: Snowflake's AUTOINCREMENT / IDENTITY value is not returned back to
# SQLAlchemy in the round-trip the ORM unit-of-work expects, so we omit
# autoincrement here and pass ``id`` explicitly when constructing rows.
# For production you'd typically manage a Snowflake ``SEQUENCE`` yourself.
class Book(Base):
    __tablename__ = "BOOKS_ORM"
    __table_args__ = {"schema": f"{DATABASE}.{SCHEMA}"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer)
    read_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String)

    def __repr__(self) -> str:
        return f"<Book id={self.id} title={self.title!r} rating={self.rating}>"


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
    try:
        # 1) Bootstrap — same DDL as the Core script, via text().
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

        # 2) Table — created from the ORM model's metadata.
        Base.metadata.create_all(engine, checkfirst=True)
        print(f"[2/5] table {Book.__tablename__} ready")

        # 3 + 4) Session: insert Book objects, then query them back.
        with Session(engine) as session:
            session.add_all(
                [
                    Book(id=1, title="Designing Data-Intensive Applications", rating=5, read_at=date(2026, 4, 12), notes="Must read"),
                    Book(id=2, title="The Pragmatic Programmer",              rating=4, read_at=date(2026, 5, 3),  notes="Classic"),
                    Book(id=3, title="Database Internals",                    rating=5, read_at=date(2026, 5, 20), notes="Deep dive"),
                ]
            )
            session.commit()
            print("[3/5] inserted 3 rows")

            stmt = select(Book).order_by(Book.rating.desc(), Book.id)
            print("[4/5] query result:")
            for book in session.scalars(stmt):
                print(f"     {book}")

        # 5) Cleanup — DROP DATABASE via text().
        with engine.begin() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {DATABASE}"))
        print(f"[5/5] dropped database {DATABASE}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
