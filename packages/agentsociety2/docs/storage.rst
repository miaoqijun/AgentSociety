存储与结果访问
=========================

AgentSociety 2 把实验数据落到两个位置：

* **SQLite 数据库**: ``<run_dir>/sqlite.db``。所有 replay 数据（agent profile、agent 快照、env 快照、事件流等）都写入这一个数据库，并通过 catalog 表自描述。
* **本地工作目录**: ``<run_dir>/artifacts/``、``<run_dir>/agents/agent_<id>/``、``<run_dir>/pid.json`` 等文件，存放 ``ask``/``intervene`` 产物、agent workspace 与运行时元信息。

读取结果有三条路径：

* 后端 REST API ``/api/v1/replay/...``\ （推荐，配合前端 / VSCode replay webview）
* 直接 SQL/Pandas 访问 SQLite
* 直接读取 workspace 中的 ``*.json`` / ``*.jsonl``\ （用于 agent 行为分析、调试）

.. note::

   ``ReplayWriter`` 不再为新实验写入 ``agent_profile``、``agent_status``、
   ``agent_dialog`` 三张旧框架表。它们仅在读取历史数据库时通过 ``agentsociety2.storage.models``
   保留 ORM 兼容；新实验等价信息以 catalog-driven dataset 形式存在。

Run 目录布局
-----------------

CLI 入口 ``python -m agentsociety2.society.cli`` 以 ``--run-dir`` 指定的目录作为实验
HOME。``ExperimentRunner`` 会在其中创建以下结构：

.. code-block:: text

   <run_dir>/
   ├── sqlite.db                # 所有 replay 数据 + catalog
   ├── pid.json                 # 进程信息与终止状态
   ├── artifacts/               # ask / intervene / questionnaire 的 Markdown 产物
   │   ├── ask_step_<i>_<ts>.md
   │   ├── intervene_step_<i>_<ts>.md
   │   └── questionnaire_step_<i>_<ts>.md
   └── agents/                  # 各 PersonAgent 的工作目录
       └── agent_0001/
           ├── agent_config.json
           ├── AGENT.md
           ├── state/
           │   ├── emotion.json
           │   ├── intention.json
           │   └── plan_state.json
           ├── .runtime/logs/
           │   ├── session_state.json
           │   ├── session_state_history.jsonl
           │   ├── step_replay.jsonl
           │   ├── tool_calls.jsonl
           │   └── thread_messages.jsonl
           └── wal/
               ├── wal.jsonl
               └── index.json

当通过后端读取实验数据时，``run_dir`` 是从 ``workspace_path`` +
``hypothesis_<id>/experiment_<id>/run`` 组装得到的（见
:func:`agentsociety2.backend.routers.replay.get_db_path`）。

SQLite 数据库
----------------

每个实验对应一个 ``sqlite.db``。``ReplayWriter`` 在 ``init()`` 时即创建两张
catalog 表，整个数据库的层次为：

* **Catalog 层**: ``replay_dataset_catalog`` + ``replay_column_catalog``。所有上层
  API、可视化与分析都先从这里发现"当前实验有哪些 dataset、每列的语义是什么"。
* **Profile 层**: ``core_agent_profile`` 表（dataset id ``core.agent_profile``，
  capability ``agent_profile``），由 :class:`~agentsociety2.society.AgentSociety`
  在 :meth:`agentsociety2.society.AgentSociety.init` 中一次性写入。
* **环境数据层**: 每个环境模块按声明式或手工方式注册的表
  （``{prefix}_agent_state``、``{prefix}_env_state``、自定义事件流表等）。

存储架构
~~~~~~~~~~~~~~~~~

.. graphviz::

   digraph storage_architecture {
       rankdir=TB;
       node [shape=box, style=rounded];

       subgraph cluster_db {
           label = "sqlite.db";
           style=filled;
           color=lightblue;

           Catalog [label="replay_dataset_catalog\nreplay_column_catalog"];
           Profile [label="core_agent_profile"];
           AgentState [label="<prefix>_agent_state\n(entity_snapshot)"];
           EnvState [label="<prefix>_env_state\n(env_snapshot)"];
           Custom [label="自定义事件 / 指标表\n(event_stream / metric_series)"];
       }

       subgraph cluster_workspace {
           label = "<run_dir>/agents/agent_<id>/";
           style=filled;
           color=lightgreen;

           Config [label="agent_config.json"];
           State [label="state/*.json"];
           Logs [label=".runtime/logs/*.jsonl"];
           WAL [label="wal/wal.jsonl"];
       }

       Society [label="AgentSociety"];
       Env [label="EnvBase 子类"];
       Person [label="PersonAgent"];

       Society -> Profile;
       Society -> Catalog;
       Env -> AgentState;
       Env -> EnvState;
       Env -> Custom;
       AgentState -> Catalog [label="register_dataset", style=dashed];
       EnvState -> Catalog [label="register_dataset", style=dashed];
       Custom -> Catalog [label="register_dataset", style=dashed];

       Person -> Config;
       Person -> State;
       Person -> Logs;
       Person -> WAL;
   }

