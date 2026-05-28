个人开发者的 Snowflake 极省钱启动指南
==============================================================================


写在前面
------------------------------------------------------------------------------
作为一个个人开发者，我想 **花最少的钱、甚至零成本**，把 Snowflake 跑起来，做一些
学习、Demo、技术验证。这篇文档把我搞清楚的事情记录下来：Snowflake 是怎么收费的、
有哪些"省钱开关"、怎么用最小代价创建第一张表跑一条查询。

核心结论先放在这里：

- 注册 **Free Trial**（30 天 + 一笔免费 credits 余额，无需信用卡），选 **Standard
  Edition**，这是最便宜的版本。
- 计算资源用 **X-Small 虚拟仓库**（最小规格，1 credit/小时），并开启
  **auto-suspend** + **auto-resume**，让仓库在没有查询时自动停机，按秒计费、不查不
  花钱。
- 存储几乎可以忽略：按 TB/月 收费，做学习实验时数据量可能是几 MB 到几 GB，一个月
  花不了几分钱。
- 数据 **入站（ingress）免费**，跨区域/跨云的 **出站（egress）** 才收钱，学习场
  景几乎用不上。
- 真正烧钱的是 **一直开着大仓库** 或者用 **Serverless 重型功能**（如
  Search Optimization、Snowpipe 大量数据连续摄取），新手只要避开就好。

下文按"先搞懂账单 → 再搞懂资源 → 再动手跑表"的顺序展开。


计费模型：Snowflake 的钱到底花在哪里
------------------------------------------------------------------------------
Snowflake 的总账单由 **三块** 组成（参考官方文档
`Understanding overall cost <https://docs.snowflake.com/en/user-guide/cost-understanding-overall>`_）：

1. **Compute（计算）** —— 跑查询、加载数据、做 DML 的算力。**这是最大头**。
2. **Storage（存储）** —— 表数据、Time Travel、Fail-safe 的存储费。
3. **Data Transfer（数据传输）** —— 跨区域/跨云的 egress 流量费。

计算又分三种：

- **Virtual Warehouse（虚拟仓库）** —— 你显式创建、显式使用的计算资源。按
  **credit** 计费，**按秒计费、起步 60 秒**。
- **Serverless Compute** —— 由 Snowflake 自动伸缩的托管算力，用在
  Snowpipe、Search Optimization、Materialized View 维护、Serverless Tasks
  等功能上。**按 compute-hour 计费**，不同功能 credit 单价不同。
- **Cloud Services** —— 元数据/身份认证等。**只有当 Cloud Services 用量超过当天
  Warehouse 用量的 10% 时才收费**，正常学习场景基本是免费的。

简单算账（来自官方文档示例）：一个 Standard Edition 组织一个月花了 $10,423，
其中 $8,928 是 compute（按 $2/credit 算），$1,495 是 storage（按 $23/TB 算）。
**所以对个人开发者来说，把 credit 用量压到接近 0 是省钱的关键。**


免费额度：Free Trial 能撑多久
------------------------------------------------------------------------------
官方文档
`Trial accounts <https://docs.snowflake.com/en/user-guide/admin-trial-account>`_
说明的几点关键事实：

- 注册只需要一个 **邮箱**，**不需要信用卡**。
- 试用期是 **30 天 或 用完免费余额（whichever comes first）**。
- 注册时可以选择 **云厂商（AWS / Azure / GCP）**、**Region** 和 **Edition**。
- 试用期结束后账号会被 **suspended**，可以登录但不能跑查询；想继续用就要绑卡转
  正式账户。

社区里普遍提到的 "$400 free credit" 是 Snowflake 官网在
`signup 页 <https://signup.snowflake.com/>`_ 长期宣传的数字（以注册页实时显示
为准）。对于一个 X-Small 仓库（1 credit/小时）而言，$400 即使全用在计算上也是
几百小时的算力，**对学习场景绰绰有余**。

**强烈建议**：注册时选 **Standard Edition**——它是最便宜的入门版，credit 单价
最低，所有学习场景需要的功能都覆盖了。


Edition 怎么选：选 Standard 就对了
------------------------------------------------------------------------------
官方文档
`Snowflake editions <https://docs.snowflake.com/en/user-guide/intro-editions>`_
里 Snowflake 提供四个版本：

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Edition
     - 适合谁
   * - **Standard**
     - **个人学习、Demo、入门首选**。包含核心 SQL、虚拟仓库、数据加载、基础安全。
   * - Enterprise
     - 大企业，加了多集群仓库、最长 90 天 Time Travel、Materialized View 等。
   * - Business Critical
     - 受合规约束的场景（HIPAA/HITRUST），灾备增强。
   * - Virtual Private Snowflake (VPS)
     - 完全隔离的物理资源，最贵。

**Edition 越高，每个 credit 的美元单价就越贵**（同一个 X-Small 仓库，Enterprise
比 Standard 贵）。学习场景没有任何理由用 Standard 以上的版本。

另外还有两种计费形态：

