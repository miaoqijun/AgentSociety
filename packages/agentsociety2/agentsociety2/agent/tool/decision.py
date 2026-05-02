"""工具决策模型。

定义 LLM 输出的工具决策结构。

.. important::
   这里不对 ``tool_name`` 做 ``Literal[...]`` 级别的强校验：LLM 偶发的拼写/变形会触发
   Pydantic ValidationError，进而引发重试，浪费 token。

   - **结构校验**：交给 Pydantic（字段存在、类型正确、extra forbid）
   - **语义校验**：在运行时执行（PersonAgent 工具循环）并返回可恢复的错误对象
"""

from typing import Any

import json_repair
from pydantic import BaseModel, ConfigDict, Field, model_validator


VALID_TOOL_NAMES = (
    "activate_skill",
    "read_skill",
    "execute_skill",
    "workspace_read",
    "workspace_write",
    "workspace_list",
    "bash",
    "glob",
    "grep",
    "codegen",
    "batch",
    "done",
    "finish",
)


class ToolDecision(BaseModel):
    """单轮工具决策输出模型。

    由 LLM 生成并通过 Pydantic 校验，作为工具循环的唯一执行输入。

    :ivar tool_name: 工具名称，必须是有效工具之一。
    :ivar arguments: 工具参数字典。
    :ivar done: 是否结束当前仿真步。
    :ivar summary: 执行摘要。
    """

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _coerce_llm_field_shapes(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw = {str(k): v for k, v in data.items()}
        for wrap in ("tool_decision", "data", "result", "output", "response"):
            inner = raw.get(wrap)
            if isinstance(inner, dict) and any(
                str(k).lower()
                in (
                    "tool_name",
                    "toolname",
                    "tool",
                    "name",
                    "action",
                )
                for k in inner
            ):
                raw = {str(k): v for k, v in inner.items()}
                break
        lower = {str(k).lower(): k for k in raw}

        def pick(*keys: str):
            for k in keys:
                if k in raw:
                    return raw[k]
                lk = k.lower()
                if lk in lower:
                    return raw[lower[lk]]
            return None

        out: dict[str, Any] = {}
        tn = pick("tool_name", "toolName", "tool", "name", "action")
        if tn is not None:
            out["tool_name"] = tn if isinstance(tn, str) else str(tn)

        args = pick("arguments", "args", "parameters", "params", "input", "tool_input")
        if args is None:
            out["arguments"] = {}
        elif isinstance(args, str):
            s = args.strip()
            if not s:
                out["arguments"] = {}
            else:
                try:
                    parsed = json_repair.loads(s)
                    out["arguments"] = parsed if isinstance(parsed, dict) else {}
                except Exception:
                    out["arguments"] = {}
        elif isinstance(args, dict):
            out["arguments"] = args
        else:
            out["arguments"] = {}

        d = pick("done", "is_done", "finished", "complete")
        if d is None:
            out["done"] = False
        elif isinstance(d, bool):
            out["done"] = d
        elif isinstance(d, (int, float)):
            out["done"] = bool(d)
        else:
            ds = str(d).strip().lower()
            out["done"] = ds in ("true", "yes", "1", "y", "on")

        summ = pick("summary", "message", "content", "text", "reason", "rationale")
        out["summary"] = "" if summ is None else str(summ)

        return out

    tool_name: str = Field(
        description=(
            "Exactly one of: activate_skill, read_skill, execute_skill, workspace_read, workspace_write, "
            "workspace_list, bash, glob, grep, codegen, batch, done, finish. "
            "Use finish or done with summary when no further tools are needed (text-only completion). "
            "activate_skill with arguments.skill_name set to the skill name."
        )
    )
    arguments: dict[str, Any] = Field(default_factory=dict)
    done: bool = Field(
        default=False,
        description="Set true when this simulation step should end after the current tool runs.",
    )
    summary: str = ""
