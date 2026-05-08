使用智能体
===================

本部分介绍如何在 AgentSociety 2 中使用智能体。

类继承层次
-----------

当前智能体体系的类继承关系：

.. code-block:: text

   AgentBase (ABC)          # agent/base.py — 所有智能体的最小接口
     └── PersonAgent        # agent/person.py — 面向人物仿真的默认智能体

AgentSociety 2 同时在 ``contrib/agent/`` 下提供若干实验性 Agent（如博弈论场景），但核心框架只依赖 ``AgentBase`` 和 ``PersonAgent``。


创建智能体
---------------

PersonAgent
~~~~~~~~~~~

``PersonAgent`` 是 AgentSociety 2 中推荐的人物智能体。它把“一个人怎样行动”拆成三层：

* **profile** 描述相对稳定的身份、背景、偏好和目标；
* **workspace** 保存这个人在仿真中的观察、情绪、意图、计划和记忆；
* **skills** 提供可组合的能力，例如观察环境、更新认知、执行计划和写入记忆。

每个 simulation step 中，``PersonAgent`` 会先构建当前上下文，再让模型按需选择工具和技能。框架不强制固定的“观察 → 认知 → 计划 → 记忆”流水线；这样做的好处是：简单 tick 可以很短，复杂 tick 又能按需要读取更多上下文。

一般情况下，推荐优先使用 ``PersonAgent`` + profile + skills 来表达人的行为差异；只有当你需要改变调度方式、状态机、外部系统调用，或要做一个与人物日常行动完全不同的实验 agent 时，才需要继承 ``AgentBase`` 写新类。

.. code-block:: python

   from agentsociety2 import PersonAgent

   agent = PersonAgent(
       id=1,
       profile={
           "name": "Alice",
           "age": 28,
           "personality": "friendly and curious",
           "bio": "A software engineer who loves hiking."
       }
   )

构造参数
^^^^^^^^^

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - 参数
     - 说明
   * - ``id`` (int)
     - 智能体唯一标识符。
   * - ``profile`` (dict | Any)
     - 画像对象（dict 或可序列化对象）。
   * - ``name`` (str, 可选)
     - 显示名称；为空时按 ``profile["name"]`` 或 ``Agent_{id}`` 推导。
   * - ``init_state`` (dict, 可选)
     - 初始状态，会写入 workspace。仅在对应文件不存在时写入，避免覆盖实验中已演化的状态。
   * - ``**capability_kwargs``
     - 行为/能力参数，全部通过 ``AgentConfig.from_kwargs()`` 解析（见 :ref:`agent-config` 节）。

.. _agent-config:

AgentConfig 配置体系
^^^^^^^^^^^^^^^^^^^^^

``PersonAgent`` 的行为参数通过 ``AgentConfig`` 聚合管理，包含以下子配置：

**ModelConfig** — 模型与上下文窗口

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - 字段
     - 说明
   * - ``model``
     - LiteLLM 模型名（如 ``openai/gpt-4o``）。
   * - ``context_window``
     - 显式声明上下文窗口（tokens）；``None`` 时自动从 LiteLLM 解析，默认 200,000。

**LoopConfig** — 工具循环限制

.. list-table::
   :widths: 30 15 55
   :header-rows: 1

   * - 字段
     - 默认值
     - 说明
   * - ``max_rounds``
     - 24
     - 单步最大工具轮数。
   * - ``step_timeout``
     - 600
     - 单步总超时（秒）。
   * - ``llm_request_timeout``
     - 120.0
     - 单次 LLM 请求超时（秒）；``None`` 表示不限。
   * - ``bash_retries``
     - 1
     - bash 超时后额外重试次数。
   * - ``llm_retries``
     - 3
     - LLM 请求最大重试次数。
   * - ``tool_decision_max_retries``
     - 10
     - ``acompletion_with_pydantic_validation`` 最大重试次数。

**ContextConfig** — 上下文与压缩

