Agent Skills（智能体技能）
=================================

概述
------

Agent Skills 是 ``PersonAgent`` 的能力插件系统。它解决的问题很直接：一个人物智能体不应该把所有行为都写死在一个巨大类里，而应该把“会观察”“会形成意图”“会执行计划”“会记住重要事件”等能力拆成可读、可替换、可调试的模块。

内置技能包括 ``observation``、``cognition``、``plan``、``memory``。用户也可以在 workspace 中添加自定义技能，让不同实验拥有不同的行为能力。

当前实现采用两条核心原则：

1. **Metadata-first**：选择阶段只暴露 ``name`` + ``description``，不加载完整正文。
2. **按需执行**：每步由模型在工具循环里 ``activate_skill`` / ``read_skill`` / ``execute_skill``，没有固定的全局流水线。

这意味着：技能是否执行由当前上下文、环境约束和模型选择共同决定。简单场景不会被迫走完整流程；复杂场景也可以按需读取技能说明、工作区文件和环境反馈。


设计目标
---------

* **按需加载**：降低每步不必要的上下文占用与执行开销。
* **可解释选择**：选择依据来自 catalog 中的简短描述，便于调试和复盘。
* **热更新友好**：支持运行时扫描、导入、启用/禁用与重载。
* **文件约定解耦**：技能通过 workspace 文件交换状态，而不是互相直接调用。
* **理论可追溯**：内置技能把心理学和认知科学中的常见模型转成可检查的状态文件，而不是让 LLM 凭空发挥。


Skill 目录结构
----------------

内置技能位于包内目录，自定义技能位于工作区目录，环境模块技能由环境提供：

.. code-block:: text

   # 内置技能
   agentsociety2/agent/skills/
   ├── observation/
   │   ├── SKILL.md
   │   └── scripts/
   │       └── observation.py
   ├── cognition/
   │   ├── SKILL.md
   │   └── scripts/
   │       └── update_cognition.py
   ├── plan/
   │   ├── SKILL.md
   │   └── scripts/
   │       └── ...
   └── memory/
       ├── SKILL.md
       └── scripts/
           └── memory_maintenance.py

   # 自定义技能
   {workspace}/custom/skills/
   └── my_skill/
       ├── SKILL.md
       └── scripts/
           └── my_skill.py

   # 环境模块技能
   {env_module}/skills/
   └── weather_query/
       └── SKILL.md


技能发现优先级
---------------

同名技能的覆盖规则（优先级从高到低）：

1. **builtin** — ``agent/skills/`` 目录下的内置技能，**不可被覆盖或禁用**。
2. **custom** — ``<workspace>/custom/skills/`` 下的自定义技能。
3. **env** — 环境模块通过 ``get_agent_skills_dirs()`` 提供的技能。

自定义技能和环境技能可以互相覆盖，但都不能覆盖内置技能。


Skill 的两种模式
------------------

Skill 与 PersonAgent skills-first 设计一致，支持两种运行模式：

1. **Prompt-only（推荐）**：不声明 ``script``。当模型选择并 activate skill 后，SKILL.md 作为行为指南注入上下文，模型使用内置原子工具（``bash`` / ``codegen`` / ``workspace_*`` 等）完成任务。

2. **Subprocess script（确定性计算/解析用）**：在 frontmatter 中声明 ``script: scripts/xxx.py``，或在 ``scripts/`` 目录下提供 ``<skill_name>.py`` 约定脚本。执行时以子进程运行脚本，参数通过 ``--args-json`` 传入，产物写入 agent workspace（``AGENT_WORK_DIR``）。

子进程执行的环境受到严格限制：

- 环境变量使用白名单机制（ ``ALLOWED_ENV_VARS`` ），只传递 PATH、HOME 等必要变量和 ``SKILL_NAME`` 、 ``SKILL_DIR`` 、 ``AGENT_WORK_DIR`` 。
- 所有 agent 共享全局 ``asyncio.Semaphore`` （默认 16 workers），防止子进程资源争用。
- 脚本执行有超时保护（默认 30 秒）。
- 执行前后会 diff 工作区文件，自动检测新产生的产物文件（artifacts）。