Catalog 表
~~~~~~~~~~~~

``replay_dataset_catalog`` 关键字段：

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 字段
     - 说明
   * - ``dataset_id``
     - dataset 全局唯一 id，例如 ``core.agent_profile``、``economy.agent_state``、``social_media.event``
   * - ``table_name``
     - 对应 SQLite 物理表名
   * - ``module_name``
     - 数据生产者，通常是环境模块类名或 ``AgentSociety``
   * - ``kind``
     - ``entity_snapshot`` / ``entity_static`` / ``env_snapshot`` / ``event_stream`` / ``metric_series``
   * - ``entity_key``
     - 标识实体的列（agent_id 等），如适用
   * - ``step_key``
     - step 列名（用于按步过滤）
   * - ``time_key``
     - 时间戳列名
   * - ``default_order``
     - 默认排序键（JSON）
   * - ``capabilities``
     - dataset 能力标签（JSON），决定上层 UI 怎么用

``replay_column_catalog`` 关键字段：``sqlite_type``、``logical_type``、
``analysis_role``、``unit``、``enum_values``、``example``、``tags``。

常见 capability：

* ``agent_profile``  — agent 静态档案
* ``agent_snapshot`` — agent per-step 状态
* ``env_snapshot``   — env per-step 状态
* ``timeseries``     — 适合按时间轴展开
* ``geo_point``      — 含 ``lng``/``lat``，可在地图上画
* ``trajectory``     — 适合做轨迹回放
* ``entity_static``  — 一次性静态实体表
* ``event_stream``   — 事件流

后端 panel-schema、map layer、time line 等接口都通过 capability 自动挑选 dataset；
模块作者只要正确声明 capability，前端无需改动即可识别。

写入数据
-----------

环境模块的状态数据有两种写入路径：**声明式**\ （推荐）和 **手工注册**\ （事件流、自定义形状）。
两条路径都直接调用同一个 ``ReplayWriter``，注入逻辑在
:meth:`agentsociety2.society.AgentSociety.init` 中自动完成
（``env_router.set_replay_writer(writer)``）。

方式 A：声明式 ``_agent_state_columns`` / ``_env_state_columns``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

子类化 :class:`~agentsociety2.env.base.EnvBase` 时，把希望每步落库的列声明在 class var
里。``EnvBase`` 会在首次写入前自动：

1. 推导表名前缀（PascalCase → snake_case，去 ``Space``/``Env``/``Module`` 后缀）。
2. 在 sqlite 里建好 ``{prefix}_agent_state`` 和/或 ``{prefix}_env_state``，主键
   ``(agent_id, step)`` / ``(step,)``，自动加索引。
3. 调 ``register_dataset`` 写入 catalog，capability 默认为
   ``["agent_snapshot", "timeseries"]`` / ``["env_snapshot", "timeseries"]``；如果
   ``_agent_state_columns`` 同时声明了 ``lng`` 和 ``lat``，会额外追加
   ``geo_point`` 和 ``trajectory``。

模块在 ``step()`` 中调用 ``EnvBase._write_agent_state()``、
``EnvBase._write_agent_state_batch()``、``EnvBase._write_env_state()`` 即可。

.. code-block:: python

   from typing import ClassVar
   from agentsociety2.env import EnvBase, tool
   from agentsociety2.storage import ColumnDef


   class EconomySpace(EnvBase):
       _agent_state_columns: ClassVar[list[ColumnDef]] = [
           ColumnDef("currency", "REAL", analysis_role="measure",
                     description="Agent currency balance."),
           ColumnDef("income", "REAL", analysis_role="measure"),
           ColumnDef("consumption", "REAL", analysis_role="measure"),
       ]
       _env_state_columns: ClassVar[list[ColumnDef]] = [
           ColumnDef("bank_interest_rate", "REAL", analysis_role="measure"),
       ]

       async def step(self, tick: int, t):
           # 每步把所有 agent 的状态批量落库
           records = [
               {"agent_id": p.id, "currency": p.currency,
                "income": p.income, "consumption": p.consumption}
               for p in self._persons.values()
           ]
           await self._write_agent_state_batch(self._step, t, records)
           await self._write_env_state(self._step, t,
                                       bank_interest_rate=self._bank_interest_rate)
           self._step += 1

声明式路径覆盖了所有"per-agent per-step 快照 + per-step 环境快照"的常见需求，
也是与前端 / replay webview 兼容性最好的方式。

