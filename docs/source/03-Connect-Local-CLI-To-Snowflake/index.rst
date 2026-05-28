本地跑通 Snowflake CLI：用 PAT (Programmatic Access Token)
==============================================================================


写在前面
------------------------------------------------------------------------------
这一篇要解决的是：

  **怎么在本地命令行里安全地跑 Snowflake CLI——而且尽量不在我本机多塞一对密钥？**

按本项目的标准（参见 `CLAUDE.md`），CLI 永远通过 ``uvx`` 调用：

.. code-block:: bash

    uvx --from snowflake-cli snow <subcommand> [args...]

最终目标是：把连接参数写到项目根的 ``.env`` 里，让 ``mise`` 在 ``cd`` 进项目时
自动加载，然后任何一条 ``uvx --from snowflake-cli snow ...`` 都能直接连上 Snowflake。


认证方式速览，为啥本项目选 PAT
------------------------------------------------------------------------------
Snowflake CLI 一共支持 4 种认证方式（详见
`Configure Snowflake CLI connections <https://docs.snowflake.com/en/developer-guide/snowflake-cli/connecting/configure-connections>`_）：

- **Password** —— 密码登录。Snowflake 正在限制人类用户用密码，不推荐。
- **External Browser (SSO)** —— CLI 跳浏览器、Snowflake 登录页登录。
  *本项目不用*：在 trial 账号上踩坑明显（容易报 "SAML Identity Provider account
  parameter" 错），而且 SSH/CI 无图形界面环境用不了。所以不展开。
- **Key-Pair (JWT)** —— RSA 公私钥对。功能强，但要在本机管理一对 ``.p8`` /
  ``.pub``。本项目跳过。
- **Programmatic Access Token (PAT)** —— **本项目就用这个**。

**PAT 的好处**：

- 像 GitHub PAT 一样的 **一根字符串**，可命名、可设过期天数（默认 15 天，最长
  365 天）、可单独吊销、可锁定 role。
- 在 CLI 里 **以 password 的位置使用**（填进 ``SNOWFLAKE_PASSWORD``），完全不
  触发 SAML/SSO 那套查询。
- Snowflake 集成了 GitHub secret scanning，PAT 进了公开仓库会自动被禁。
- 单个 user 最多 15 个 PAT，能按用途切开（笔记本、CI、不同项目各一）。

官方文档：`Programmatic access tokens <https://docs.snowflake.com/en/user-guide/programmatic-access-tokens>`_。


Step 1：拿到 Account Identifier 和 Username
------------------------------------------------------------------------------
登录 `Snowsight <https://app.snowflake.com>`_ → 开 Worksheet → 跑：

.. code-block:: sql

    SELECT
        CURRENT_ORGANIZATION_NAME()                                    AS org_name,
        CURRENT_ACCOUNT_NAME()                                         AS account_name,
        CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME()   AS account_identifier,
        CURRENT_USER()                                                 AS username;

记下三个值：

- ``account_identifier`` —— ``<orgname>-<accountname>`` 拼起来的那串，等下要填到
  ``SNOWFLAKE_ACCOUNT``。Snowflake 推荐使用这种新版格式。
- ``username`` —— **以这个返回值为准**，trial 账号默认是 ``ADMIN``，但不一定，别
  靠猜。
- 后续 ``ALTER USER`` 语句里的 ``<YOUR_USERNAME>`` 都用这个值替换。


Step 2：看懂 .env.example，准备写 .env
------------------------------------------------------------------------------
项目根有一份模板 ``.env.example``：

.. code-block:: bash
    :caption: .env.example

    # Snowflake Credentials
    SNOWFLAKE_ACCOUNT="MYORG-MYACCOUNT"
    SNOWFLAKE_USER="YOUR_USERNAME"
    SNOWFLAKE_PASSWORD="YOUR_PAT_TOKEN"

    # 默认资源
    SNOWFLAKE_ROLE="ACCOUNTADMIN"
    SNOWFLAKE_WAREHOUSE="LEARN_WH"
    SNOWFLAKE_DATABASE="LEARN_DB"
    SNOWFLAKE_SCHEMA="PLAYGROUND"

