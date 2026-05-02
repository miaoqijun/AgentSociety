Agent Skills 模块
==================

本模块提供智能体技能的注册与管理，支持渐进式加载。

SkillRegistry
-------------

.. autoclass:: agentsociety2.agent.skills.SkillRegistry
   :members:
   :undoc-members:
   :show-inheritance:

SkillInfo
---------

.. autoclass:: agentsociety2.agent.skills.SkillInfo
   :members:
   :undoc-members:

工具函数
--------

.. autofunction:: agentsociety2.agent.skills.get_skill_registry

SKILL.md Frontmatter
--------------------

SKILL.md 文件使用 YAML frontmatter 声明 skill 元信息：

.. code-block:: yaml

   ---
   name: my_skill
   description: 这是一个示例 skill
   ---

**解析进 catalog 的字段**：``name``、``description``。
子进程脚本通过约定路径 ``scripts/<name>.py`` 自动识别。环境交互走工具 ``codegen``，不经 skill 的 execute 分支。
