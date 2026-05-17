Skills 模块
============

本页分为两部分：

* **Research Skills**：``agentsociety2.skills`` 下的科研工作流模块。
* **Agent Skills**：``agentsociety2.agent.skills`` 下的 PersonAgent 技能注册与运行时机制。

Research Skills
---------------

总入口
~~~~~~

.. automodule:: agentsociety2.skills
   :members:

analysis
~~~~~~~~

.. automodule:: agentsociety2.skills.analysis
   :members:

experiment
~~~~~~~~~~

.. automodule:: agentsociety2.skills.experiment
   :members:

hypothesis
~~~~~~~~~~

.. automodule:: agentsociety2.skills.hypothesis
   :members:

literature
~~~~~~~~~~

.. automodule:: agentsociety2.skills.literature
   :members:

paper
~~~~~

.. automodule:: agentsociety2.skills.paper
   :members:

.. note::

   当前仓库中可公开使用的 research skills 模块为 ``analysis``、``experiment``、
   ``hypothesis``、``literature``、``paper``。``web_research`` 目录当前没有保留
   可读源码，因此未列为文档 API 表面。

Agent Skills
------------

本模块提供智能体技能的注册与管理，支持渐进式加载。

SkillRegistry
~~~~~~~~~~~~~

.. autoclass:: agentsociety2.agent.skills.SkillRegistry
   :members:
   :undoc-members:
   :show-inheritance:

SkillInfo
~~~~~~~~~

.. autoclass:: agentsociety2.agent.skills.SkillInfo
   :members:
   :undoc-members:

工具函数
~~~~~~~~

.. autofunction:: agentsociety2.agent.skills.get_skill_registry

SKILL.md Frontmatter
~~~~~~~~~~~~~~~~~~~~

SKILL.md 文件使用 YAML frontmatter 声明 skill 元信息：

.. code-block:: yaml

   ---
   name: my_skill
   description: 这是一个示例 skill
   script: scripts/my_skill.py
   ---

**解析进 catalog 的字段**：``name``、``description``。
``script`` 为可选子进程脚本路径；未声明时会尝试按 ``scripts/<name>.py`` 自动识别。环境交互走工具 ``codegen``，不经 skill 的 execute 分支。