.. list-table::
   :widths: 35 15 50
   :header-rows: 1

   * - 字段
     - 默认值
     - 说明
   * - ``preload_workspace_paths``
     - []
     - 预读文件列表，注入 system prompt 的 workspace 快照。
   * - ``thread_key_state_paths``
     - []
     - thread 压缩时附带的 KEY_STATE_JSON 文件路径。
   * - ``system_prompt_max_identity_chars``
     - 10000
     - Agent Identity JSON 总长度上限。
   * - ``workspace_read_chunk_cap``
     - 32000
     - ``workspace_read`` 单段最大字符数。
   * - ``tool_result_thread_budget``
     - 64000
     - 单条 TOOL_RESULT_JSON 序列化预算。
   * - ``profile_max_chars``
     - 4000
     - profile 截断阈值。

**PersistenceConfig** — 持久化

.. list-table::
   :widths: 35 15 50
   :header-rows: 1

   * - 字段
     - 默认值
     - 说明
   * - ``checkpoint_interval``
     - 10
     - 每 N 步保存一次检查点。
   * - ``checkpoint_max``
     - 20
     - 保留的最大检查点数量。
   * - ``enable_llm_history``
     - False
     - 是否启用 LLM 交互历史记录。
   * - ``llm_history_max_entries``
     - 100
     - LLM 历史最大条目数。

**ConcurrencyConfig** — 并发控制

.. list-table::
   :widths: 35 15 50
   :header-rows: 1

   * - 字段
     - 默认值
     - 说明
   * - ``max_parallel_tools``
     - 5
     - batch 工具最大并行数。
   * - ``max_llm_concurrent``
     - 5
     - LLM 最大并发请求。
   * - ``max_subprocess``
     - 8
     - 子进程最大并发数。
   * - ``rate_limit_rps``
     - 10.0
     - 令牌桶限流（请求/秒）。

这些参数可通过构造时的 ``**capability_kwargs`` 传入，也可通过环境变量覆盖（如 ``AGENT_MODEL``、``AGENT_MAX_TOOL_ROUNDS`` 等）。


工具循环（Tool Loop）
^^^^^^^^^^^^^^^^^^^^^^

``PersonAgent.step()`` 的核心是一个“决策—执行—反馈”循环。模型每轮只提交一个结构化 ``ToolDecision``，运行时负责校验、执行和把结果写回上下文。这个设计让 LLM 的自由生成被限制在可审计的工具结果里，也方便在 replay 中复盘每一步为什么发生。

核心流程：

.. list-table::
   :widths: 28 72
   :header-rows: 1

   * - 阶段
     - 说明
   * - 上下文构建
     - 预读 workspace 文件、刷新技能目录、构建系统提示词（静态段可缓存 + 动态段）。
   * - 决策
     - 每轮由 ``acompletion_with_pydantic_validation(ToolDecision)`` 获取工具决策。
   * - 语义校验
     - ``tool_name`` 做模糊匹配与纠正，无效名称返回可恢复错误对象。
   * - 安全检查
     - ``ToolPolicy.check()`` 对 bash 命令做安全拦截。
   * - 循环检测
     - ``LoopDetectionService`` 检测 AAAA/ABAB 重复、过度使用等异常模式。
   * - 执行工具
     - 按工具名分发到具体处理器（技能操作、workspace 操作、bash、codegen 等）。
   * - 结果回写
     - 工具结果写入 thread（内存窗口 + 磁盘 JSONL），同时更新 workspace 缓存。
   * - 结束条件
     - ``done=true`` 时先执行当前工具再结束；``tool_name="done"/"finish"`` 立即结束。

有效工具列表
^^^^^^^^^^^^^

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - 工具名
     - 说明
   * - ``activate_skill``
     - 加载指定技能的完整 SKILL.md（含 ``$ARGUMENTS``/``$N`` 占位符替换和以 ``!`` 开头的反引号命令动态上下文注入）。
   * - ``read_skill``
     - 读取技能目录内的文件。
   * - ``execute_skill``
     - 执行技能脚本（如有 ``scripts/<name>.py``），以子进程运行。
   * - ``workspace_read``
     - 读取 agent 工作区文件（含分页）。
   * - ``workspace_write``
     - 写入 agent 工作区文件。
   * - ``workspace_list``
     - 列出工作区文件。
   * - ``bash``
     - 在工作区内执行 bash 命令（含安全检查与超时）。
   * - ``glob``
     - 按模式搜索工作区文件。
   * - ``grep``
     - 在工作区文件中搜索内容。
   * - ``codegen``
     - 通过环境路由器执行代码生成。
   * - ``batch``
     - 批量执行多个工具（只读工具并行，写入工具顺序执行）。
   * - ``done``
     - 结束当前仿真步（不执行额外工具）。
   * - ``finish``
     - 同 ``done``，带 summary 提交。

