本地跑通 Snowflake CLI：用 PAT / SSO，不再管 RSA 密钥
==============================================================================


写在前面
------------------------------------------------------------------------------
上一篇我们建好了 ``LEARN_WH`` / ``LEARN_DB`` / 跑通了第一张表。这一篇要解决的是：

  **怎么在本地命令行里安全地跑 Snowflake CLI——而且尽量不在我本机多塞一对密钥？**

按本项目的标准（参见 `CLAUDE.md`），CLI 永远通过 ``uvx`` 调用：

.. code-block:: bash

    uvx --from snowflake-cli snow <subcommand> [args...]

最终目标是：把连接参数写到 ``.env`` 里，让 ``mise`` 在进入项目目录时自动加载，
然后任何一条 ``uvx --from snowflake-cli snow sql -q "..."`` 都能直接连上。

**核心结论先放在这里**：

Snowflake 一共支持 4 种 CLI 认证方式（参见
`Configure Snowflake CLI connections <https://docs.snowflake.com/en/developer-guide/snowflake-cli/connecting/configure-connections>`_），
对个人开发者来说真正值得用的是 **前两种**：

.. list-table::
   :header-rows: 1
   :widths: 22 38 25 15

   * - 方式
     - 本质
     - 本地 secret
     - 推荐度
   * - **External Browser (SSO)**
     - CLI 跳浏览器，浏览器登录后回写 token
     - **无**
     - 互动场景首选
   * - **PAT** (Programmatic Access Token)
     - 像 GitHub PAT 一样的字符串
     - 一个 token 字符串
     - 自动化/headless 首选
   * - Key-Pair (JWT)
     - RSA 公私钥
     - 一对 ``.p8`` / ``.pub``
     - CI/CD 才值得搞
   * - Password
     - 用户名 + 密码
     - 密码
     - 不要用

**推荐策略**：

- 笔记本上 **手动跑 CLI** → 用 ``EXTERNALBROWSER``，**本地一个 secret 都不用存**。
- 笔记本上 **要让脚本/Cron 跑**、或者偶尔在没有图形界面的机器上跑 → 用 **PAT**，
  一个字符串扔进 ``.env`` 就完事。
- 这两种都不需要你管 RSA 密钥。


方案 A：External Browser（零 secret，最推荐互动用）
------------------------------------------------------------------------------
原理：CLI 不直接拿凭据，而是 **打开你默认浏览器跳到 Snowflake 登录页**——你在
浏览器里完成登录（这一步可能用你早就缓存好的 cookie，秒过）后，Snowflake 把
session token 回写给 CLI。整个过程 **本地不落任何 secret**，密码也不会经过 CLI。

A.1 配 ``.env``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

在项目根新建 ``.env``（注意 **必须在 ``.gitignore`` 里**）：

.. code-block:: bash
    :caption: .env

    SNOWFLAKE_ACCOUNT=myorg-myaccount       # Step "拿账号标识符" 里查到的那个
    SNOWFLAKE_USER=YOUR_USERNAME            # 你的 Snowflake 用户名
    SNOWFLAKE_AUTHENTICATOR=externalbrowser

    # 默认资源（可选，但建议明确写出来）
    SNOWFLAKE_ROLE=LEARN_ROLE               # 没建专用 role 就填 ACCOUNTADMIN
    SNOWFLAKE_WAREHOUSE=LEARN_WH
    SNOWFLAKE_DATABASE=LEARN_DB
    SNOWFLAKE_SCHEMA=PLAYGROUND

A.2 让 mise 加载 ``.env``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``mise.toml`` 加一行（如果还没的话）：

.. code-block:: toml
    :caption: mise.toml

    [env]
    _.file = ".env"

确认变量已注入：

.. code-block:: bash

    mise env | grep '^SNOWFLAKE_'

A.3 跑通连接
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    uvx --from snowflake-cli snow connection test

第一次执行会自动弹出浏览器，在浏览器里点 "Continue" / 确认账号即可。CLI 收到
token 后会回报连接成功。**之后一段时间内的 CLI 命令会复用 session，不再弹窗**。

.. note::

   - 浏览器跳转是 OS 级别行为：远程 SSH / 无 GUI 的机器上用不了。这种场景请走
     方案 B (PAT)。
   - 不需要 Snowflake 账户开通任何 SSO/SAML——``EXTERNALBROWSER`` 就是走 Snowflake
     自家的网页登录，trial 账户开箱可用。


方案 B：Programmatic Access Token（PAT，唯一要管的 "token"）
------------------------------------------------------------------------------
PAT 就是 Snowflake 版的 **GitHub Personal Access Token**：在 UI 里点一下生成一个
长字符串，复制下来放进 ``.env`` 当 ``SNOWFLAKE_PASSWORD``，CLI 直接拿来用。
官方文档：`Programmatic access tokens <https://docs.snowflake.com/en/user-guide/programmatic-access-tokens>`_。