- **On Demand**：按用多少付多少，无承诺，注册即可用。**新手就用这个**。
- **Capacity**：预付容量，单价更便宜，但要走采购合同。**和个人开发者无关**。


Virtual Warehouse：把这个开关玩明白，省 90% 的钱
------------------------------------------------------------------------------
Virtual Warehouse 是 Snowflake 的计算单元。**只要你跑 SQL，就必须有一个仓库在
运行**。它的关键属性是 **大小（size）**——参考官方文档
`Virtual warehouses overview <https://docs.snowflake.com/en/user-guide/warehouses-overview>`_：

.. list-table:: 仓库规格 vs Credit 消耗（Gen1，每小时）
   :header-rows: 1
   :widths: 30 30 40

   * - 规格
     - Credits/小时
     - 用途
   * - **X-Small**
     - **1**
     - **个人学习、小数据集、入门首选**
   * - Small
     - 2
     - 中等数据
   * - Medium
     - 4
     - 较大数据
   * - Large
     - 8
     - 生产负载
   * - X-Large
     - 16
     - 大型生产
   * - 2X-Large
     - 32
     - …
   * - 3X-Large
     - 64
     - …
   * - 4X-Large
     - 128
     - …
   * - 5X-Large
     - 256
     - …
   * - 6X-Large
     - 512
     - 顶配

**关键规律**：每升一档，**算力翻倍、价格也翻倍**。
**对个人学习来说，X-Small 已经足够强**——它对应数 GB 数据集的秒级查询是没问题的。

省钱的真正杀手锏：**Per-second billing + auto-suspend + auto-resume**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

官方计费规则（来自
`Understanding compute cost <https://docs.snowflake.com/en/user-guide/cost-understanding-compute>`_）：

- **启动/恢复时按 1 分钟最小计费**（即使你只跑了 5 秒钟，也算 1 分钟）。
- **1 分钟之后切换到按秒计费**，仓库持续运行多久就算多久。
- **挂起后再启动重新走 1 分钟最小值**——所以频繁手动启停反而费钱。

正确姿势：让 Snowflake **自动** 启停：

- **AUTO_SUSPEND**：仓库在指定秒数内没活动就自动挂起。**学习用建议设 60 秒**
  （就是空闲 1 分钟自动停）。
- **AUTO_RESUME**：有 SQL 来了自动恢复，使用者无感知。

这样做的效果：你只在 **真正跑查询的时候** 才烧 credit。一个 X-Small 仓库跑 10 秒
查询，账单大约就是 1 分钟 × 1 credit/小时 ≈ **0.0167 credit ≈ 几美分**。

.. note::

   开个 X-Small + 60 秒 auto-suspend 的仓库，一周不跑任何查询，账单基本是 0。
   这就是 "serverless 体验" 的本质——**Snowflake 替你把闲置资源关掉了**。


Serverless 是另一回事：别和 "auto-suspend" 搞混
------------------------------------------------------------------------------
在 Snowflake 的语境里，**Serverless** 不是指 "我的 warehouse 自动停"，而是指
**一组完全由 Snowflake 托管、不需要你创建仓库** 的功能：

- **Snowpipe / Snowpipe Streaming** —— 自动数据摄取。
- **Serverless Tasks** —— 不绑定仓库的调度任务。
- **Search Optimization** —— 加速点查的后台索引维护。
- **Materialized View 自动刷新**
- **Automatic Clustering**
- **Replication / Failover**

这些功能 **不消耗你的 warehouse credit**，而是按 "serverless compute-hours" 单独
计费，**每种功能的 credit 单价不同**（且通常比同等 warehouse 贵一些，因为
Snowflake 替你做了运维）。

**对个人学习的建议**：

- ✅ 主力计算用 **X-Small warehouse + auto-suspend**——这才是最便宜的 "serverless
  体验"。
- ⚠️ 不要随便开 Snowpipe 持续摄取、Search Optimization、Automatic Clustering
  这些 serverless 功能——它们 **在后台一直跑**，账单可能悄悄涨上来。


Storage：几乎不用考虑
------------------------------------------------------------------------------
存储计费规则（来自
`Understanding storage cost <https://docs.snowflake.com/en/user-guide/cost-understanding-data-storage>`_）：

- **按 TB/月 收费**，**按每日平均字节** 计算。
- On Demand 价格大约 **$23/TB/月**（具体看 region）。
- 包含：表数据、stage 文件、Time Travel、Fail-safe、Clone。
- **数据自动压缩**，所以原始 CSV 1GB 进去通常只占几百 MB。

学习场景的数据量典型是 **几 MB ~ 几 GB**，**一个月存储费用不到 1 美元**，
基本可以忽略。

如果想进一步压低存储成本，可以把测试表建成 **TRANSIENT TABLE** —— 没有 Fail-safe
period，最多 1 天的 Time Travel，存储成本上限更低。


数据传输：学习场景免费
------------------------------------------------------------------------------
- **Ingress（入站）：完全免费**——把数据传到 Snowflake 不要钱。
- **Egress（出站）：只在跨 region 或跨云时按 TB 收费**。

