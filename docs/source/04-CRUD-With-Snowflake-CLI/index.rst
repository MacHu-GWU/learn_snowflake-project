用 Snowflake CLI 跑一遍 CRUD，最后一键清场
==============================================================================


写在前面
------------------------------------------------------------------------------
上一篇我们把 PAT 配通了，现在所有的 ``uvx --from snowflake-cli snow sql ...`` 都能
直接连上 Snowflake。这一篇就 **每一步一条命令、每一步看一眼输出**，把数据库到表
到 CRUD 全跑一遍，最后一条命令把所有东西干净地删掉。

整个 walkthrough 用一张极简的 ``BOOKS`` 表（5 列）作为靶子：

============  ======================  ==========================
字段           类型                    含义
============  ======================  ==========================
``id``        INT (AUTOINCREMENT)     主键，自增
``title``     STRING NOT NULL         书名
``rating``    INT                     1-5 分
``read_at``   DATE                    读完日期
``notes``     STRING                  备注
============  ======================  ==========================

每条命令的统一模板：

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "<SQL>"

- ``-x`` ：临时连接（从 ``.env`` 里的环境变量起，**不走 config.toml**）。
- ``-q``：把后面的字符串当作 SQL 跑。SQL 字符串用双引号包，里面的字面值用单引号。

.. note::

   注意一个小坑：上一篇 ``.env`` 里已经写了 ``SNOWFLAKE_DATABASE="LEARN_DB"`` /
   ``SNOWFLAKE_SCHEMA="PLAYGROUND"`` 作为默认。这意味着在 ``LEARN_DB`` 还没建出
   来之前，**每条命令会在最开始尝试 USE LEARN_DB.PLAYGROUND 然后失败**，CLI 会
   报 ``Could not use database "LEARN_DB". Object does not exist``——但 **后面的
   SQL 还是会照样执行**。所以 Step 1～3（建 DB 之前的命令）会看到这个 warning，
   忽略即可。从 Step 4 开始就不会再出现了。


预检：CLI 还能连上吗
------------------------------------------------------------------------------
.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "SELECT CURRENT_USER(), CURRENT_ROLE();"

能正常返回你的 username 和 role 就 OK，继续。报错就先回 03 篇修。


Step 1：建一个最便宜的 Warehouse
------------------------------------------------------------------------------
**目标**：用 ``XSMALL`` + ``AUTO_SUSPEND = 60`` + ``INITIALLY_SUSPENDED = TRUE``
建一个不烧 credit 的 warehouse。

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "
    CREATE WAREHOUSE IF NOT EXISTS LEARN_WH
        WAREHOUSE_SIZE = 'XSMALL'
        AUTO_SUSPEND   = 60
        AUTO_RESUME    = TRUE
        INITIALLY_SUSPENDED = TRUE;
    "

确认一下：

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "SHOW WAREHOUSES LIKE 'LEARN_WH';"

应该能看到一行，``state`` 是 ``SUSPENDED``。


Step 2：建 Database
------------------------------------------------------------------------------
.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "CREATE DATABASE IF NOT EXISTS LEARN_DB;"


Step 3：建 Schema
------------------------------------------------------------------------------
.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "CREATE SCHEMA IF NOT EXISTS LEARN_DB.PLAYGROUND;"

从这一步开始，``USE LEARN_DB.PLAYGROUND`` 的 warning 就消失了。


Step 4：建表
------------------------------------------------------------------------------
**目标**：建一张 ``TRANSIENT TABLE`` ——没有 Fail-safe period，存储成本上限低，
适合学习。``id`` 用 ``AUTOINCREMENT`` 自动生成，不用手动给。

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "
    CREATE OR REPLACE TRANSIENT TABLE LEARN_DB.PLAYGROUND.BOOKS (
        id        INT AUTOINCREMENT START 1 INCREMENT 1,
        title     STRING NOT NULL,
        rating    INT,
        read_at   DATE,
        notes     STRING
    );
    "

看一眼表结构：

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "DESC TABLE LEARN_DB.PLAYGROUND.BOOKS;"


Step 5：INSERT（C — Create）
------------------------------------------------------------------------------
插 4 行数据。``id`` 留给 ``AUTOINCREMENT`` 自动生成。

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "
    INSERT INTO LEARN_DB.PLAYGROUND.BOOKS (title, rating, read_at, notes) VALUES
        ('Designing Data-Intensive Applications', 5, '2026-04-12', 'Must read'),
        ('The Pragmatic Programmer',              4, '2026-05-03', 'Classic'),
        ('Database Internals',                    5, '2026-05-20', 'Deep dive'),
        ('Snowflake The Definitive Guide',        4, '2026-05-25', NULL);
    "

返回行里会显示 ``number of rows inserted = 4``。


Step 6：SELECT（R — Read）
------------------------------------------------------------------------------
**全表扫一眼**：

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "SELECT * FROM LEARN_DB.PLAYGROUND.BOOKS ORDER BY id;"

应该能看到 4 行，``id`` 是 1～4。

**带过滤条件**——只看评分 = 5 的：

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "
    SELECT title, rating, read_at
      FROM LEARN_DB.PLAYGROUND.BOOKS
     WHERE rating = 5
     ORDER BY read_at;
    "