亮点：

- **不是密码、不是密钥**——是一根字符串，可命名、可设过期天数、可单独吊销。
- **作用范围可收窄**到指定 role（``ROLE_RESTRICTION``）。
- **泄漏自动保护**——Snowflake 集成了 GitHub secret scanning，token 进了公开仓库
  会自动被禁。
- 单个用户上限 **15 个 PAT**，够你按用途切开（笔记本、CI、不同项目各一）。

B.1 (一次性) 准备一个 Network Policy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

PAT 的官方要求：**user 必须有一个 network policy 才能用 PAT 登录**。Trial 账号
默认没有，所以需要先建一个。最简单的做法是建一个 "允许所有 IP" 的占位 policy：

.. code-block:: sql

    USE ROLE ACCOUNTADMIN;

    -- 允许所有 IPv4 的占位 policy（学习用够了；生产环境请收窄到自己出口 IP）
    CREATE NETWORK POLICY IF NOT EXISTS PAT_ALLOW_ALL
        ALLOWED_IP_LIST = ('0.0.0.0/0');

    -- 挂到你自己用户上
    ALTER USER <YOUR_USERNAME> SET NETWORK_POLICY = PAT_ALLOW_ALL;

.. tip::

   想更安全？把 ``ALLOWED_IP_LIST`` 换成你家/办公室的出口 IP。临时查出口 IP::

       curl -s ifconfig.me

B.2 生成 PAT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**方式一：Snowsight UI（推荐第一次用）**

1. 左下角账号头像 → **My profile** → 滚到 **Programmatic access tokens**
2. （或：**Admin** → **Users & roles** → 选中自己 → **Programmatic access tokens**）
3. **Generate new token**
4. 填：

   - **Name**：起个有意义的名字，比如 ``learn-laptop-cli``
   - **Expires in**：默认 15 天，最长 365 天
   - **Role restriction**（可选）：选 ``LEARN_ROLE`` 把作用域收窄到学习库

5. 点 **Generate** → **立刻复制出来的那串 token**。**关闭窗口后再也看不到了**。

**方式二：SQL**

.. code-block:: sql

    ALTER USER <YOUR_USERNAME>
        ADD PROGRAMMATIC ACCESS TOKEN learn_laptop_cli
        ROLE_RESTRICTION = 'LEARN_ROLE'
        DAYS_TO_EXPIRY    = 90
        COMMENT           = 'Used by snowflake-cli on personal laptop';

返回结果里会有一个 ``token_secret`` 字段——**就那一次能看到，立刻复制**。

B.3 配 ``.env``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

PAT 在 Snowflake CLI 里 **以 password 的位置使用**——把 token 字符串填到
``SNOWFLAKE_PASSWORD``，不用设 ``SNOWFLAKE_AUTHENTICATOR``：

.. code-block:: bash
    :caption: .env

    SNOWFLAKE_ACCOUNT=myorg-myaccount
    SNOWFLAKE_USER=YOUR_USERNAME
    SNOWFLAKE_PASSWORD=eyJ...这一长串就是 PAT...XYZ

    # 默认资源
    SNOWFLAKE_ROLE=LEARN_ROLE
    SNOWFLAKE_WAREHOUSE=LEARN_WH
    SNOWFLAKE_DATABASE=LEARN_DB
    SNOWFLAKE_SCHEMA=PLAYGROUND

mise 加载方式和方案 A 完全一样（``[env]`` + ``_.file = ".env"``）。

B.4 验证
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    uvx --from snowflake-cli snow connection test
    uvx --from snowflake-cli snow sql -q "SELECT CURRENT_USER(), CURRENT_ROLE();"

B.5 日常管理 PAT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: sql

    -- 列出你的 PAT
    SHOW USER PROGRAMMATIC ACCESS TOKENS FOR USER <YOUR_USERNAME>;

    -- 轮换（旧的立即失效，返回新 token_secret）
    ALTER USER <YOUR_USERNAME> ROTATE PROGRAMMATIC ACCESS TOKEN learn_laptop_cli;

    -- 临时禁用
    ALTER USER <YOUR_USERNAME>
        MODIFY PROGRAMMATIC ACCESS TOKEN learn_laptop_cli SET DISABLED = TRUE;

    -- 吊销
    ALTER USER <YOUR_USERNAME> REMOVE PROGRAMMATIC ACCESS TOKEN learn_laptop_cli;


共用：拿账号标识符 + ``.env.example``
------------------------------------------------------------------------------
不管走方案 A 还是 B，都需要先在 Snowsight Worksheet 里拿到账号标识符（推荐用的
新版 ``<orgname>-<accountname>`` 格式）：