方式 B：手工 ``register_table`` + ``register_dataset``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

事件流（``kind="event_stream"``）或形状不规则的数据，仍可手工注册：

.. code-block:: python

   from agentsociety2.storage import ColumnDef, ReplayDatasetSpec, TableSchema

   schema = TableSchema(
       name="social_media_event",
       columns=[
           ColumnDef("id", "INTEGER", nullable=False),
           ColumnDef("step", "INTEGER", nullable=False, logical_type="step"),
           ColumnDef("t", "TIMESTAMP", nullable=False, logical_type="timestamp"),
           ColumnDef("sender_id", "INTEGER", logical_type="identifier"),
           ColumnDef("event_type", "TEXT", logical_type="enum",
                     enum_values=["post", "follow", "like", "comment", "repost"]),
           ColumnDef("payload", "JSON"),
       ],
       primary_key=["id"],
       indexes=[["step"], ["sender_id"], ["event_type"]],
   )
   await self._replay_writer.register_table(schema)
   await self._replay_writer.register_dataset(
       ReplayDatasetSpec(
           dataset_id="social_media.event",
           table_name="social_media_event",
           module_name=self.name,
           kind="event_stream",
           title="Social Media Event Stream",
           description="Posts / follows / likes / comments / reposts.",
           entity_key="sender_id",
           step_key="step",
           time_key="t",
           default_order=["step", "id"],
           capabilities=["event_stream", "social_event"],
       ),
       schema.columns,
   )

   # 写入
   await self._replay_writer.write("social_media_event", {...})
   await self._replay_writer.write_batch("social_media_event", [{...}, {...}])

``register_table`` 和 ``register_dataset`` 都是幂等的：相同 ``dataset_id`` 会覆盖
catalog 行，相同 ``table_name`` 不会重复建表。

``ReplayWriter`` 的核心 API
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* :meth:`agentsociety2.storage.ReplayWriter.init` /
  :meth:`agentsociety2.storage.ReplayWriter.close`: 生命周期。
* :meth:`agentsociety2.storage.ReplayWriter.register_table`: 仅建物理表。
* :meth:`agentsociety2.storage.ReplayWriter.register_dataset`: 写 catalog
  （会自动确保 catalog 表存在）。
* :meth:`agentsociety2.storage.ReplayWriter.write` /
  :meth:`agentsociety2.storage.ReplayWriter.write_batch`:
  通用行级 / 批量 ``INSERT OR REPLACE``，自动处理 ``datetime`` 与 dict/list。

``ReplayWriter`` 是 async + 锁保护的，可被多个 env module 并发调用。
``AgentSociety`` 在 :meth:`agentsociety2.society.AgentSociety.init` 中自动把 writer
注入给每个 env module；自定义编排（直接构造 ``AgentSociety``）也可以传入已经
``init()`` 过的 writer。

读取数据
-----------

方式 1：后端 REST API（推荐）
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

启动 ``python -m agentsociety2.backend.run`` 后，replay API 挂在 ``/api/v1/replay``，
所有请求都带一个 ``workspace_path`` query 参数，后端据此定位
``<workspace_path>/hypothesis_<id>/experiment_<id>/run/sqlite.db``。

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - 路径
     - 作用
   * - ``GET /info``
     - 实验摘要：``total_steps``、``start_time``、``end_time``、``agent_count``
   * - ``GET /datasets``
     - 返回当前实验所有 dataset 及列元数据
   * - ``GET /datasets/{dataset_id}``
     - 单个 dataset 详情
   * - ``GET /datasets/{dataset_id}/rows``
     - 分页行查询（详见下表）
   * - ``GET /panel-schema``
     - 前端 panel/地图布局：``agent_profile_dataset``、``agent_state_datasets``、``env_state_datasets``、``geo_dataset``、``primary_agent_state_dataset_id``、``layout_hint``、``supports_map``
   * - ``GET /steps/{step}/bundle``
     - 某一步的合并快照：所有 agent 状态、env 状态、地理位置
   * - ``GET /timeline``
     - ``step → t`` 映射，用于时间轴
   * - ``GET /agents/profiles``
     - agent profile 列表（优先读 ``core_agent_profile``，否则从主 agent state dataset 推导）

完整前缀为 ``/api/v1/replay/{hypothesis_id}/{experiment_id}/...``。