**个人学习时，你不会触发 egress 费用**——把数据传进来跑查询而已。


动手实践：最小可运行配置
------------------------------------------------------------------------------
下面是一个 **零成本起步** 的完整脚本。注册完账号、登录 Snowsight（Snowflake 的
Web UI）后，新建一个 Worksheet 粘进去执行。

Step 1：创建一个最小、最省钱的仓库
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sql

    -- 创建一个 X-Small 仓库，空闲 60 秒自动挂起，自动恢复
    CREATE WAREHOUSE IF NOT EXISTS LEARN_WH
        WAREHOUSE_SIZE = 'XSMALL'      -- 1 credit/小时，最小规格
        AUTO_SUSPEND   = 60            -- 空闲 60 秒自动停（最小可设 60）
        AUTO_RESUME    = TRUE          -- 有查询自动恢复
        INITIALLY_SUSPENDED = TRUE;    -- 创建时就处于停机状态，不烧钱

    USE WAREHOUSE LEARN_WH;

Step 2：创建 Database → Schema → Table
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Snowflake 的对象层级是 **Database → Schema → Table**（参考
`Databases, Tables and Views Overview <https://docs.snowflake.com/en/guides-overview-db>`_）。

.. code-block:: sql

    -- 1) 数据库
    CREATE DATABASE IF NOT EXISTS LEARN_DB;
    USE DATABASE LEARN_DB;

    -- 2) Schema
    CREATE SCHEMA IF NOT EXISTS PLAYGROUND;
    USE SCHEMA PLAYGROUND;

    -- 3) 表（用 TRANSIENT 进一步降低存储成本，学习用足够）
    CREATE OR REPLACE TRANSIENT TABLE HELLO_SNOWFLAKE (
        id          INT,
        name        STRING,
        created_at  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
    );

Step 3：插点数据，跑个查询
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sql

    INSERT INTO HELLO_SNOWFLAKE (id, name) VALUES
        (1, 'Alice'),
        (2, 'Bob'),
        (3, 'Charlie');

    SELECT * FROM HELLO_SNOWFLAKE;

跑完后什么都不用做。60 秒后仓库自动挂起，账单就停了。下次再写 SQL 时它会自动恢复。

Step 4：随时查询你花了多少钱
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sql

    -- 看 warehouse 的 credit 消耗（最近 7 天）
    SELECT
        warehouse_name,
        SUM(credits_used) AS total_credits,
        SUM(credits_used_compute) AS compute_credits,
        SUM(credits_used_cloud_services) AS cloud_services_credits
    FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
    WHERE start_time >= DATEADD(day, -7, CURRENT_TIMESTAMP())
    GROUP BY warehouse_name;

    -- 看存储用量
    SELECT *
    FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
    ORDER BY usage_date DESC
    LIMIT 7;


省钱清单（Cheat Sheet）
------------------------------------------------------------------------------
.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - 该做的
     - 该避免的
   * - ✅ 选 Standard Edition + On Demand
     - ❌ 选 Enterprise 及以上
   * - ✅ 用 X-Small 仓库（1 credit/小时）
     - ❌ 创建 Small 或更大的仓库
   * - ✅ AUTO_SUSPEND = 60，AUTO_RESUME = TRUE
     - ❌ 把仓库设成永不挂起，或手动开着不关
   * - ✅ INITIALLY_SUSPENDED = TRUE
     - ❌ 创建即启动
   * - ✅ 学习表用 TRANSIENT TABLE
     - ❌ 用 permanent table 还开长 Time Travel
   * - ✅ 只用 warehouse 做计算
     - ❌ 顺手打开 Snowpipe / Search Optimization / Auto-Clustering
   * - ✅ 数据 ingress（往里传）随便用
     - ❌ 频繁跨 region/跨云 egress
   * - ✅ 定期查 ``WAREHOUSE_METERING_HISTORY`` 看账
     - ❌ 试用期结束才发现 credit 用光


参考资料
------------------------------------------------------------------------------
- `Cost & billing 总入口 <https://docs.snowflake.com/en/guides-overview-cost>`_
- `Understanding overall cost <https://docs.snowflake.com/en/user-guide/cost-understanding-overall>`_
- `Understanding compute cost <https://docs.snowflake.com/en/user-guide/cost-understanding-compute>`_
- `Understanding storage cost <https://docs.snowflake.com/en/user-guide/cost-understanding-data-storage>`_
- `Virtual warehouses overview <https://docs.snowflake.com/en/user-guide/warehouses-overview>`_
- `Snowflake editions <https://docs.snowflake.com/en/user-guide/intro-editions>`_
- `Trial accounts <https://docs.snowflake.com/en/user-guide/admin-trial-account>`_
- `Databases, Tables and Views <https://docs.snowflake.com/en/guides-overview-db>`_
- `Snowflake 官方 pricing 页 <https://www.snowflake.com/pricing/>`_
- `Snowflake Service Consumption Table (PDF) <https://www.snowflake.com/legal-files/CreditConsumptionTable.pdf>`_