.. code-block:: sql

    SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS account_identifier;

把 ``.env.example`` 提交进 git（**不要提交 ``.env``**）方便其他人参考：

.. code-block:: bash
    :caption: .env.example

    # Snowflake CLI connection (filled in via .env, loaded by mise)
    SNOWFLAKE_ACCOUNT=
    SNOWFLAKE_USER=

    # Option A: External Browser (no secret stored locally)
    # SNOWFLAKE_AUTHENTICATOR=externalbrowser

    # Option B: Programmatic Access Token (paste PAT secret here)
    # SNOWFLAKE_PASSWORD=

    SNOWFLAKE_ROLE=
    SNOWFLAKE_WAREHOUSE=
    SNOWFLAKE_DATABASE=
    SNOWFLAKE_SCHEMA=

确认 ``.env`` 在 ``.gitignore`` 里：

.. code-block:: bash

    grep -q '^\.env$' .gitignore || echo '.env' >> .gitignore


故障排查
------------------------------------------------------------------------------
.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - 报错 / 现象
     - 大概率原因 + 修复
   * - 跑 ``snow connection test`` 一直转圈不弹浏览器
     - 你在 SSH/无 GUI 的机器上用 ``EXTERNALBROWSER``。换方案 B (PAT)。
   * - ``IP ... is not allowed to access Snowflake``
     - PAT 用了但 user 没挂 network policy（或 policy 不包含当前 IP）。
       回到 B.1 创建 ``PAT_ALLOW_ALL`` 并挂到 user。
   * - ``Programmatic access token is invalid``
     - PAT 过期、被禁用或被吊销了。SQL ``SHOW USER PROGRAMMATIC ACCESS TOKENS``
       查状态，要么 ``ROTATE`` 要么重新生成。
   * - ``Insufficient privileges to operate on warehouse 'LEARN_WH'``
     - Role 没拿到 warehouse 的 USAGE，或者 PAT 的 ``ROLE_RESTRICTION`` 限死在
       一个没权限的 role 上。回上一篇看 ``GRANT USAGE ON WAREHOUSE``。
   * - ``mise env`` 看不到 ``SNOWFLAKE_*``
     - ``mise.toml`` 没加 ``[env] _.file = ".env"``，或者你不在项目目录里。
   * - ``Token type "PROGRAMMATIC_ACCESS_TOKEN" is not allowed``
     - 账号上挂了 authentication policy 没把 PAT 加进 ``AUTHENTICATION_METHODS``。
       Trial 账号默认不会有这种 policy，一般不会遇到。


安全清单
------------------------------------------------------------------------------
- ✅ ``.env`` 在 ``.gitignore`` 里
- ✅ PAT 起名带用途和位置（``learn-laptop-cli`` 而不是 ``token1``）
- ✅ PAT 设了合理的 ``DAYS_TO_EXPIRY``（学习用 90 天，自动化用更短）
- ✅ PAT 用 ``ROLE_RESTRICTION`` 锁到 ``LEARN_ROLE``，不是 ``ACCOUNTADMIN``
- ✅ Network policy 收窄到自己的出口 IP（``ALLOW_ALL`` 只用于初学阶段）
- ✅ 定期 ``ROTATE`` PAT
- ❌ 不要把 ``.env`` 上传到任何云盘 / GitHub / Gist


附录：还有 Key-Pair (JWT) 这条路
------------------------------------------------------------------------------
Snowflake 还支持基于 RSA 公私钥的 ``SNOWFLAKE_JWT`` 认证（参见
`Key-pair authentication <https://docs.snowflake.com/en/user-guide/key-pair-auth>`_）。
对纯 CI/CD 场景它有不可替代的好处（私钥不过期、可以单独挂在 service user 上），
但对个人开发者来说，PAT 已经能覆盖 99% 的诉求且管理更简单——所以本项目把
key-pair 留作未来真要做 CI/CD 时再补的方案。


参考资料
------------------------------------------------------------------------------
- `Configure Snowflake CLI connections <https://docs.snowflake.com/en/developer-guide/snowflake-cli/connecting/configure-connections>`_
- `Programmatic access tokens (PATs) <https://docs.snowflake.com/en/user-guide/programmatic-access-tokens>`_
- `Network policies <https://docs.snowflake.com/en/user-guide/network-policies>`_
- `Authentication policies <https://docs.snowflake.com/en/user-guide/authentication-policies>`_
- `Snowflake account identifier 格式 <https://docs.snowflake.com/en/user-guide/admin-account-identifier>`_
- `mise env files <https://mise.jdx.dev/configuration.html#env-file>`_
