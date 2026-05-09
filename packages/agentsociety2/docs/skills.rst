研究技能
========================================

AgentSociety 2 包含一组 LLM 原生的研究技能，用于自动化科学研究工作流。

概述
------------

研究技能模块提供以下功能：

* **文献检索**: 搜索和管理学术论文
* **假设生成**: 从研究问题生成可测试的假设
* **实验设计**: 设计完整的实验配置
* **论文撰写**: 通过 paper-orchestrator skill 套件（重写中）生成 Nature 风格学术论文 PDF
* **数据分析**: 分析实验数据并生成报告
* **智能体处理**: 智能体选择、生成和过滤

Claude Code Skills
--------------------

研究工作流主要通过 Claude Code 的“skills-first”方式提供：
- AgentSociety 内置研究 skills：随 VSCode 插件打包，可在插件树视图中浏览（只读）。
- Agent(Person) 扩展 skills：由后端 `/api/v1/agent-skills/*` 管理，支持扫描/导入/热重载。

* **agentsociety-literature-search** - 文献检索
* **agentsociety-hypothesis** - 假设管理（add, get, list, delete）
* **agentsociety-experiment-config** - 实验配置生成与验证
* **agentsociety-run-experiment** - 实验执行与监控
* **agentsociety-analysis** - 数据分析与跨实验综合
* **agentsociety-paper-orchestrator** - Nature/Science 级论文生成（6-skill 状态机）

Python API
--------------------

研究技能也可以通过 Python API 直接调用。

文献技能 (literature)
~~~~~~~~~~~~~~~~~~~~~~~

文献技能默认使用已经配置好的 ``LITERATURE_SEARCH_API_URL`` 和
``LITERATURE_SEARCH_API_KEY`` 调用统一检索服务。推荐优先使用
``search_literature_and_save``，而不是直接调用底层 ``search_literature``：
前者会把检索结果落到工作区中，确保后续 Agent、Claude Code 和论文写作技能
都能通过本地文件继续引用这些文献。

.. code-block:: python

   from agentsociety2.skills.literature import search_literature_and_save, load_literature_index

   # 搜索并保存文献（默认搜索所有数据源，并更新 papers/literature_index.json）
   result = await search_literature_and_save(
       workspace_path=Path("./workspace"),
       query="agent-based modeling social networks",
       limit=10,
       year_from=2020,      # 可选：年份筛选
       year_to=2024,
       enable_multi_query=True,  # 可选：启用多查询模式
   )

   # 指定数据源搜索
   await search_literature_and_save(
       workspace_path=Path("./workspace"),
       query="machine learning",
       limit=5,
       sources=["local", "arxiv"],  # 可选：指定数据源
   )

   # 加载文献索引
   index = load_literature_index(workspace_path=Path("./workspace"))

**保存结果**:

- 每篇检索结果都会保存为 ``papers/<title>_<timestamp>.md``。
  这个 Markdown 文件是稳定的本地文献笔记，包含标题、检索词、年份、期刊、
  DOI/URL、摘要、作者和相关内容片段。
- ``papers/literature_index.json`` 会同步更新。索引中的 ``file_path``
  指向本地 Markdown 文献笔记，因此插件中的 ``@引用`` 可以复制为
  ``@papers/<title>_<timestamp>.md``，供 Claude Code 或 Agent 读取。
- 重复运行检索时会生成新的本地文献笔记，并追加到索引中，便于保留不同检索轮次的上下文。

**原文下载（由 Claude/Agent 按需执行）**:

文献技能不会在 Python API 中硬编码下载策略。检索结果会尽量保留
``doi``、``url``、``pdf_url``、``full_text_url``、``download_url``、
``open_access``、``best_oa_location`` 等元信息；Claude Code 或 Agent
可以基于这些线索按需下载开放获取原文。

建议的下载约定：