SKILL.md 格式
--------------

每个 skill 目录必须包含 ``SKILL.md``。文件头部使用 YAML frontmatter 描述元数据：

.. code-block:: markdown

   ---
   name: cognition
   description: Update emotions and form intentions from current context
   ---

   # Cognition Skill

   You should analyze the current context and update your emotional state...

字段说明：

.. list-table::
   :widths: 24 76
   :header-rows: 1

   * - 字段
     - 说明
   * - ``name``
     - Skill 名称（唯一标识）。未指定时使用目录名。
   * - ``description``
     - 给模型选择器看的功能描述，尽量具体、可判别。这是模型决定是否激活该技能的关键依据。
   * - ``script``
     - 可选。子进程脚本相对路径（如 ``scripts/update_cognition.py``）。未声明时会尝试自动检测 ``scripts/<skill_name>.py``。

脚本路径必须位于 skill 目录内；运行时仍会做路径越界检查。


SKILL.md 高级特性
-------------------

激活技能时，SKILL.md 正文支持以下动态注入：

占位符替换
^^^^^^^^^^

- ``$ARGUMENTS`` — 替换为 ``activate_skill`` 时传入的 ``arguments`` 字符串。
- ``$1``, ``$2``, ... — 替换为按空格分割的各参数。

命令输出注入
^^^^^^^^^^^^

正文中使用以 ``!`` 开头的反引号命令语法，运行时会执行命令并将输出替换到对应位置。例如：

.. code-block:: markdown

   Current workspace files:
    !`ls -la`

   Recent memory entries:
    !`head -n 5 memory/memory.jsonl`


每步执行流程
--------------

PersonAgent.step() 的工具循环流程如下：

1. **上下文构建**：预读 workspace 文件，准备 system prompt（静态段可缓存 + 动态段）。
2. **注入技能 catalog**：仅 ``name`` + ``description`` + 工作区状态 + 最近工具历史。
3. **LLM 决策**：每轮由 ``acompletion_with_pydantic_validation(ToolDecision)`` 获取工具选择。
4. **分发执行**：运行时按需加载完整 SKILL.md，执行具体工具。
5. **结果回写**：工具结果写入 thread（内存窗口 + 磁盘 JSONL）。
6. **循环/结束**：达到 ``done`` 或轮次上限后结束本 step，并持久化最小会话状态与工具历史。

关键点：

* **技能** 由能力目录、行为规范与可选子进程脚本组成，而不是框架内固定顺序的 pipeline。
* **渐进披露**：先暴露 catalog，激活后再注入全文，用于减少上下文负担。


内置技能详解
-------------

当前包内置四个面向 ``PersonAgent`` 的基础技能。它们共享同一个 workspace，并通过文件约定解耦：一个技能只承诺读写哪些文件，不要求其它技能在同一 step 内必然先运行。

.. list-table::
   :widths: 18 27 27 28
   :header-rows: 1

   * - Skill
     - 主要输入
     - 主要输出
     - 适用场景
   * - ``observation``
     - 环境路由器、Agent Identity
     - ``state/observation.txt``、``state/observation_ctx.json``
     - 需要当前 tick 的新环境事实。
   * - ``cognition``
     - observation、memory、plan、profile
     - ``state/emotion.json``、``state/intention.json``
     - 需要把事实转成情绪、需求压力和下一目标。
   * - ``plan``
     - ``state/intention.json``、observation、已有 plan
     - ``state/plan_state.json``，以及一次 ``codegen`` 环境行动
     - 需要把意图落实为环境动作或多步计划。
   * - ``memory``
     - observation、emotion、intention、plan、工具结果
     - ``state/memory.jsonl``
     - 需要保留值得跨 tick 检索的事件、关系、承诺或结果。