**聚合**——按 rating 分组数一下：

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "
    SELECT rating, COUNT(*) AS n
      FROM LEARN_DB.PLAYGROUND.BOOKS
     GROUP BY rating
     ORDER BY rating DESC;
    "


Step 7：UPDATE（U — Update）
------------------------------------------------------------------------------
**目标**：把 ``The Pragmatic Programmer`` 的 ``notes`` 改了。

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "
    UPDATE LEARN_DB.PLAYGROUND.BOOKS
       SET notes = 'Re-read in 2026, still great'
     WHERE title = 'The Pragmatic Programmer';
    "

返回 ``number of rows updated = 1``。

确认改成功：

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "
    SELECT id, title, notes
      FROM LEARN_DB.PLAYGROUND.BOOKS
     WHERE title = 'The Pragmatic Programmer';
    "


Step 8：DELETE（D — Delete）
------------------------------------------------------------------------------
**目标**：删掉所有 ``rating < 5`` 的书。

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "
    DELETE FROM LEARN_DB.PLAYGROUND.BOOKS
     WHERE rating < 5;
    "

返回 ``number of rows deleted = 2``。

确认只剩 2 行：

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "SELECT COUNT(*) AS remaining FROM LEARN_DB.PLAYGROUND.BOOKS;"


Step 9：体验一下 Snowflake 独有的 Time Travel
------------------------------------------------------------------------------
**这是 Snowflake 真正 "酷" 的地方**：你刚才删掉的 2 行 **没有真的消失**，
Snowflake 默认保留过去 1 天的所有数据版本。你可以指定一个偏移（比如
"60 秒以前"）去看那时候的表是什么样。

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "
    SELECT id, title, rating
      FROM LEARN_DB.PLAYGROUND.BOOKS AT(OFFSET => -60)
     ORDER BY id;
    "

应该能看到 **4 行**（删除前的状态）——尽管当前表只有 2 行。

.. note::

   ``AT(OFFSET => -60)`` 是 "60 秒前"。如果你 DELETE 之后过了不止 60 秒，
   把这个数字调大，比如 ``-300`` (5 分钟前)。

**反过来：用 Time Travel 恢复刚才删掉的行**——一行 SQL 搞定：

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "
    INSERT INTO LEARN_DB.PLAYGROUND.BOOKS (id, title, rating, read_at, notes)
    SELECT id, title, rating, read_at, notes
      FROM LEARN_DB.PLAYGROUND.BOOKS AT(OFFSET => -120)
     WHERE rating < 5;
    "

再查一遍，4 行回来了：

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "SELECT * FROM LEARN_DB.PLAYGROUND.BOOKS ORDER BY id;"

.. note::

   这个能力叫 **Time Travel**。``TRANSIENT TABLE`` 默认 1 天，
   ``PERMANENT TABLE`` 在 Standard Edition 也是 1 天，
   Enterprise Edition 可以最长 90 天。误删大表救命用。


Step 10：清场（一条命令删干净）
------------------------------------------------------------------------------
``DROP DATABASE`` 默认级联（cascade）——删 DB 时它下面的所有 schema、所有表、
所有数据全部一起干掉。**一条命令清空所有学习痕迹**：

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "DROP DATABASE IF EXISTS LEARN_DB;"

如果你不再用 ``LEARN_WH``，也一起删掉（不删也不会烧钱，因为它已经
``AUTO_SUSPEND``）：

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "DROP WAREHOUSE IF EXISTS LEARN_WH;"

确认一下：

.. code-block:: bash

    uvx --from snowflake-cli snow sql -x -q "SHOW DATABASES LIKE 'LEARN_DB';"
    uvx --from snowflake-cli snow sql -x -q "SHOW WAREHOUSES LIKE 'LEARN_WH';"

两条都应该返回 0 行。

.. warning::

   ``DROP DATABASE`` 之后的 1 天内你还能用 ``UNDROP DATABASE LEARN_DB`` 把它整个
   恢复回来（Time Travel 也保护 drop 操作）。1 天后才会真正从存储里消失。学习
   场景无所谓，生产环境要心里有数。


小结
------------------------------------------------------------------------------
你刚刚用 **纯 CLI** 完成了：

#. 建 warehouse / database / schema / table
#. INSERT 4 行 → SELECT / WHERE / GROUP BY
#. UPDATE 一行 → DELETE 两行
#. Time Travel 看 60 秒前的快照 → 一行 SQL 把误删的数据捞回来
#. 一条 ``DROP DATABASE`` 干净清场

整套流程烧的 credit 大概是 ``LEARN_WH`` 跑了几次查询，每次几秒——保守估
算 **不到 1 美分**。这就是 "X-Small + auto-suspend + transient table" 的威力。


参考资料
------------------------------------------------------------------------------
- `CREATE WAREHOUSE <https://docs.snowflake.com/en/sql-reference/sql/create-warehouse>`_
- `CREATE TABLE <https://docs.snowflake.com/en/sql-reference/sql/create-table>`_
- `Time Travel (AT / BEFORE) <https://docs.snowflake.com/en/sql-reference/constructs/at-before>`_
- `DROP DATABASE / UNDROP <https://docs.snowflake.com/en/sql-reference/sql/drop-database>`_
- `Snowflake CLI: snow sql <https://docs.snowflake.com/en/developer-guide/snowflake-cli/sql/execute-sql>`_
