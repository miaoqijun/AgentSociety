Agent Skills（智能体技能）
=================================

概述
------

Agent Skills 是 PersonAgent 的能力插件系统。PersonAgent 本身是轻量编排器，
真正的认知与行为能力由独立 skill 提供（如 observation、needs、cognition、plan、memory）。

当前实现采用两条核心原则：

1. **Metadata-first**：选择阶段只暴露 ``name`` + ``description``，不加载完整正文。
2. **Tool-loop**：每步由模型在工具循环里 ``activate_skill`` / ``read_skill`` / ``execute_skill``，无固定 pipeline 层级。

这意味着：技能是否执行由当前上下文与模型选择决定。


设计目标
---------

* **按需加载**：降低每步不必要的加载与执行开销。
* **可解释选择**：选择依据来自 catalog 中的简短描述，便于调试与治理。
* **热更新友好**：支持运行时扫描、导入、启用/禁用与重载。
* **依赖在文档中说明**：需要其它 skill 时在 SKILL.md 正文写明，由模型按需激活。


Skill 目录结构
----------------

内置技能位于包内目录，自定义技能位于工作区目录：

.. code-block:: text

   agentsociety2/agent/skills/
   ├── observation/
   │   ├── SKILL.md
   │   └── scripts/
   │       └── observation.py
   ├── cognition/
   │   ├── SKILL.md
   │   └── scripts/
   │       └── cognition.py
   └── ...

   {workspace}/custom/skills/
   └── my_skill/
       ├── SKILL.md
       └── scripts/
           └── my_skill.py

Skill 的两种模式（与当前 PersonAgent skills-first 设计一致）：

1. **Prompt-only（推荐）**：不声明 ``script``。当模型选择并 activate skill 后，SKILL.md 作为行为指南注入上下文，模型使用内置原子工具（bash/codegen/workspace_* 等）完成任务。
2. **Subprocess script（确定性计算/解析用）**：在 frontmatter 中声明 ``script: scripts/my_skill.py``。执行时以子进程运行脚本，参数通过 ``--args-json`` 传入，产物写入 agent workspace（``AGENT_WORK_DIR``）。


SKILL.md 格式
--------------

每个 skill 目录应包含 ``SKILL.md``。文件头部使用 YAML frontmatter 描述元数据：

.. code-block:: markdown

   ---
   name: cognition
   description: Update emotions and form intentions from current context
   ---

   # Cognition Skill
   ...

字段说明：

.. list-table::
   :widths: 24 76
   :header-rows: 1

   * - 字段
     - 说明
   * - ``name``
     - Skill 名称（唯一标识）。
   * - ``description``
     - 给选择器看的功能描述，尽量具体、可判别。

可选：包内技能可通过约定 ``scripts/<name>.py`` 提供子进程脚本；框架不在 frontmatter 中解析 ``priority`` / ``requires`` / ``inputs`` / ``outputs`` 等扩展字段。


每步执行流程
--------------

PersonAgent.step() 的流程如下：

1. 注入技能 catalog（仅 ``name`` + ``description``）+ 工作区状态 + 最近工具历史。
2. 进入 tool-loop：模型每轮选择一个工具调用（activate/read/execute/workspace_* 等）。
3. 当调用某个 skill 时，运行时会按需加载完整 SKILL.md 与 skill 目录下的文件。
4. 达到 done 或轮次上限后结束本 step，并持久化最小会话状态与工具历史。

关键点：

* **技能** 由能力目录、行为规范与可选子进程脚本组成，而不是框架内固定顺序的 pipeline。
* **渐进披露**：先暴露 catalog，激活后再注入全文，用于减少上下文负担。


Memory 语义
------------

认知相关技能通常先把内容写入 ``_cognition_memory`` 缓冲：

* 当 ``memory`` 技能在本步被选中执行时，缓冲会被 flush 到长期记忆。
* 当 ``memory`` 未被选中时，缓冲不会丢失，会保留到后续 step。
* 在 Agent ``close()`` 时，会执行兜底 flush，避免遗留缓冲丢失。

因此，memory 行为不再是固定“Finalize 层”，而是由选择结果驱动。


运行时管理 API
----------------

后端提供 Agent Skills 管理接口（前缀 ``/api/v1/agent-skills``）：

* ``GET /list``：列出技能（builtin + custom）
* ``POST /scan``：扫描 ``{workspace}/custom/skills``
* ``POST /import``：从外部目录导入技能
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

1. ``description`` 写成”触发条件 + 输出结果”，便于选择器判断。
2. 若依赖其它 skill，在正文写清并引导先 ``activate_skill``。
3. Skill 代码尽量幂等，避免重复执行造成状态污染。
4. 对关键技能保留清晰日志，便于复盘每步选择与执行。


参考
------

* :doc:`agents` - PersonAgent 使用说明
* :doc:`api/skills` - SkillRegistry API
* :doc:`development` - 开发指南
