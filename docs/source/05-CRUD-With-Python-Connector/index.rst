用 Python Connector 把 03 + 04 一把跑通
==============================================================================


写在前面
------------------------------------------------------------------------------
03 篇我们用 ``snowflake-cli`` 把本地认证搞通了；04 篇我们用 ``snow sql`` 把
warehouse / DB / schema / table / CRUD 一条条手敲过一遍。

这一篇的目的是 **把同样的事在 Python 里做一次**——一个脚本端到端跑完
建仓 → 建库 → 建表 → 插数据 → 查回来 → 清场，**用同一份 .env 凭据**。等你之后
想把 Snowflake 编排到自己的 Python 项目里时，这个脚本就是骨架。


前置条件
------------------------------------------------------------------------------
**1. .env 已经配好**（03 篇做过的）。脚本读这几个环境变量：

- ``SNOWFLAKE_ACCOUNT``
- ``SNOWFLAKE_USER``
- ``SNOWFLAKE_PASSWORD``（PAT 的 ``token_secret``）
- ``SNOWFLAKE_ROLE``（可选，默认 ``ACCOUNTADMIN``）

mise 会在 ``cd`` 进项目时自动把它们加载到 shell。

**2. 装 Snowflake Python Connector**：

.. code-block:: bash

    uv add snowflake-connector-python

或者要保持本项目"学习用，不影响主包依赖"的话，把它放进 ``requirements-dev.txt``
然后 ``mise run inst``。


脚本演示了哪些 Python Connector 的 "套路"
------------------------------------------------------------------------------
不抄具体语法（具体看下面的 ``literalinclude``），只列模式：

- **从环境变量构造连接**——不写 ``config.toml``、不硬编码、不要 RSA 密钥。和 CLI
  走的是同一套 ``.env``，凭据零重复。
- **PAT 当 password 用**——Python Connector 也把 PAT 通过 ``password=`` 参数传
  入，跟 CLI 完全一致。不需要任何 "PAT 专用" 的 connect 参数。
- **``with conn.cursor() as cur:``** —— cursor 用 context manager 管，离开
  ``with`` 块时自动 close。**别忘记**外层还要用 ``try/finally`` 包 connection
  自己的 ``close()``。
- **``cur.execute(sql)`` 跑单条 SQL** —— DDL（``CREATE / DROP``）、单条 DML 都用
  这个。
- **``cur.executemany(sql, rows)`` + ``%s`` 占位符 = 安全的批量 INSERT**——
  *不要* 用 Python f-string / ``%`` / ``.format()`` 拼用户输入到 SQL 里，
  那是 SQL 注入。Snowflake Connector 走的是 ``paramstyle = "pyformat"``，占位符
  写 ``%s``，传 list-of-tuples 进去。
- **直接迭代 cursor 拿结果**——``for row in cur: ...``，每个 ``row`` 是 tuple，
  按列顺序解包就行。不需要 ``fetchall()`` 一次拉全（数据多时省内存）。
- **``DROP DATABASE`` 一条 SQL 清场**——和 04 篇的策略一致，``IF EXISTS`` 保证
  脚本幂等。``WAREHOUSE`` 故意不删，重复跑脚本不用每次都重建。

.. note::

   脚本里所有 ``CREATE`` 都加 ``IF NOT EXISTS``，建表用 ``CREATE OR REPLACE``，
   末尾 ``DROP DATABASE IF EXISTS``。**所以这脚本是幂等的**——重复跑不会报错，
   也不会留下脏状态。这是写 demo / setup 脚本的好习惯。


完整脚本
------------------------------------------------------------------------------
.. literalinclude:: ./snowflake_quickstart.py
   :language: python
   :linenos:
   :caption: docs/source/05-CRUD-With-Python-Connector/snowflake_quickstart.py


怎么跑
------------------------------------------------------------------------------
.. code-block:: bash

    .venv/bin/python docs/source/05-CRUD-With-Python-Connector/snowflake_quickstart.py

预期输出（书名顺序可能略不同）::

    [1/5] warehouse LEARN_WH ready
    [2/5] database LEARN_DB.PLAYGROUND ready
    [3/5] table BOOKS ready
    [4/5] inserted 3 rows
    [5/5] query result:
           id  title                                     rating
            1  Designing Data-Intensive Applications          5
            3  Database Internals                             5
            2  The Pragmatic Programmer                       4
    [cleanup] dropped database LEARN_DB


CLI vs Python Connector，啥时候用哪个
------------------------------------------------------------------------------
.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - 场景
     - ``snow sql`` (CLI)
     - Python Connector
   * - 临时跑一条 SQL 看结果
     - ✅ 最快
     - 杀鸡用牛刀
   * - 一次性脚本 (DDL / 数据迁移)
     - ✅ ``snow sql -f file.sql``
     - ✅ 也可，但要写代码
   * - 复杂条件 / 拿 SQL 结果做 Python 逻辑
     - ❌ 转值出来很别扭
     - ✅ 原生 Python 对象
   * - 集成到应用 / Web 后端 / 定时任务
     - ❌
     - ✅ 唯一选择
   * - 数据科学 / pandas
     - ❌
     - ✅（或者 ``snowflake-snowpark-python``）


参考资料
------------------------------------------------------------------------------
- `Snowflake Python Connector — overview <https://docs.snowflake.com/en/developer-guide/python-connector/python-connector>`_
- `Connecting to Snowflake (Python) <https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-connect>`_
- `Executing queries with the Python connector <https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-example>`_
- `Binding parameters (avoid SQL injection) <https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-api#bindings>`_
