Agent 模块
==========

本模块提供智能体的核心类和数据模型。

核心类
------

AgentBase
~~~~~~~~~

.. autoclass:: agentsociety2.agent.base.AgentBase
   :members:
   :undoc-members:
   :show-inheritance:

PersonAgent
~~~~~~~~~~~

.. autoclass:: agentsociety2.agent.person.PersonAgent
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

数据模型
--------

LLMInteractionHistory
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: agentsociety2.agent.base.LLMInteractionHistory
   :members:
   :undoc-members:

``AgentBase`` 只规定智能体必须具备的最小生命周期接口。``PersonAgent`` 在此基础上增加了 workspace、技能目录、工具循环、检查点与上下文压缩等运行时能力。

如果只是扩展人物行为，优先新增或修改 Agent Skill；只有需要改变智能体生命周期、状态机或外部系统调用方式时，才继承 ``AgentBase`` / ``PersonAgent`` 创建新类。技能系统的设计说明见 :doc:`/agent_skills`，API 参考见 :doc:`/api/skills`。