``observation``
^^^^^^^^^^^^^^^

``observation`` 是环境感知层。它提示模型调用 ``codegen``，使用 ``instruction: "<observe>"`` 和当前 agent id 从环境获取最新观察，然后把自然语言观察写入 ``state/observation.txt``，把结构化上下文写入 ``state/observation_ctx.json``。

它的设计约束是“一步内不要反复观察”。环境行动成功或进入 ``in_progress`` 后应结束本 step，在下一个 tick 再观察。这能避免工具循环退化成观察-行动-观察的长链，也让 replay 中每个 tick 的状态边界更清楚。

理论上，它对应具身智能体中的 sense-act 闭环：语言模型不能只依赖 profile 和旧记忆作答，必须定期从环境取回外部事实。它也和 ReAct 一类语言智能体方法相通：推理需要通过外部行动获得新证据，再用新证据校正后续决策。

``cognition``
^^^^^^^^^^^^^

``cognition`` 负责把当前上下文转换为内在状态。其脚本 ``scripts/update_cognition.py`` 提供确定性 baseline：读取已有 workspace 文件，计算 appraisal 变量，生成有连续性约束的情绪强度、mood 层，以及一个基于 TPB 评分的意图。

核心输出：

* ``state/emotion.json``：包含 ``primary``、``mood``、六维强度（``joy``、``sadness``、``fear``、``disgust``、``anger``、``surprise``）、``valence``、``arousal`` 等字段。
* ``state/intention.json``：当前最高优先级目标，包含 ``attitude``、``subjective_norm``、``perceived_control`` 等 Theory of Planned Behavior 字段。

它的理论映射有三层：

* **Appraisal / CPM**：用 novelty、pleasantness、goal conduciveness、urgency、control、norm pressure 等评价变量解释情绪如何从事件意义中产生。
* **OCC/离散情绪标签**：用固定 label 集合给主导情绪命名，方便实验分析和 replay 比较。
* **TPB 意图选择**：把态度、主观规范和感知控制作为候选目标评分的核心项，再让当前情绪影响行动倾向和控制感。

实现上采用保守更新：每个 tick 的情绪强度变化有上限，mood 慢速漂移，profile 中的 personality 可调节反应幅度。这适合仿真，因为它避免 LLM 在相邻 tick 间产生不连续的人格和情绪跳变。

``plan``
^^^^^^^^

``plan`` 把 ``state/intention.json`` 中的目标变成环境动作。简单、熟悉、低风险的目标可以直接用一次 ``codegen`` 执行；复杂或不确定的目标会写入 ``state/plan_state.json``，记录 goal、steps、current_step、status、decision_mode 等字段。

该技能采用双系统决策的工程化近似：

* **System 1**：熟悉、重复、低风险或时间紧迫时，直接产生单步行动，不额外维护 plan。
* **System 2**：新目标、多步骤、高不确定性或目标冲突时，显式维护 ``plan_state.json``。

它还会根据 workspace 中可能出现的低饱腹、低精力、低安全等信号中断计划。中断计划不会简单丢弃，而是可写成 ``status: "interrupted"``、``resumable`` 和 ``resume_conditions``，让后续 tick 可以恢复。

``memory``
^^^^^^^^^^

``memory`` 是经验记忆写入与维护技能。LLM 先判断本 tick 是否有值得记住的内容，再追加一行 JSON 到 ``state/memory.jsonl``。维护脚本 ``scripts/memory_maintenance.py`` 可周期性清理和强化记忆。

推荐写入的内容包括：重要互动、新地点/新人物、强情绪事件、计划完成/失败、显著需求变化、承诺、发现和决策。重复观察、无事件 idle tick 和已被最近记忆覆盖的信息应跳过。

记忆维护结合两个可解释模型：

* **Ebbinghaus-style retention**：按时间衰减，重要性越高衰减越慢。
* **ACT-R base-level activation**：重复呈现或检索会提高激活值，让反复出现的人、地点、规则和承诺更容易保留下来。