ToolDecision 模型
^^^^^^^^^^^^^^^^^^

LLM 的每轮输出会被解析为 ``ToolDecision`` Pydantic 模型：

.. code-block:: python

   class ToolDecision(BaseModel):
       tool_name: str              # 必须是有效工具之一
       arguments: dict[str, Any]   # 工具参数
       done: bool = False          # 是否在当前工具执行后结束步骤
       summary: str = ""           # 执行摘要

模型内置 ``_coerce_llm_field_shapes`` 验证器，自动处理 LLM 常见的输出错误（嵌套包装、字段名别名、arguments 为字符串等）。


上下文压缩
^^^^^^^^^^^

当对话线程（thread）过长时，``PersonAgent`` 会执行分层压缩以控制在模型上下文窗口内：

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - 层级
     - 说明
   * - Light pruning
     - 去重相邻工具结果，按优先级丢弃低优先级消息。
   * - Medium compression
     - 调用 LLM 生成 ``StructuredSummary`` （结构化摘要 JSON）。
   * - Heavy compression
     - 滚动摘要合并，适用于极高利用率场景。

触发阈值（占上下文窗口比例）：

- **58%** — 警告
- **72%** — 触发压缩
- **84%** — 自动压缩
- **90%** — 强制压缩


内置 Skills
^^^^^^^^^^^

当前内置技能位于 ``agentsociety2/agent/skills/`` 目录：

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - 技能
     - 说明
   * - ``observation``
     - 观察环境与自身状态。
   * - ``cognition``
     - 生成情绪、需求和意图。
   * - ``plan``
     - 制定与更新行动计划。
   * - ``memory``
     - 记忆管理与检索。

它们不是固定“必须执行层”，而是由模型按上下文按需选择。

详细说明请参见 :doc:`agent_skills`。

理解这些技能时，可以把它们看成一条常见但不强制的行动链：

1. ``observation`` 获取新环境事实。
2. ``cognition`` 把事实、需求、记忆和 profile 转成情绪与意图。
3. ``plan`` 把意图变成一个可提交给环境的行动或多步计划。
4. ``memory`` 只记录值得跨 tick 保留的结果。

这只是推荐链路，不是框架硬编码的流程。实际执行顺序由工具循环中的模型决策、环境约束 ``PersonStepConstraints``、已存在的 workspace 状态共同决定。


初始化流程
^^^^^^^^^^

``PersonAgent.init(env)`` 执行以下步骤：

1. 调用父类 ``AgentBase.init(env)``
2. 创建 agent 工作目录与标准目录结构
3. 从 ``init_state`` 种子写入 workspace（仅写入不存在的文件）
4. 加载持久化的 ``agent_config.json`` （恢复已激活技能）
5. 扫描 custom skills（``<workspace>/custom/skills/``）与环境模块 skills
6. 刷新可见技能列表
7. 激活环境模块声明的默认技能
8. 获取世界描述
9. 初始化检查点、WAL（预写日志）和清理器
10. 尝试从最近检查点恢复
11. 初始化持久化记忆（``AgentMemory``）


持久化与恢复
^^^^^^^^^^^^^

``PersonAgent`` 的持久化由多层机制保障：

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - 组件
     - 说明
   * - ``Checkpoint``
     - ACID 检查点（原子写入 + SHA256 校验 + fsync），按 ``checkpoint_interval`` 定期保存。
   * - ``WriteAheadLog``
     - 预写日志，记录 workspace_write/bash/execute_skill 的写入意图，用于崩溃恢复。
   * - ``WorkspaceCleaner``
     - 定期清理日志、JSONL 轮转、检查点归档。
   * - ``SessionRecovery``
     - 从检查点 + WAL pending + 状态摘要构建恢复上下文。
   * - ``AgentMemory``
     - 持久化记忆（``AGENT_MEMORY.md``），跨 step 保持关键信息。

Agent 工作区文件结构：

