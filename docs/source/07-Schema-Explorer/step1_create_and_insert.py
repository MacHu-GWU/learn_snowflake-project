"""
Step 1: build a 4-table relational schema and seed ~50 rows.

The model demonstrates the two canonical relationships:

- ``USERS`` 1-to-many ``POSTS`` (POSTS.user_id is the FK).
- ``POSTS`` many-to-many ``TAGS`` through the ``POST_TAGS`` association table
  (a composite-PK table whose two columns are both FKs).

The DROP DATABASE at the very bottom is **commented out on purpose** — leave the
schema in place so ``step2_reflect_and_print.py`` has something to introspect.
Run ``step3_drop.py`` when you actually want to clean up.

Run with::

    .venv/bin/python docs/source/07-Schema-Explorer/step1_create_and_insert.py
"""

import os

from sqlalchemy import ForeignKey, Integer, String, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from snowflake.sqlalchemy import URL


WAREHOUSE = "LEARN_WH"
DATABASE = "LEARN_DB"
SCHEMA = "PLAYGROUND"
SCHEMA_PATH = f"{DATABASE}.{SCHEMA}"


class Base(DeclarativeBase):
    pass


class User(Base):
    """Author of blog posts. 1-to-many with POSTS."""

    __tablename__ = "USERS"
    __table_args__ = {"schema": SCHEMA_PATH}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(200), nullable=False)


class Post(Base):
    """Blog post. FK to USERS (1-to-many) and M:N to TAGS via POST_TAGS."""

    __tablename__ = "POSTS"
    __table_args__ = {"schema": SCHEMA_PATH}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{SCHEMA_PATH}.USERS.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(String)


class Tag(Base):
    """Topic tag. M:N with POSTS via POST_TAGS."""

    __tablename__ = "TAGS"
    __table_args__ = {"schema": SCHEMA_PATH}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)


class PostTag(Base):
    """Association table — composite PK of two FKs implements POSTS↔TAGS M:N."""

    __tablename__ = "POST_TAGS"
    __table_args__ = {"schema": SCHEMA_PATH}

    post_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{SCHEMA_PATH}.POSTS.id"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{SCHEMA_PATH}.TAGS.id"),
        primary_key=True,
    )


def build_engine():
    # Pin warehouse at the URL level so every connection from the pool uses
    # LEARN_WH, not the user's DEFAULT_WAREHOUSE (which on trial is the
    # always-on COMPUTE_WH — would silently burn credits).
    # First-run safety: Snowflake validates the warehouse lazily on first
    # query that needs compute, so connecting with warehouse=LEARN_WH before
    # it exists is fine — bootstrap()'s CREATE WAREHOUSE is a metadata op
    # and doesn't need an active warehouse.
    url = URL(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=WAREHOUSE,
        role=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
    )
    return create_engine(url)


def bootstrap(engine) -> None:
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
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_PATH}"))


def seed(engine) -> dict[str, int]:
    Base.metadata.create_all(engine, checkfirst=True)

    users = [
        User(id=i, username=f"user_{i}", email=f"u{i}@example.com")
        for i in range(1, 6)
    ]
    posts = [
        Post(
            id=post_id,
            user_id=((post_id - 1) // 3) + 1,
            title=f"Post {post_id}",
            content=f"Body of post {post_id}",
        )
        for post_id in range(1, 16)
    ]
    tag_names = [
        "python", "data", "snowflake", "sql", "etl",
        "ml", "ai", "warehouse", "cloud", "tutorial",
    ]
    tags = [Tag(id=i + 1, name=name) for i, name in enumerate(tag_names)]

    # 20 associations spread across the 15 posts.
    # Round 1: (post_id, (post_id % 10) + 1) for posts 1..15  → 15 rows
    # Round 2: (post_id, ((post_id + 4) % 10) + 1) for posts 1..5 → 5 more rows
    post_tags = [
        PostTag(post_id=p, tag_id=(p % 10) + 1) for p in range(1, 16)
    ] + [
        PostTag(post_id=p, tag_id=((p + 4) % 10) + 1) for p in range(1, 6)
    ]

    with Session(engine) as session:
        session.add_all(users + posts + tags + post_tags)
        session.commit()

    return {
        User.__tablename__: len(users),
        Post.__tablename__: len(posts),
        Tag.__tablename__: len(tags),
        PostTag.__tablename__: len(post_tags),
    }


def main() -> None:
    engine = build_engine()
    try:
        bootstrap(engine)
        print(f"[1/2] warehouse {WAREHOUSE} / database {SCHEMA_PATH} ready")
        counts = seed(engine)
        total = sum(counts.values())
        print(f"[2/2] seeded {total} rows:")
        for name, n in counts.items():
            print(f"        {name:<12} {n:>3} rows")

        # ----------------------------------------------------------------
        # Cleanup is intentionally commented out — keep the schema around
        # so step2_reflect_and_print.py has something to introspect.
        # Run step3_drop.py to actually drop the database.
        # ----------------------------------------------------------------
        # with engine.begin() as conn:
        #     conn.execute(text(f"DROP DATABASE IF EXISTS {DATABASE}"))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
