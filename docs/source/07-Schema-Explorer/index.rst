Schema Explorer：用 SQLAlchemy ``reflect`` 反向拿回 Snowflake 的元数据
==============================================================================


写在前面
------------------------------------------------------------------------------
06 篇我们用 SQLAlchemy 把 Python class 推下去变成 Snowflake 里的表。这一篇
反过来：

  **不写一行 DDL，让 SQLAlchemy 去 Snowflake 把所有表/列/外键的元数据**
  **"反射" 回 Python 内存，然后我们把它编码成一份对 LLM 友好的紧凑文本视图。**

为啥要这么干？两个场景：

- **Text-to-SQL / 自动化数据探索**：把数据库 schema 喂给 LLM 之前，需要一份比
  原始 ``SHOW TABLES`` 输出更结构化、token 更省的描述。
- **Schema-aware 的代码工具**：IDE / agent 需要知道表的列、主键、外键，才能
  做补全 / 校验 / 关联推理。``reflect()`` 是省事的拿到途径——你不需要维护
  ORM 模型的副本。

POC 拆三步：

==============  =======================================================
脚本             干啥的
==============  =======================================================
``step1_...``   用 ORM 建 4 张关系表 + 灌 50 行数据。**末尾的 DROP 注释掉了**。
``step2_...``   连上 Snowflake → ``MetaData.reflect()`` → 走 extractor → 走 encoder → 打印。
``step3_...``   单独跑这条把 ``LEARN_DB`` 清掉。
==============  =======================================================

参考：`Snowflake Python Connector + SQLAlchemy 官方文档
<https://docs.snowflake.com/en/developer-guide/python-connector/sqlalchemy>`_。


数据模型：1-对多 + 多对多（经典关系建模）
------------------------------------------------------------------------------
4 张表把 1-对多和多对多两种关系都覆盖：

.. code-block:: text

           USERS                                   TAGS
          ┌──────┐                                ┌──────┐
          │ id   │                                │ id   │
          │ ...  │                                │ ...  │
          └──┬───┘                                └──┬───┘
             │ 1                                     │ 1
             │                                       │
             │ N                                     │ N
          ┌──┴─────┐  N    ┌─────────────┐   N   ┌──┴───┐
          │ POSTS  │───────│  POST_TAGS  │───────│ TAGS │
          │ id     │       │ post_id PK  │       │      │
          │ user_id│ FK    │ tag_id  PK  │       │      │
          └────────┘       └─────────────┘       └──────┘
                          (association table)

- ``POSTS.user_id`` 指向 ``USERS.id`` —— **1 用户 → 多 post**。
- ``POST_TAGS`` 是经典 association table：复合主键 ``(post_id, tag_id)``
  两列同时都是 FK —— **post ↔ tag 多对多**。

行数预算：5 users + 15 posts + 10 tags + 20 post_tags = **50 行**，总量小到
出错也无感。


"那几个看起来奇怪的文件" 是干啥的
------------------------------------------------------------------------------
folder 里这几个文件是从一个完整的 schema-introspection 库里抽出来的，目的是给
LLM 提供一种比原始 SQLAlchemy 对象更友好的中间表示：

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 文件
     - 职责
   * - ``constants.py``
     - 各种枚举：DB 类型 (Snowflake / Postgres / ...)、表类型、列类型缩写
       (PK / UQ / NN / IDX / FK)、LLM-friendly 类型缩写 (str / int / dec / ...)。
   * - ``metadata.py``
     - 基础 Pydantic 模型：``BaseInfo`` / ``BaseColumnInfo`` /
       ``BaseTableInfo`` / ``BaseSchemaInfo`` / ``BaseDatabaseInfo``。
   * - ``schema_1_model.py``
     - 在基础模型上扩展出 ``ForeignKeyInfo`` / ``ColumnInfo`` / ``TableInfo`` /
       ``SchemaInfo`` / ``DatabaseInfo`` —— 带 SQLAlchemy 特有字段（type、
       primary_key、nullable、foreign_keys 等）。
   * - ``schema_2_encoder.py``
     - 把上面的 Pydantic 树编码成紧凑文本格式 (``Table T(col:type*PK*FK->X.Y)``)。
       *专为 LLM token 效率设计*——比 SQL DDL 省 ~70%。
   * - ``schema_3_extractor.py``
     - 桥接层：吃一个 SQLAlchemy 的 ``Engine`` + ``MetaData``，吐出
       ``SchemaInfo`` / ``DatabaseInfo`` 实例。