.. code-block:: text

   <run_dir>/agents/agent_XXXX/
   ├── agent_config.json       # Agent 配置
   ├── AGENT.md                # 动态上下文文件
   ├── AGENT_FILES.md          # 工作区文件清单
   ├── state/                  # 状态文件
   │   ├── emotion.json
   │   ├── intention.json
   │   ├── needs.json
   │   └── plan_state.json
   ├── memory/                 # 记忆文件
   ├── .runtime/
   │   ├── logs/
   │   │   ├── session_state.json
   │   │   ├── thread_messages.jsonl
   │   │   ├── tool_calls.jsonl
   │   │   └── thread_compact_state.json
   │   └── checkpoints/
   ├── custom/skills/          # 自定义技能目录
   └── wal/                    # Write-Ahead Log 目录


自定义智能体
~~~~~~~~~~~~~

.. note::

   对于扩展 PersonAgent 的认知能力，推荐使用 **Agent Skills** 系统。
   参见 :doc:`agent_skills` 了解如何创建自定义 skill。

   只有在需要完全不同的智能体架构时，才需要创建自定义智能体类。

要创建自定义智能体，请继承 ``AgentBase`` 并实现必需的抽象方法。

如果你通过 VS Code 扩展或 ``.agentsociety/bin/ags.py`` 工作流创建自定义 Agent，可以使用内置的 **agentsociety-create-agent** 技能。它会把文件放在 ``custom/agents/``，并用本地校验器检查：

* 文件必须是 Python 文件，且不要放在路径片段 ``examples/`` 下（扫描器会跳过示例目录）。
* 至少有一个直接继承 ``AgentBase`` 或 ``PersonAgent`` 的类。
* ``ask``、``step``、``dump``、``load`` 必须都是 ``async def``。
* 模块能被动态导入，目标类不能仍是 abstract class。

校验命令示例：

.. code-block:: bash

   PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
   PYTHON_PATH=${PYTHON_PATH:-.venv/bin/python}
   $PYTHON_PATH .agentsociety/bin/ags.py create-agent --file custom/agents/my_agent.py

AgentBase 抽象方法
^^^^^^^^^^^^^^^^^^^

创建自定义智能体时，必须实现 ``AgentBase`` 的以下抽象方法：

1. **async def ask(self, message: str, readonly: bool = True) -> str**

   处理来自环境或用户的问题并返回响应。

   :param message: 要处理的问题或指令。
   :param readonly: 智能体是否可以修改环境（``False`` = 可以修改）。
   :returns: 智能体的响应字符串。

2. **async def step(self, tick: int, t: datetime) -> str**

   执行一个模拟步骤。

   :param tick: 此步骤的时间跨度（秒）。
   :param t: 此步骤结束后的当前模拟日期时间。
   :returns: 智能体在此步骤中的操作描述。

3. **async def dump(self) -> dict**

   将智能体状态序列化为字典以便保存/加载。

4. **async def load(self, dump_data: dict)**

   从先前 dump 的字典中恢复智能体状态。

AgentBase 其他可用方法
^^^^^^^^^^^^^^^^^^^^^^^

``AgentBase`` 还提供以下可直接使用的方法：

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - 方法
     - 说明
   * - ``acompletion(messages, stream)``
     - 向 LLM 发送补全请求，支持流式/非流式。
   * - ``acompletion_with_system_prompt(messages, tick, t)``
     - 自动附加系统提示词的 LLM 补全请求。
   * - ``acompletion_with_pydantic_validation(model_type, messages, tick, t, ...)``
     - 带自动 Pydantic 校验与多轮纠错的 LLM 请求（支持 429 指数退避）。
   * - ``ask_env(ctx, message, readonly, template_mode)``
     - 向环境路由器发送请求。
   * - ``get_system_prompt(tick, t)``
     - 生成包含身份、时间上下文和行为指南的系统提示词。
   * - ``answer_external_question(prompt, *, t, response_type, choices)``
     - 基于内部状态回答外部问卷/访谈（不经过环境路由）。
   * - ``set_skill_state(skill_name, state)``
     - 设置技能状态。
   * - ``get_skill_state(skill_name)``
     - 获取技能状态。
   * - ``get_token_usages()``
     - 获取 Token 使用统计。
   * - ``get_llm_interaction_history()``
     - 获取 LLM 交互历史记录。

参考实现
^^^^^^^^^^^^

有关完整参考，请参阅源代码中的 ``PersonAgent``。

示例：

