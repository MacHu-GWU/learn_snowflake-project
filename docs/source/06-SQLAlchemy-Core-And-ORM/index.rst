用 SQLAlchemy（Core / ORM）替掉裸 SQL
==============================================================================


写在前面
------------------------------------------------------------------------------
上一篇我们用 ``snowflake-connector-python`` 直接跑 raw SQL——简单粗暴，
什么 SQL 都能塞进去。但是再往复杂场景走的时候，三个问题会冒出来：

- **SQL 字符串拼接容易出错**（少个逗号、表名打错）；
- **跨数据库不可移植**（同一段 INSERT 在 SQLite/Postgres/Snowflake 上语法可能不
  一致）；
- **手动管理 cursor / 事务 / 类型转换**，样板代码越写越多。

SQLAlchemy 就是解决这些问题的标准答案。它提供两种风格：

- **Core (SQL Expression Language)** —— 把表当成 Python 对象，用方法链构造
  ``select() / insert() / update() / delete()``。**生成的 SQL 看起来还是 SQL**，
  只是用 Python 写。适合：偏 DB-first 的项目、做数据 ETL / 分析。
- **ORM (Object Relational Mapper)** —— 把表当成 Python class，把行当成 Python
  对象。``session.add(book)``、``session.query(Book).filter(...)``，**几乎看不到
  SQL**。适合：偏应用 / Web 后端、行级别的业务逻辑。

这一篇用两个独立的脚本各演示一遍，做的事和 05 篇完全一样：建仓 → 建库 → 建表
→ 插数据 → 查回来 → 清场。但是 **表定义和 CRUD 全部走 SQLAlchemy**，不再拼
SQL 字符串。


前置条件
------------------------------------------------------------------------------
**1. .env 和 03 篇的 PAT 一切如旧**——env vars 这一套照搬，连接器底层用的还是
``snowflake-connector-python``。

**2. 装 snowflake-sqlalchemy**:

.. code-block:: bash

    uv add snowflake-sqlalchemy

它会顺带把 ``sqlalchemy`` 和 ``snowflake-connector-python`` 拉过来。


两种风格速览
------------------------------------------------------------------------------
.. list-table::
   :header-rows: 1
   :widths: 25 37 38

   * - 维度
     - Core
     - ORM
   * - 表的抽象
     - ``Table(...)`` + ``MetaData()``
     - ``class Book(Base): ...``
   * - 连接 / 事务
     - ``engine.begin()`` / ``engine.connect()``
     - ``Session(engine)`` (自带工作单元)
   * - INSERT
     - ``conn.execute(insert(t), [dict,...])``
     - ``session.add_all([Book(...), ...])``
   * - SELECT
     - ``conn.execute(select(t.c.x, ...))`` 返回 row tuple
     - ``session.scalars(select(Book))`` 返回 ``Book`` 实例
   * - 心智模型
     - "在 Python 里写 SQL"
     - "操作 Python 对象，SQL 自动飞"


Core 风格：``quickstart_core.py``
------------------------------------------------------------------------------
这个脚本演示的 pattern：

- **用 ``URL(...)`` 拼连接字符串**——``snowflake.sqlalchemy.URL`` builder 接受
  ``account``、``user``、``password`` (PAT)、``role`` 等参数，避免手拼 URL。
- **``create_engine(url)`` 一次构造、全程复用**——SQLAlchemy 的连接池替你管。
- **``MetaData()`` + ``Table(name, metadata, Column(...))`` 描述表结构**——
  schema 写成 ``"<DATABASE>.<SCHEMA>"`` 让表名全限定。
- **Bootstrap 仍走 ``text()``**——CREATE WAREHOUSE / DATABASE / SCHEMA 不是
  SQLAlchemy 抽象里的"object"，没法用 ``MetaData`` 管，落回纯 SQL。
- **``metadata.create_all(engine, checkfirst=True)``**——一行建表，幂等。
- **``conn.execute(insert(table), [dict, dict, ...])``**——参数绑定、批量 insert
  内置，不需要手写 ``%s``。
- **``select(t.c.id, t.c.title).order_by(...).where(...)`` 链式构造 SELECT**——
  类型安全、IDE 自动补全、可以拼接复用。结果迭代返回 ``Row``，按列名访问。
- **``engine.begin()`` 是事务、``engine.connect()`` 是只读**——读多用后者，
  写多用前者（自动 commit / rollback）。
- **``engine.dispose()`` 在 ``finally`` 里关连接池**——好习惯。

.. literalinclude:: ./quickstart_core.py
   :language: python
   :linenos:
   :caption: docs/source/06-SQLAlchemy-Core-And-ORM/quickstart_core.py


