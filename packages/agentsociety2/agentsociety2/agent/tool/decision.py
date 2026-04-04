"""工具决策模型。

定义 LLM 输出的工具决策结构。
"""

from typing import Any

from pydantic import BaseModel, Field


class ToolDecision(BaseModel):
    """单轮工具决策输出模型。

    由 LLM 生成并通过 Pydantic 校验，作为工具循环的唯一执行输入。

    :ivar tool_name: 工具名称，必须是有效工具之一。
    :ivar arguments: 工具参数字典。
    :ivar done: 是否结束当前仿真步。
    :ivar summary: 执行摘要。
    """

    tool_name: str = Field(
        description=(
            "Exactly one of: activate_skill, read_skill, execute_skill, workspace_read, workspace_write, "
            "workspace_list, enable_skill, disable_skill, bash, glob, grep, codegen, batch, done. "
            "activate_skill with arguments.skill_name set to the skill name."
        )
    )
    arguments: dict[str, Any] = Field(default_factory=dict)
    done: bool = Field(
        default=False,
        description="Set true when this simulation step should end after the current tool runs.",
    )
    summary: str = ""