逐个字段说明：

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 变量
     - 干啥的
   * - ``SNOWFLAKE_ACCOUNT``
     - Step 1 拿到的 ``account_identifier``，形如 ``KNHJBXZ-HJ83313``。
   * - ``SNOWFLAKE_USER``
     - Step 1 拿到的 ``username``，trial 通常是 ``ADMIN``。
   * - ``SNOWFLAKE_PASSWORD``
     - **PAT 的 token_secret**（一长串），不是真密码。Step 3 生成。
   * - ``SNOWFLAKE_ROLE``
     - CLI 会话默认 role。学习阶段填 ``ACCOUNTADMIN`` 即可。
   * - ``SNOWFLAKE_WAREHOUSE``
     - 默认 warehouse。上一篇建过的 ``LEARN_WH``；还没建就先用 trial 自带的
       ``COMPUTE_WH``。
   * - ``SNOWFLAKE_DATABASE`` / ``SNOWFLAKE_SCHEMA``
     - 默认 DB / Schema。**还没创建之前 CLI 连上会报 "Object does not exist"**，
       属于正常现象——下一篇会建 ``LEARN_DB`` / ``PLAYGROUND``。


Step 3：生成 PAT
------------------------------------------------------------------------------
两种方式任选一种。

3.1 方式一：Snowsight UI（推荐第一次用）
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. 左下角账号头像 → **My profile**
2. 滚到 **Programmatic access tokens** → **Generate new token**
3. 填：

   - **Name**：起个有意义的名字，比如 ``learn-laptop-cli``
   - **Expires in**：学习用 90 天比较合适
   - **Role restriction**（可选）：留空就跟随用户当前 role

4. 点 **Generate** → **立刻复制弹出来的那串 token_secret**。**关闭窗口后再也看不到了**。

3.2 方式二：SQL
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sql

    USE ROLE ACCOUNTADMIN;

    ALTER USER ADMIN
        ADD PROGRAMMATIC ACCESS TOKEN learn_laptop_cli
        DAYS_TO_EXPIRY = 90
        COMMENT        = 'snowflake-cli on personal laptop';

返回结果里有一个 ``token_secret`` 字段——**只显示这一次，立刻复制**。

3.3 后续管理 PAT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sql

    -- 列出当前用户的所有 PAT
    SHOW USER PROGRAMMATIC ACCESS TOKENS FOR USER ADMIN;

    -- 轮换（旧的立即失效、返回新 token_secret）
    ALTER USER ADMIN ROTATE PROGRAMMATIC ACCESS TOKEN learn_laptop_cli;

    -- 临时禁用
    ALTER USER ADMIN MODIFY PROGRAMMATIC ACCESS TOKEN learn_laptop_cli SET DISABLED = TRUE;

    -- 吊销
    ALTER USER ADMIN REMOVE PROGRAMMATIC ACCESS TOKEN learn_laptop_cli;


Step 4：给 user 挂 Network Policy（**PAT 必需**）
------------------------------------------------------------------------------
**官方规则**：user 必须挂着一个 network policy 才能用 PAT 登录。Trial 账号默认
没有任何 policy，所以你 **第一次用 PAT 一定会卡** "Network policy is required"
这个错。

最简单的做法：建一个允许所有 IP 的占位 policy，挂到 user 上：

.. code-block:: sql

    USE ROLE ACCOUNTADMIN;

    -- 1) 建一个允许所有 IP 的占位 policy
    CREATE NETWORK POLICY IF NOT EXISTS PAT_ALLOW_ALL
        ALLOWED_IP_LIST = ('0.0.0.0/0');

    -- 2) 挂到当前 user 上
    ALTER USER ADMIN SET NETWORK_POLICY = PAT_ALLOW_ALL;

.. note::

   **关于安全性**：``0.0.0.0/0`` 允许任何 IP 用这个 PAT 来登。考虑到
   PAT 本身就是 secret，泄漏才是真正的攻击向量（不是 IP），而且 PAT 有过期
   时间和可吊销，trial 账号也没真实数据，**学习阶段够用**。等以后要保护真实
   数据时，把 ``ALLOWED_IP_LIST`` 换成自己的出口 IP（用 ``curl -s ifconfig.me``
   查）。

**怎么验证 network policy 挂上了？**

不是 ``DESC USER``！user 层级的 ``NETWORK_POLICY`` 是 **parameter** 不是
property，``DESC USER`` 的输出里看不到它。正确查法：

.. code-block:: sql

    SHOW PARAMETERS LIKE 'network_policy' IN USER ADMIN;

应该能看到 ``value = PAT_ALLOW_ALL``。


Step 5：写 .env，让 mise 加载
------------------------------------------------------------------------------
照 ``.env.example`` 抄一份 ``.env`` 到项目根，填上真值：