这个设计不声称精确复刻人脑记忆，而是在大规模仿真中提供稳定、可调参、可审计的长期记忆近似。


理论依据
---------

这些技能的理论依据被转化为可执行的工程约定：

.. list-table::
   :widths: 24 38 38
   :header-rows: 1

   * - 理论/模型
     - 文献中的核心思想
     - 在 AgentSociety 2 中的落点
   * - ReAct / 语言智能体工具循环
     - 推理与外部行动交替，行动用于查询环境、更新事实、处理异常。
     - ``PersonAgent`` 的 ``ToolDecision`` 循环，以及 ``observation`` / ``plan`` 对 ``codegen`` 的调用。
   * - Component Process Model
     - 情绪来自对事件的连续 appraisal，包括新颖性、愉悦性、目标相关性、控制感和规范意义。
     - ``cognition`` 的 appraisal 变量和情绪强度更新。
   * - Theory of Planned Behavior
     - 意图由 attitude、subjective norm、perceived behavioral control 共同预测。
     - ``state/intention.json`` 的候选目标评分字段。
   * - Dual-process decision making
     - 快速自动加工适合熟悉/低风险情境，慢速审慎加工适合新颖/复杂/冲突情境。
     - ``plan`` 在单步行动与 ``plan_state.json`` 多步计划之间切换。
   * - Ebbinghaus forgetting curve
     - 记忆保留随时间下降，早期遗忘快，后期变慢；指数形式是简单可控的 baseline。
     - ``memory_maintenance.py`` 的 retention 衰减。
   * - ACT-R base-level learning
     - 记忆可得性与频率、近因和呈现间隔有关，重复呈现按幂律项叠加。
     - ``memory`` 的 ``_presentations``、``_access_count``、activation 与 retrieval probability。

.. note::

   这些理论在框架中是“可解释启发式”，不是心理学参数估计器。它们的作用是让仿真行为有连续性、可调性和可复盘性，同时把 LLM 的自由生成限制在可检查的状态文件与工具结果中。


SkillRegistry API
-------------------

``SkillRegistry`` 是技能的发现、管理与执行中心。每个 ``PersonAgent`` 实例持有独立的 registry 副本。

发现与扫描
^^^^^^^^^^

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - 方法
     - 说明
   * - ``scan_builtin()``
     - 扫描内置技能（仅执行一次）。
   * - ``scan_custom(workspace_path)``
     - 扫描自定义技能（``<workspace>/custom/skills/``）。
   * - ``scan_env_skills(skills_dir, env_name)``
     - 扫描环境模块提供的技能。

列出与查询
^^^^^^^^^^

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - 方法
     - 说明
   * - ``list_all()``
     - 返回所有已注册技能（按名称排序）。
   * - ``list_enabled()``
     - 返回所有已启用的技能。
   * - ``list_selection_metadata(names=None)``
     - 返回 catalog 条目（仅 name + description），供模型选择。
   * - ``get_skill_info(name, load_content=True)``
     - 获取指定技能的完整信息。

激活与读取
^^^^^^^^^^

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - 方法
     - 说明
   * - ``activate(name) -> str``
     - 加载并返回 SKILL.md 完整内容（含占位符替换和命令注入）。
   * - ``read(name, relative_path) -> str``
     - 读取技能目录内的文件（含路径越界保护）。

执行
^^^^^

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - 方法
     - 说明
   * - ``execute(skill_name, args, agent_work_dir, timeout_sec=30)``
     - 执行技能脚本。有 script 则子进程执行；无 script 返回空成功。返回包含 ``ok``、``exit_code``、``stdout``、``stderr``、``artifacts`` 等字段的字典。

状态管理
^^^^^^^^

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - 方法
     - 说明
   * - ``enable(name)``
     - 启用技能。
   * - ``disable(name)``
     - 禁用技能（内置技能不可禁用）。
   * - ``reload_skill(name)``
     - 热重载技能元数据，清除缓存的 SKILL.md 内容。
   * - ``remove_custom(name)``
     - 从注册表移除自定义技能（不删除磁盘文件）。
   * - ``sync_enabled_from(source)``
     - 从另一个 registry 同步启用状态。