**关键 pattern**：``step2`` 不直接拼字符串去描述 schema，而是

::

    SQLAlchemy reflect → extractor → SchemaInfo (pydantic) → encoder → text

四步管线，每一步责任单一、易测试、易替换（比如想换 JSON 输出就改 encoder）。


step1：建表 + 灌数据
------------------------------------------------------------------------------
``step1_create_and_insert.py`` 演示的 pattern：

- **4 个 ORM class 全用 SQLAlchemy 2.0 的 ``Mapped[T]`` + ``mapped_column(...)``
  写法**——类型在签名上明示，IDE 一眼能看出每列类型。
- **``__table_args__ = {"schema": "DATABASE.SCHEMA"}``**——表名全限定。
- **``ForeignKey("DATABASE.SCHEMA.USERS.id")`` 用全限定字符串引用 FK 目标**——
  这样 SQLAlchemy 不用从 metadata 里搜表。
- **Bootstrap 走 ``text()``**——warehouse / database / schema 这些不是
  SQLAlchemy 抽象里的对象，仍然要写 raw SQL。
- **``Base.metadata.create_all(engine, checkfirst=True)`` 一行建 4 张表**——
  FK 依赖顺序由 SQLAlchemy 自动排序。
- **手动管 ``id``**——上一篇说过 Snowflake 的 AUTOINCREMENT 在 ORM 里不能回填，
  这里依旧显式指定 id。
- **``session.add_all(users + posts + tags + post_tags)`` + ``session.commit()``**
  ——4 张表一起 flush，SQLAlchemy 根据 FK 关系决定 INSERT 顺序。
- **末尾的 ``DROP DATABASE`` 是注释掉的**——保留数据，让 step2 有得反射。

.. literalinclude:: ./step1_create_and_insert.py
   :language: python
   :linenos:
   :caption: docs/source/07-Schema-Explorer/step1_create_and_insert.py


step2：reflect + extractor + encoder（核心）
------------------------------------------------------------------------------
``step2_reflect_and_print.py`` 演示的 pattern：

- **``URL(... database=DATABASE, schema=SCHEMA ...)`` 把 DB/schema 钉在 engine
  级别**——这是一个 Snowflake-SQLAlchemy 的坑：如果你把 ``"DB.SCHEMA"`` 当成
  一个字符串塞进 ``MetaData(schema=...)``，反射器会把 DB 解析成字面 ``"None"``
  然后查 ``"None".information_schema.columns``，报 ``Database '"None"' does
  not exist``。**正解是把 database 放 URL 里**。
- **``MetaData(schema=SCHEMA).reflect(bind=engine)`` —— 一行拉回所有表**。
  SQLAlchemy 后台会查 INFORMATION_SCHEMA 把列、PK、FK 全部还原成 ``Table`` 对象。
- **``metadata.sorted_tables`` 按 FK 拓扑序返回表**——这就是 encoder 能输出
  "tags → users → posts → post_tags" 这种依赖顺序的原因。
- **snowflake-sqlalchemy 反射 FK 时会副作用地往 metadata 里塞带 schema 前缀的
  副本**——所以 ``len(metadata.tables)`` 可能比真实表数多。脚本里用
  ``[t for t in metadata.sorted_tables if t.schema == SCHEMA]`` 过滤掉副本。
- **三步管线 ``reflect → new_schema_info → encode_database_info``**——
  每一步都是纯函数，输入输出明确，单独测试都很简单。

