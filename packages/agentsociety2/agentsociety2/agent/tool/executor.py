"""工具执行器。

在 Agent workspace 内安全执行 bash、codegen、glob、grep。
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, Callable, Coroutine

from agentsociety2.agent.tool.security import BashSecurityChecker
from agentsociety2.logger import get_logger

logger = get_logger()


class ToolExecutor:
    """在 Agent workspace 内执行工具。

    提供安全约束，防止危险操作。

    :ivar workspace: Workspace 根目录。
    :ivar codegen_ctx: codegen 上下文覆盖。
    :ivar ask_fn: 环境 ask 函数。
    :ivar retries: Bash 超时重试次数。
    :ivar security_checker: Bash 安全检查器。
    """

    def __init__(
        self,
        workspace: Path,
        codegen_ctx: dict[str, Any] | None = None,
        ask_fn: Callable[..., Coroutine[Any, Any, tuple[dict, str]]] | None = None,
        retries: int = 2,
    ):
        """初始化工具执行器。

        :param workspace: Workspace 根目录。
        :param codegen_ctx: codegen 上下文覆盖。
        :param ask_fn: 环境 ask 函数。
        :param retries: Bash 超时重试次数。
        """
        self.workspace = workspace
        self.codegen_ctx = codegen_ctx or {}
        self.ask_fn = ask_fn
        self.retries = retries
        self._security_checker = BashSecurityChecker()

    async def bash(self, cmd: str, timeout: int = 30) -> dict[str, Any]:
        """在 workspace 内执行 bash 命令。

        :param cmd: Bash 命令。
        :param timeout: 超时秒数。
        :return: {ok, exit_code, stdout, stderr}
        :rtype: dict[str, Any]
        """
        cmd = cmd.strip()
        if not cmd:
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "empty command",
            }

        # 绝对路径检查
        if re.search(r"(^|[\s\\'\"();|&])\/", cmd):
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "blocked: absolute path",
            }

        # 父目录遍历检查
        if "../" in cmd or "/.." in cmd or "..\\\\" in cmd:
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "blocked: parent traversal",
            }

        # 使用 BashSecurityChecker 进行安全检查
        is_safe, reason = self._security_checker.check(cmd)
        if not is_safe:
            return {
                "ok": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"blocked: {reason}",
            }

        for attempt in range(self.retries + 1):
            proc = await asyncio.create_subprocess_exec(
                "bash",
                "-c",
                cmd,
                cwd=str(self.workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                return {
                    "ok": (proc.returncode or 0) == 0,
                    "exit_code": proc.returncode or 0,
                    "stdout": out.decode("utf-8", errors="replace"),
                    "stderr": err.decode("utf-8", errors="replace"),
                }
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                if attempt < self.retries:
                    logger.warning(f"Bash timeout; retry {attempt + 1}/{self.retries}")
                    await asyncio.sleep(1.0)
                    continue
                return {"ok": False, "exit_code": -1, "stdout": "", "stderr": "timeout"}

        return {"ok": False, "exit_code": -1, "stdout": "", "stderr": "error"}

    async def codegen(
        self, instruction: str, ctx: dict[str, Any], template: bool = False
    ) -> dict[str, Any]:
        """通过环境执行 codegen 指令。

        :param instruction: 指令文本。
        :param ctx: 上下文对象。
        :param template: 是否使用模板模式。
        :return: {ok, stdout, stderr, ctx}
        :rtype: dict[str, Any]
        """
        if self.ask_fn is None:
            return {"ok": False, "stdout": "", "stderr": "no environment"}
        if not instruction.strip():
            return {"ok": False, "stdout": "", "stderr": "empty instruction"}

        merged = {**ctx, **self.codegen_ctx}
        updated, answer = await self.ask_fn(
            ctx=merged, instruction=instruction, readonly=False, template_mode=template
        )
        return {"ok": True, "stdout": answer, "stderr": "", "ctx": updated}

    def glob(self, pattern: str, root: str = ".") -> dict[str, Any]:
        """在 workspace 内执行 glob 搜索。

        :param pattern: Glob 模式。
        :param root: 相对根目录。
        :return: {ok, count, matches, error}
        :rtype: dict[str, Any]
        """
        root_path = (self.workspace / (root or ".")).resolve()
        if root_path != self.workspace and self.workspace not in root_path.parents:
            return {
                "ok": False,
                "error": "Path escapes workspace",
                "count": 0,
                "matches": [],
            }
        if not root_path.exists():
            return {"ok": True, "count": 0, "matches": []}
        matches = [
            str(p.relative_to(self.workspace))
            for p in root_path.glob(pattern or "**/*")
            if p.is_file()
        ]
        return {"ok": True, "count": len(matches), "matches": sorted(matches)}

    def grep(
        self,
        pattern: str,
        root: str = ".",
        file_pattern: str = "*",
        max_files: int = 2000,
        max_matches: int = 1000,
        max_bytes: int = 2 * 1024 * 1024,
    ) -> dict[str, Any]:
        """在 workspace 内执行内容搜索。

        :param pattern: 正则模式。
        :param root: 相对根目录。
        :param file_pattern: 文件 glob 模式。
        :param max_files: 最大扫描文件数。
        :param max_matches: 最大返回匹配数。
        :param max_bytes: 最大文件大小。
        :return: {ok, count, matches, truncated, error}
        :rtype: dict[str, Any]
        """
        root_path = (self.workspace / (root or ".")).resolve()
        if root_path != self.workspace and self.workspace not in root_path.parents:
            return {
                "ok": False,
                "error": "Path escapes workspace",
                "count": 0,
                "matches": [],
                "truncated": False,
            }

        try:
            rx = re.compile(pattern)
        except re.error as e:
            return {
                "ok": False,
                "error": f"Invalid regex: {pattern}",
                "count": 0,
                "matches": [],
                "truncated": False,
            }

        walker = root_path.rglob(file_pattern) if file_pattern else root_path.rglob("*")
        matches = []
        files_scanned = 0
        truncated = False

        for path in walker:
            if not path.is_file():
                continue
            if files_scanned >= max_files:
                truncated = True
                break
            try:
                if path.stat().st_size > max_bytes:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            files_scanned += 1
            for line_no, line in enumerate(text.splitlines(), 1):
                if len(matches) >= max_matches:
                    truncated = True
                    break
                if rx.search(line):
                    matches.append(
                        {
                            "path": str(path.relative_to(self.workspace)),
                            "line": line_no,
                            "content": line[:500],
                        }
                    )
            if truncated:
                break

        return {
            "ok": True,
            "count": len(matches),
            "matches": matches,
            "truncated": truncated,
        }