- 原文 PDF 放在 ``papers/full_texts/*.pdf``。
- 优先使用 API 返回的 PDF 直链；arXiv 论文可从 ``/abs/<id>`` 转为
  ``https://arxiv.org/pdf/<id>.pdf``。
- DOI 仅作为落地页线索，不保证能直接得到 PDF；如果需要下载，应确认最终响应确实是 PDF。
- 下载完成后，可在对应索引条目的 ``extra_fields["full_text"]`` 中记录:

  .. code-block:: json

     {
       "status": "downloaded",
       "file_path": "papers/full_texts/example.pdf",
       "source_url": "https://arxiv.org/pdf/2401.01234.pdf"
     }

  如果没有找到开放原文，也可以记录 ``{"status": "no_candidate"}`` 或
  ``{"status": "failed", "reason": "..."}``，便于插件页面显示状态。

.. note::

   许多 CrossRef/OpenAlex 结果只提供 DOI 或落地页，不一定有开放 PDF。
   Claude/Agent 不应绕过出版商权限，也不应把 HTML 落地页当作 PDF 保存。

**数据源**:
- ``local``: RAGFlow 本地知识库
- ``arxiv``: arXiv 预印本平台
- ``crossref``: CrossRef DOI 元数据库
- ``openalex``: OpenAlex 学术图谱 (2.5亿+ 论文)

**配置**:
需要在 ``.env`` 文件中配置 API:

.. code-block:: bash

   LITERATURE_SEARCH_API_URL=http://localhost:8008/api/search
   LITERATURE_SEARCH_API_KEY=lit-your-api-key-here

假设技能 (hypothesis)
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from agentsociety2.skills.hypothesis import add_hypothesis, get_hypothesis, list_hypotheses

   # 添加假设
   add_hypothesis(
       workspace_path=Path("./workspace"),
       hypothesis="网络密度越高，信息传播速度越快"
   )

   # 列出假设
   hypotheses = list_hypotheses(workspace_path=Path("./workspace"))

实验技能 (experiment)
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from agentsociety2.skills.experiment import (
       start_experiment, get_experiment_status,
       get_available_env_modules, get_available_agent_modules
   )

   # 获取可用模块
   env_modules = get_available_env_modules()
   agent_modules = get_available_agent_modules()

   # 启动实验
   await start_experiment(
       workspace_path=Path("./workspace"),
       hypothesis_id="1",
       experiment_id="1"
   )

分析技能 (analysis)
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pathlib import Path

   from agentsociety2.skills.analysis import ContextLoader, DataReader, EDAGenerator

   workspace = Path("./workspace")
   context = ContextLoader(workspace).load_context("1", "1")
   summary = DataReader(
       workspace / "hypothesis_1" / "experiment_1" / "run" / "sqlite.db"
   ).read_full_summary()
   quick_stats = EDAGenerator().generate_quick_stats(
       workspace / "hypothesis_1" / "experiment_1" / "run" / "sqlite.db",
       tables=["agent_profile"],
   )

跨实验对比不再使用独立综合 skill，而是作为
``agentsociety-analysis`` 的 Stage 5 在 Claude Code 中完成。

论文技能 (paper)
~~~~~~~~~~~~~~~~~

论文生成由 6 个 plugin skill 组成的状态机驱动，通过
``paper-orchestrator`` 作为唯一入口点调度。Python 包
``agentsociety2.skills.paper`` 提供非 LLM 逻辑（状态管理、适配器、
LaTeX 编译）。

**Skill 套件：**

- ``agentsociety-paper-orchestrator`` — 状态机内核，读取
  ``paper_state.yaml``，调度 Task subagent，持久化产出
- ``agentsociety-paper-adapter`` — workspace → ResearchPack 标准化
- ``agentsociety-paper-framing`` — storyline_map 生成（问题、角度、贡献类型）
- ``agentsociety-paper-evidence-expansion`` — 证据缺口审计与补全
- ``agentsociety-paper-architecture`` — claim tree + figure-argument map +
  章节大纲 + manuscript 草稿
- ``agentsociety-paper-skeptical-review`` — 3 审稿人评审轮次（significance-calibrator /
  precision-editor / evidence-skeptic）

**状态机阶段：**

``intake → framing → evidence-audit → expansion-plan → manuscript-build →
skeptical-review → revision-router → release-gate``

**持久化布局：**

所有论文状态持久化在 ``<workspace>/paper/`` 下：

- ``paper_meta.yaml`` — 标题、作者、机构
- ``state/`` — ``paper_state.yaml``、``research_pack.json``、``human_gates.yaml``
- ``artifacts/`` — ``storyline_map.json``、``claim_ledger.json``、
  ``evidence_backlog.json``、``figure_argument_map.json``、
  ``manuscript/``（abstract.md, main.md, results/*, discussion.md）
- ``reviews/`` — ``review_round_NNN.yaml``
- ``runs/<TS>/compose/out/paper.pdf`` — 最终交付物

**CLI 入口：**

``$PYTHON_PATH .agentsociety/bin/ags.py paper-orchestrator <subcommand>``

子命令：init-meta, intake, build-pack, framing, evidence, architecture,
review, compile, run-loop, status。别名 ``paper``、``generate-paper``、
``generate_paper`` 均路由至此。

完整工作流示例
------------------------

下面是一个使用 Claude Code Skills 的典型研究工作流：

1. **定义研究话题** - 编辑 ``TOPIC.md``
2. **文献检索** - 使用 ``/agentsociety-literature-search``
3. **创建假设** - 使用 ``/agentsociety-hypothesis add``
4. **配置实验** - 使用 ``/agentsociety-experiment-config validate/prepare/run``
5. **执行实验** - 使用 ``/agentsociety-run-experiment start``
6. **分析结果** - 使用 ``/agentsociety-analysis``
7. **生成论文** - 使用 ``/agentsociety-paper-orchestrator``（别名 ``/paper``）

配置
------------------------

研究技能使用相同的 LLM 配置。可以通过环境变量为特定技能配置不同的模型：

.. code-block:: bash

   # 默认 LLM
   export AGENTSOCIETY_LLM_MODEL="gpt-5.4"

   # 代码生成（实验设计、分析）
   export AGENTSOCIETY_CODER_LLM_MODEL="gpt-5.4"

   # 高频操作（智能体生成）
   export AGENTSOCIETY_NANO_LLM_MODEL="gpt-5.4-nano"

Agent Skills
--------------------

AgentSociety 2 还支持 Agent Skills，这些是 PersonAgent 的认知能力模块：

* **observation** - 环境感知
* **cognition** - 认知与意图
* **plan** - 规划与执行
* **memory** - 记忆管理

详见 :doc:`agent_skills`。

参考
------------------------

* :doc:`cli` - 使用 CLI 运行实验
* :doc:`agent_skills` - Agent Skills 详解
* :doc:`custom_modules` - 创建自定义模块
* :doc:`development` - 开发指南