.. code-block:: bash
    :caption: .env

    SNOWFLAKE_ACCOUNT="KNHJBXZ-HJ83313"
    SNOWFLAKE_USER="ADMIN"
    SNOWFLAKE_PASSWORD="<<刚才复制的 PAT token_secret>>"

    SNOWFLAKE_ROLE="ACCOUNTADMIN"
    SNOWFLAKE_WAREHOUSE="LEARN_WH"
    SNOWFLAKE_DATABASE="LEARN_DB"
    SNOWFLAKE_SCHEMA="PLAYGROUND"

.. important::

   - ``.env`` **必须在 ``.gitignore`` 里**，不能提交。
   - 不要设 ``SNOWFLAKE_AUTHENTICATOR``——PAT 走默认 authenticator 即可，设了
     ``externalbrowser`` 就会去走 SAML 路径，必报错。

``mise.toml`` 里要让 mise 自动加载 ``.env``：

.. code-block:: toml
    :caption: mise.toml

    [env]
    _.file = ".env"

确认变量加载成功（只打印变量**名字**，不打印值，避免 PAT 露出来）：

.. code-block:: bash

    env | grep -o '^SNOWFLAKE_[A-Z_]*=' | sort


Step 6：验证连接
------------------------------------------------------------------------------
``snow connection test`` 这个子命令默认要去 config.toml 找一个名叫 ``default``
的连接，本项目走纯环境变量、不维护 config.toml，所以一定要加 ``-x``
（``--temporary-connection``）让 CLI 直接从环境变量起一个临时连接：

.. code-block:: bash

    uvx --from snowflake-cli snow connection test -x

成功输出形如::

    Host:        KNHJBXZ-HJ83313.snowflakecomputing.com
    Account:     KNHJBXZ-HJ83313
    User:        ADMIN
    Role:        ACCOUNTADMIN
    Warehouse:   LEARN_WH
    Database:    LEARN_DB
    Schema:      PLAYGROUND
    Status:      OK

跑一条真实 SQL：

.. code-block:: bash

    uvx --from snowflake-cli snow sql -q "SELECT CURRENT_VERSION(), CURRENT_USER(), CURRENT_ROLE();" -x


故障排查（按错误信息查）
------------------------------------------------------------------------------
.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - 错误信息
     - 根因 + 解法
   * - ``Connection default is not configured``
     - 漏了 ``-x``。所有 ``snow ...`` 命令在本项目都要加 ``-x``。
   * - ``There was an error related to the SAML Identity Provider account parameter``
     - shell 里残留了 ``SNOWFLAKE_AUTHENTICATOR=externalbrowser``（之前试过
       browser 方案的话）。``.env`` 改了但当前 shell 里旧变量还粘着。修法：
       ``unset SNOWFLAKE_AUTHENTICATOR`` 或者 ``exec $SHELL`` 开新 shell 让
       mise 重新加载。
   * - ``Network policy is required``
     - PAT 必须配 network policy。回到 Step 4 跑 ``CREATE NETWORK POLICY`` +
       ``ALTER USER ... SET NETWORK_POLICY``。
   * - ``Could not use database "LEARN_DB". Object does not exist``
     - **PAT 认证已经成功**！只是 ``.env`` 里 ``SNOWFLAKE_DATABASE=LEARN_DB``
       而你还没建这个 DB。下一篇会建。
   * - ``Programmatic access token is invalid``
     - PAT 过期、被禁用或被吊销。Snowsight 里 ``SHOW USER PROGRAMMATIC
       ACCESS TOKENS FOR USER ADMIN`` 查状态，要么 ``ROTATE`` 要么重建。
   * - ``IP ... is not allowed to access Snowflake``
     - network policy 没包含当前 IP。学习阶段最省事是 ``ALLOWED_IP_LIST =
       ('0.0.0.0/0')``。


到这里就完了，接下来呢？
------------------------------------------------------------------------------
本地 CLI 已经能通过 PAT 连上 Snowflake——下一篇会用 ``uvx --from snowflake-cli
snow sql`` 来建 ``LEARN_WH`` / ``LEARN_DB`` / ``PLAYGROUND`` / 第一张表，把上一
篇用 Snowsight 跑的步骤搬到 CLI 上重做一遍。


参考资料
------------------------------------------------------------------------------
- `Configure Snowflake CLI connections <https://docs.snowflake.com/en/developer-guide/snowflake-cli/connecting/configure-connections>`_
- `Programmatic access tokens (PATs) <https://docs.snowflake.com/en/user-guide/programmatic-access-tokens>`_
- `Network policies <https://docs.snowflake.com/en/user-guide/network-policies>`_
- `Snowflake account identifier 格式 <https://docs.snowflake.com/en/user-guide/admin-account-identifier>`_
- `mise env files <https://mise.jdx.dev/configuration.html#env-file>`_