SkillInfo 数据类
^^^^^^^^^^^^^^^^

.. code-block:: python

   @dataclass
   class SkillInfo:
       name: str               # 技能名称
       description: str        # 功能描述
       script: str             # 脚本相对路径（如 scripts/update_cognition.py）
       source: str             # 来源: builtin | custom | env:<name>
       path: str               # 技能目录的绝对路径
       enabled: bool           # 是否启用
       skill_md: str           # SKILL.md 缓存内容
       skill_md_loaded: bool   # SKILL.md 是否已加载


AgentSkillRuntime
-------------------

``AgentSkillRuntime`` 是将 workspace 管理、skill 执行、日志记录集中在一起的组件。PersonAgent 通过组合使用，避免 agent 主体过度膨胀。

Workspace 管理
^^^^^^^^^^^^^^

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - 方法
     - 说明
   * - ``ensure_agent_work_dir(env_obj)``
     - 确保工作目录存在（形如 ``<run_dir>/agents/agent_0001``）。
   * - ``ensure_standard_workspace_dirs()``
     - 创建标准目录结构（state/、memory/、input/、custom/skills/、.runtime/logs/）。
   * - ``workspace_root()``
     - 返回工作区根路径。
   * - ``workspace_read(relative_path)``
     - 读取工作区文件（含越界保护）。
   * - ``workspace_write(relative_path, content)``
     - 写入工作区文件。
   * - ``workspace_exists(relative_path)``
     - 检查文件是否存在。
   * - ``workspace_delete(relative_path)``
     - 删除文件。
   * - ``workspace_list(relative_path=".")``
     - 列出目录下所有文件。

日志与持久化
^^^^^^^^^^^^

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - 方法
     - 说明
   * - ``append_thread_message(role, content, tick, t)``
     - 追加 thread 消息（磁盘 JSONL + 内存窗口）。
   * - ``read_recent_thread_messages(limit=40)``
     - 读取最近 N 条 thread 消息。
   * - ``append_tool_log(entry)``
     - 追加工具调用日志。
   * - ``read_recent_tool_logs(limit=20)``
     - 读取最近 N 条工具日志。
   * - ``persist_session_state(tick, t, selected_skills, activated_skills)``
     - 持久化会话状态。
   * - ``append_step_replay(tick, t, selected_skills, tool_history, step_end_reason)``
     - 追加步骤回放记录。