.. code-block:: python

   from agentsociety2.agent import AgentBase
   from datetime import datetime

   class MyAgent(AgentBase):
       def __init__(self, id: int, profile: dict, **kwargs):
           super().__init__(id=id, profile=profile, **kwargs)
           self._custom_state = profile.get("custom_field", {})

       async def ask(self, message: str, readonly: bool = True) -> str:
           return await super().ask(message, readonly=readonly)

       async def step(self, tick: int, t: datetime) -> str:
           return await super().step(tick, t)

       async def dump(self) -> dict:
           return {
               "custom_state": self._custom_state,
               "profile": self.get_profile(),
           }

       async def load(self, dump_data: dict):
           self._custom_state = dump_data.get("custom_state", {})


智能体配置文件
--------------

配置文件设计
~~~~~~~~~~~~~

一个好的智能体配置文件应包括：

* **身份**: 姓名、年龄、角色
* **个性**: 特征、偏好、怪癖
* **背景**: 历史、专业知识、关系
* **目标**: 动机、欲望、恐惧

.. code-block:: python

   profile = {
       # Identity
       "name": "Dr. Sarah Chen",
       "age": 35,
       "occupation": "climate scientist",

       # Personality
       "personality": "analytical, passionate, slightly anxious",
       "traits": ["detail-oriented", "empathetic", "curious"],

       # Background
       "education": "PhD in Atmospheric Science",
       "experience": "10 years in climate research",
       "achievements": ["Published 30+ papers", "Nobel nominee"],

       # Goals
       "goal": "raise awareness about climate change",
       "fears": ["sea level rise", "ecosystem collapse"]
   }

配置文件可以包含你希望的任何字段；``PersonAgent`` 会自动过滤潜在的指令注入（如 SYSTEM/INSTRUCTION 等关键字模式），并将过长的 profile 截断到配置的 ``profile_max_chars`` 阈值内。

与智能体交互
-----------------------

ask() 方法
~~~~~~~~~~~~~~~~~

.. code-block:: python

   response = await agent.ask(
       "What's your opinion on renewable energy?",
       readonly=True  # No side effects
   )

``readonly`` 参数控制智能体是否可以修改环境：

* ``readonly=True``: 仅查询，无副作用
* ``readonly=False``: 可能调用修改状态的环境工具

step() 方法
~~~~~~~~~~~~~~~~~

``step()`` 方法在 AgentSociety 模拟期间自动调用：

.. code-block:: python

   # Called by AgentSociety.run()
   # tick = duration in seconds, t = current simulation time
   action_description = await agent.step(tick=3600, t=datetime.now())

execute() 方法
~~~~~~~~~~~~~~~~~

直接执行技能（不经过工具循环）：

.. code-block:: python

   result = await agent.execute(
       skill_name="cognition",
       args={"tick": 3600}
   )

会话管理
~~~~~~~~~

.. code-block:: python

   # 重置会话（清空 thread、工具状态，可选保留记忆）
   agent.clear_session(keep_memory=True)

   # 将当前状态写入持久化记忆
   agent.handoff_to_memory()

智能体记忆
------------

``PersonAgent`` 的记忆系统分为三层：

1. **Thread（对话线程）**：短期上下文，维护最近工具调用和 LLM 交互，过长时自动压缩。
2. **AgentMemory（运行时持久化记忆）**：跨 step 保持当前任务、已完成动作、错误记录等。位于 ``AGENT_MEMORY.md``，由 thread 压缩摘要和 ``handoff_to_memory()`` 更新。
3. **Skill 记忆文件**：``memory`` 技能按需写入 ``state/memory.jsonl``，并可用维护脚本执行遗忘曲线和检索强化。
4. **Workspace 状态文件**：技能脚本写入的状态文件（``state/emotion.json``、``state/intention.json``、``state/plan_state.json`` 等）。

``AgentMemory`` 与 ``memory`` skill 不是同一个东西：

* ``AgentMemory`` 是框架级会话摘要，主要服务长线程压缩、恢复与错误连续性。
* ``state/memory.jsonl`` 是 agent 的经验记忆，由 LLM 决定写什么，适合保存社会关系、地点、承诺、计划结果等可检索事实。
* 是否写入 ``state/memory.jsonl`` 由 ``memory`` 技能和工具循环决定，不是每步固定 finalize 阶段。

如果你想替换/扩展记忆策略，推荐做法是新增/替换 skill，而不是修改 ``PersonAgent`` 本体。
