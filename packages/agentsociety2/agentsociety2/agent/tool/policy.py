"""工具执行策略（policy-first 拦截）。

本模块提供统一的工具执行护栏，将「是否允许执行某个工具」从
:class:`~agentsociety2.agent.person.PersonAgent` 主流程中抽离，以获得更清晰的边界、
更一致的失败语义，以及更容易的单元测试。

该 policy **只做判定**，不执行 I/O；调用方应把返回的结构化错误对象写入 thread 作为
``TOOL_RESULT_JSON``，让模型在同一步内自我纠错。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from agentsociety2.agent.tool.security import BashSecurityChecker


def _as_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


@dataclass(frozen=True)
class ToolPolicyContext:
    """Policy 判定所需的最小上下文。

    :param active_skill_scope: 当前 active scope（skill name），供日志/错误信息使用。
    :param workspace_root: workspace 根路径（用于 bash 安全检查的路径上下文）。
    """

    active_skill_scope: str
    workspace_root: str = ""


class ToolPolicy:
    """统一的 tool 执行拦截器。"""

    def __init__(self) -> None:
        self._bash_checker = BashSecurityChecker()

    def check(
        self, *, action: str, args: Any, ctx: ToolPolicyContext
    ) -> dict[str, Any] | None:
        """检查某次工具调用是否允许。

        :param action: 工具名称。
        :param args: 工具参数（LLM 输出，可能不是 dict）。
        :param ctx: policy 上下文。
        :returns: None 表示允许；否则返回结构化错误对象（可直接写入 ``TOOL_RESULT_JSON``）。
        """
        action = str(action or "").strip()
        if not action:
            return {"action": action, "ok": False, "error": "empty tool_name"}

        if action == "bash":
            d = _as_dict(args)
            command = str(d.get("command", "") or d.get("cmd", "") or "").strip()
            if not command:
                return {"action": action, "ok": False, "error": "empty command"}
            ok, reason = self._bash_checker.check(
                command, workspace=ctx.workspace_root or None
            )
            if not ok:
                return {
                    "action": action,
                    "ok": False,
                    "error": f"blocked: {reason}",
                    "policy": {"kind": "bash_security", "reason": reason},
                }

        return None