ORM 风格：``quickstart_orm.py``
------------------------------------------------------------------------------
这个脚本演示的 pattern：

- **``class Base(DeclarativeBase): pass``**——SQLAlchemy 2.0 的现代 declarative
  base 入口。
- **``class Book(Base)`` 带 ``__tablename__`` / ``__table_args__``**——
  ``schema`` 仍然写 ``"<DATABASE>.<SCHEMA>"`` 做全限定。
- **``Mapped[T]`` + ``mapped_column(...)`` 是 SQLAlchemy 2.0 的类型化列**——
  IDE 一眼看出每列是什么 Python 类型，运行时也有验证。
- **``Base.metadata.create_all(engine)``** 把所有继承自 ``Base`` 的类自动建表。
- **``with Session(engine) as session:`` —— 工作单元（unit of work）模式**。
  ``add_all([...])`` 只是把对象放进 session、``commit()`` 时才真正 flush 出
  INSERT。
- **``session.scalars(select(Book))`` 返回 ``Book`` 实例的迭代器**——拿到的不
  是 row tuple 而是 class 实例。可以直接 ``book.title`` 这样访问。

.. warning::

   **Snowflake 的 auto-increment 在 SQLAlchemy ORM 里有坑**：Snowflake 不通过
   "INSERT … RETURNING" 把生成的主键回传给客户端，所以 ORM 的工作单元拿不到
   新建对象的 ``id``，``commit()`` 时会抛 ``NULL identity key`` 错误。

   实际可用的两条路：

   - **本脚本采用的方法**：表上不开 ``autoincrement``，**插入时显式给 ``id``**。
     最简单，对学习场景够用。
   - **生产环境推荐**：在 Snowflake 里手动 ``CREATE SEQUENCE``，应用层用
     ``conn.execute(text("SELECT my_seq.NEXTVAL")).scalar()`` 取下一个 id，
     再喂给 ORM 对象。

.. literalinclude:: ./quickstart_orm.py
   :language: python
   :linenos:
   :caption: docs/source/06-SQLAlchemy-Core-And-ORM/quickstart_orm.py


怎么跑
------------------------------------------------------------------------------
两个脚本都幂等、都自带清场，跑哪个、跑几次都不会留脏状态：

.. code-block:: bash

    # Core
    .venv/bin/python docs/source/06-SQLAlchemy-Core-And-ORM/quickstart_core.py

    # ORM
    .venv/bin/python docs/source/06-SQLAlchemy-Core-And-ORM/quickstart_orm.py

两个脚本预期输出几乎一样（数字对齐略差一点）::

    [1/5] warehouse LEARN_WH / database LEARN_DB.PLAYGROUND ready
    [2/5] table BOOKS_CORE ready          # ORM 这里是 BOOKS_ORM
    [3/5] inserted 3 rows
    [4/5] query result:
           ...
    [5/5] dropped database LEARN_DB


啥时候用 Core，啥时候用 ORM
------------------------------------------------------------------------------
.. list-table::
   :header-rows: 1
   :widths: 35 30 35

   * - 场景
     - Core
     - ORM
   * - 数据 ETL / 分析、批量计算
     - ✅ 偏好
     - 杀鸡用牛刀
   * - Web 后端 / API 单行 CRUD
     - 可以
     - ✅ 偏好
   * - 已经有现成的复杂 SQL
     - ✅ 直接 ``text()`` 接管
     - 强行用 ORM 容易别扭
   * - 想让 Python 业务对象和 DB 行结构强绑定
     - ❌
     - ✅
   * - 关注查询性能、避免 N+1
     - ✅ 一切显式
     - 要懂 ``selectinload`` / ``joinedload``
   * - 团队里大家熟悉 ORM 而不熟 SQL
     - ❌
     - ✅

**学习路径建议**：先 Core 上手（你已经会 SQL 了，Core 就是把 SQL 翻成 Python
方法链）；再 ORM（多一层抽象，但能"忘掉"表结构、专注业务对象）。


参考资料
------------------------------------------------------------------------------
- `snowflake-sqlalchemy README <https://github.com/snowflakedb/snowflake-sqlalchemy>`_
- `SQLAlchemy 2.0 — Core: SQL Expression Language Tutorial <https://docs.sqlalchemy.org/en/20/tutorial/index.html>`_
- `SQLAlchemy 2.0 — ORM Quick Start <https://docs.sqlalchemy.org/en/20/orm/quickstart.html>`_
- `Snowflake SEQUENCE reference <https://docs.snowflake.com/en/sql-reference/sql/create-sequence>`_