上下文维护
^^^^^^^^^^

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - 方法
     - 说明
   * - ``refresh_workspace_documents()``
     - 刷新 AGENT.md 和 AGENT_FILES.md。
   * - ``sync_state_to_context()``
     - 将 ``state/*.json`` 同步到 AGENT.md。
   * - ``build_workspace_summary()``
     - 构建 workspace 摘要。
   * - ``auto_update_agent_context(skill_name, tool_result, args)``
     - 根据工具执行结果自动更新上下文。
   * - ``build_file_manifest()``
     - 构建文件清单。
   * - ``write_file_manifest()``
     - 将文件清单写入 AGENT_FILES.md。

行为追踪
^^^^^^^^

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - 方法
     - 说明
   * - ``emit_behavior_event(event_type, data, tick, trace_id, span_id, ...)``
     - 发送行为追踪事件（step_start、tool_call 等）。
   * - ``get_behavior_summary(limit=100)``
     - 获取行为事件统计摘要。


Memory 语义
------------

``PersonAgent`` 中有两类容易混淆的记忆：

* ``AGENT_MEMORY.md`` 是运行时维护的会话摘要，保存当前任务、已完成动作和错误等信息，主要服务长线程压缩与恢复。
* ``state/memory.jsonl`` 是 ``memory`` 技能维护的经验记忆，保存人物在仿真中值得跨 tick 检索的事件、关系、地点、承诺和计划结果。

``memory`` 技能不是每步固定执行的收尾层。是否写入 ``state/memory.jsonl``，由工具循环根据当前事件是否值得保留来决定。这样可以减少重复记忆，也让长期记忆更像“重要经验”而不是完整日志。


运行时管理 API
----------------

后端提供 Agent Skills 管理接口（前缀 ``/api/v1/agent-skills``）：

* ``GET /list``：列出技能（builtin + custom）
* ``POST /enable``：启用指定技能（内置技能始终启用）
* ``POST /disable``：禁用指定自定义/环境技能（内置技能不可禁用）
* ``POST /scan``：扫描 ``{workspace}/custom/skills``
* ``POST /import``：从外部目录导入技能
* ``POST /create``：在线创建新技能（``SKILL.md`` + 可选脚本）
* ``POST /upload``：上传 zip 包导入技能
* ``POST /reload``：热重载单个技能
* ``POST /remove``：删除自定义技能
* ``GET /{name}/info``：查看技能详细信息（含 SKILL.md 内容）

这些接口同时被 VS Code 扩展与手动调试流程使用。


自定义 Skill 最小示例
----------------------

目录：

.. code-block:: text

   {workspace}/custom/skills/hello_skill/
   ├── SKILL.md
   └── scripts/
       └── hello_skill.py

``SKILL.md``：

.. code-block:: markdown

   ---
   name: hello_skill
   description: Add a short greeting into step log
   ---

   # Hello Skill

   Write a greeting to the workspace.

``scripts/hello_skill.py``：

.. code-block:: python

   import argparse
   import json
   from pathlib import Path

   def main() -> int:
       parser = argparse.ArgumentParser()
       parser.add_argument("--args-json", default="{}")
       ns = parser.parse_args()
       args = json.loads(ns.args_json or "{}")
       result = {"ok": True, "summary": "hello_skill: greeted", "tick": args.get("tick")}
       Path("hello_skill.txt").write_text("hello_skill: greeted", encoding="utf-8")
       print(json.dumps(result, ensure_ascii=False))
       return 0

   if __name__ == "__main__":
       raise SystemExit(main())

导入并启用后，主 LLM 会在合适上下文中选择它执行。


最佳实践
---------

1. ``description`` 写成"触发条件 + 输出结果"，便于模型选择器判断。
2. 若依赖其它 skill，在正文写清并引导先 ``activate_skill``。
3. Skill 代码尽量幂等，避免重复执行造成状态污染。
4. 对关键技能保留清晰日志，便于复盘每步选择与执行。
5. 优先使用 Prompt-only 模式，只在需要确定性计算时才用 Subprocess script。
6. 脚本中通过 ``--args-json`` 接收参数，输出以 JSON 打印到 stdout，产物写入 ``AGENT_WORK_DIR``。


参考
------

* :doc:`agents` - PersonAgent 使用说明
* :doc:`api/skills` - SkillRegistry API
* :doc:`development` - 开发指南

外部理论参考：

* ReAct: Synergizing Reasoning and Acting in Language Models, Yao et al. (2022): https://arxiv.org/abs/2210.03629
* Ajzen, I. (1991). The Theory of Planned Behavior: https://doi.org/10.1016/0749-5978(91)90020-T
* Scherer, K. R. (2001). Appraisal considered as a process of multilevel sequential checking. In *Appraisal Processes in Emotion*.
* Murre, J. M. J. and Dros, J. (2015). Replication and Analysis of Ebbinghaus' Forgetting Curve: https://doi.org/10.1371/journal.pone.0120644
* Anderson, J. R. and Schooler, L. J. (1991). Reflections of the Environment in Memory: https://doi.org/10.1111/j.1467-9280.1991.tb00174.x
* Evans, J. S. B. T. (2008). Dual-processing accounts of reasoning, judgment, and social cognition: https://doi.org/10.1146/annurev.psych.59.103006.093629