.. literalinclude:: ./step2_reflect_and_print.py
   :language: python
   :linenos:
   :caption: docs/source/07-Schema-Explorer/step2_reflect_and_print.py


step3：清场
------------------------------------------------------------------------------
.. literalinclude:: ./step3_drop.py
   :language: python
   :linenos:
   :caption: docs/source/07-Schema-Explorer/step3_drop.py


怎么跑
------------------------------------------------------------------------------
.. code-block:: bash

    # 1) 建表 + 灌 50 行数据（末尾 DROP 注释掉了，保留数据给 step2）
    .venv/bin/python docs/source/07-Schema-Explorer/step1_create_and_insert.py

    # 2) reflect + 打印（核心 POC）
    .venv/bin/python docs/source/07-Schema-Explorer/step2_reflect_and_print.py

    # 3) 玩够了再清场
    .venv/bin/python docs/source/07-Schema-Explorer/step3_drop.py


预期输出（节选）
------------------------------------------------------------------------------
``step1`` ::

    [1/2] warehouse LEARN_WH / database LEARN_DB.PLAYGROUND ready
    [2/2] seeded 50 rows:
            USERS          5 rows
            POSTS         15 rows
            TAGS          10 rows
            POST_TAGS     20 rows

``step2`` ::

    ========================================================================
    Reflected 4 tables from LEARN_DB.PLAYGROUND
    ========================================================================
      tags  (2 columns, 0 FKs)
      users  (3 columns, 0 FKs)
      posts  (4 columns, 1 FKs)
      post_tags  (2 columns, 2 FKs)

    ========================================================================
    Compact schema view (encoded for LLM token efficiency)
    ========================================================================
    snowflake Database LEARN_DB(
      Schema PLAYGROUND(
        Table tags(
          id:dec*PK,
          name:str*NN,
        )
        Table users(
          id:dec*PK,
          username:str*NN,
          email:str*NN,
        )
        Table posts(
          id:dec*PK,
          user_id:dec*NN*FK->users.id,
          title:str*NN,
          content:str,
        )
        Table post_tags(
          post_id:dec*PK*FK->posts.id,
          tag_id:dec*PK*FK->tags.id,
        )
      )
    )


踩过的 Snowflake 特有的坑
------------------------------------------------------------------------------
.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - 现象
     - 解释
   * - 整数列反射回来变成 ``dec`` (DECIMAL) 不是 ``int``
     - Snowflake 内部把所有 ``INTEGER`` 存成 ``NUMBER(38, 0)``，
       INFORMATION_SCHEMA 报出来就是 DECIMAL。这是 Snowflake 的存储真相、不是
       bug。
   * - ``MetaData.reflect(schema="DB.SCHEMA")`` 报
       ``Database '"None"' does not exist``
     - snowflake-sqlalchemy 反射时不解析 "dot-form"。Database 必须放 ``URL(...)``
       里、schema 单独传。
   * - ``metadata.tables`` 里出现 ``PLAYGROUND.posts`` 这种带前缀的副本
     - 反射 FK 时副作用注册的额外条目。用 ``[t for t in
       metadata.sorted_tables if t.schema == SCHEMA]`` 过滤掉。
   * - 上一篇说过：ORM ``autoincrement`` 在 Snowflake 拿不回 id
     - 这里依然显式 ``id=1, id=2, ...``。一致策略。


参考资料
------------------------------------------------------------------------------
- `Using Connector + SQLAlchemy (Snowflake 官方) <https://docs.snowflake.com/en/developer-guide/python-connector/sqlalchemy>`_
- `SQLAlchemy MetaData.reflect <https://docs.sqlalchemy.org/en/20/core/metadata.html#sqlalchemy.schema.MetaData.reflect>`_
- `SQLAlchemy Inspection API <https://docs.sqlalchemy.org/en/20/core/inspection.html>`_
- `Snowflake INFORMATION_SCHEMA <https://docs.snowflake.com/en/sql-reference/info-schema>`_