``/datasets/{dataset_id}/rows`` 支持的过滤/分页参数：

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - 参数
     - 说明
   * - ``page``
     - 从 1 开始的页码
   * - ``page_size``
     - 每页行数（1–200）
   * - ``order_by``
     - 手动指定排序列；不传则用 dataset 的 ``default_order``
   * - ``desc_order``
     - 是否倒序
   * - ``step``
     - 精确等于某一 step
   * - ``entity_id``
     - 精确等于某个实体 id（``entity_key`` 必须存在）
   * - ``start_step``
     - step 范围下界（含）
   * - ``end_step``
     - step 范围上界（含）
   * - ``max_step``
     - step ≤ max_step（用于"截止某步"查询）
   * - ``columns``
     - 逗号分隔白名单
   * - ``latest_per_entity``
     - ``true`` 时返回每个实体最新的一行（按 ``step`` 倒序窗口函数）

示例：

.. code-block:: bash

   # 列出所有 dataset
   curl 'http://localhost:8001/api/v1/replay/1/1/datasets?workspace_path=/data/workspace'

   # 查 step=42 的所有 economy.agent_state 行
   curl 'http://localhost:8001/api/v1/replay/1/1/datasets/economy.agent_state/rows?workspace_path=/data/workspace&step=42&page_size=200'

   # 拉时间线
   curl 'http://localhost:8001/api/v1/replay/1/1/timeline?workspace_path=/data/workspace'

返回值约定：catalog 中标为 JSON 的列会被自动反序列化为对象；``datetime`` 列以
ISO-8601 字符串返回。

方式 2：直接读 SQLite
~~~~~~~~~~~~~~~~~~~~~~

适合做分析、生成图表，或在没有后端的环境下离线消费：

.. code-block:: python

   import sqlite3
   import pandas as pd

   with sqlite3.connect("<run_dir>/sqlite.db") as conn:
       # 1. 先看 catalog 知道有哪些 dataset
       datasets = pd.read_sql_query(
           "SELECT dataset_id, table_name, kind, module_name, "
           "capabilities_json FROM replay_dataset_catalog "
           "ORDER BY dataset_id",
           conn,
       )

       # 2. 抓 agent profile
       profile = pd.read_sql_query(
           "SELECT id, name, profile FROM core_agent_profile ORDER BY id",
           conn,
       )

       # 3. 抓 per-step 快照
       state = pd.read_sql_query(
           "SELECT * FROM economy_agent_state "
           "WHERE step BETWEEN ? AND ? ORDER BY step, agent_id",
           conn,
           params=(0, 100),
       )

JSON 列（profile、payload 等）以 TEXT 形式存储，使用前需 ``json.loads`` 或
``pd.read_json``。``TIMESTAMP`` 列以 ISO-8601 字符串形式存储（``ReplayWriter``
内部对 Python 3.12+ 弃用的 sqlite3 datetime adapter 做了规避）。

方式 3：直接读 workspace 文件
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``<run_dir>/artifacts/`` 是 CLI 在 ``ask`` / ``intervene`` / ``questionnaire``
步骤上保存的 Markdown 产物，可直接展示给研究者。

``<run_dir>/agents/agent_<id>/`` 中常用文件：

* ``agent_config.json`` — agent 能力、初始状态、技能可见性覆盖、已激活技能
* ``AGENT.md`` — 运行时维护的上下文文件 / workspace 文件索引
* ``state/*.json`` — 内置状态（``emotion``、``intention``、``plan_state``）以及
  任何用户自定义状态文件
* ``state/memory.jsonl`` — ``memory`` skill 写入的长期事件记忆
* ``.runtime/logs/session_state.json`` — 最近一次 step 的可见 / 已激活技能
* ``.runtime/logs/session_state_history.jsonl`` — 会话状态时间线
* ``.runtime/logs/step_replay.jsonl`` — 每个 step 的工具历史
* ``.runtime/logs/tool_calls.jsonl`` — 工具调用日志
* ``.runtime/logs/thread_messages.jsonl`` — 最近 thread 消息
* ``wal/wal.jsonl`` + ``wal/index.json`` — 写前日志与内存索引

这些文件适合调试 agent 行为、复现 thread 上下文、审视技能执行过程；不会进入
SQLite 数据库。

兼容旧数据库
----------------

旧版本（v1 或早期 v2）数据库里可能仍包含 ``agent_profile``、``agent_status``、
``agent_dialog`` 三张框架表。读取规则：

* 新实验不再写入这三张表。
* 后端 replay API 在 ``core.agent_profile`` dataset 不存在时，会从有
  ``agent_snapshot`` capability 的动态 dataset 中推导 agent 列表
  （实现位于 ``agentsociety2.backend.routers.replay`` 的私有加载逻辑中）。
* 历史表的 ORM 定义仍保留在 ``agentsociety2.storage.models``，供需要时显式读取。

迁移建议：分析旧实验时优先看 ``replay_dataset_catalog`` 是否存在；若不存在则数据库
属于纯旧格式，直接查 ``agent_profile`` / ``agent_status`` / ``agent_dialog``。
