"""Bash 命令安全检查模块。

提供统一的 BLOCKED_TOKENS 和 BLOCKED_PATTERNS 定义，
以及 BashSecurityChecker 类用于检测危险命令。

Example:
    from agentsociety2.agent.tool.security import BashSecurityChecker

    checker = BashSecurityChecker()
    is_safe, reason = checker.check("curl http://example.com")
    if not is_safe:
        print(f"Blocked: {reason}")
"""

from __future__ import annotations

import re
import shlex
from typing import Final


#: 被阻止的命令标记（基础黑名单）
BLOCKED_TOKENS: Final[frozenset[str]] = frozenset(
    {
        # 危险操作
        "rm",
        "rmdir",
        # 网络工具
        "curl",
        "wget",
        "nc",
        "ncat",
        "netcat",
        "ssh",
        "scp",
        "rsync",
        "ftp",
        "telnet",
        "nmap",
        # 权限提升
        "sudo",
        "su",
        # 文件权限
        "chmod",
        "chown",
        "chgrp",
        # 系统控制
        "shutdown",
        "reboot",
        "poweroff",
        "halt",
        "init",
        # 磁盘操作
        "mkfs",
        "fdisk",
        "dd",
        # fork bomb
        ":(){",
    }
)


#: 被阻止的命令模式（正则表达式）
BLOCKED_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    # 命令替换 $(...)
    re.compile(r"\$\([^)]*\)"),
    # 命令替换 `...`
    re.compile(r"`[^`]*`"),
    # 变量展开 ${...}
    re.compile(r"\$\{[^}]*\}"),
    # 重定向到设备文件
    re.compile(r">\s*/dev/"),
    # 危险路径操作
    re.compile(r"/\s*\.\.\s*/"),
    # fork bomb 特征
    re.compile(r":\(\)\s*\{"),
    # 管道到 bash/sh
    re.compile(r"\|\s*(ba)?sh\b"),
    # 嵌套命令执行
    re.compile(r"eval\s+"),
)

#: 被阻止的危险子串（路径/敏感文件等）
#:
#: 说明：
#: - 该集合用于补齐“命令本身未必是黑名单 token，但一旦包含这些敏感路径就应拒绝”的场景。
#: - 采用子串匹配（lowercase）以覆盖常见拼接/参数变化。
BLOCKED_SUBSTRINGS: Final[frozenset[str]] = frozenset(
    {
        "/etc/passwd",
        "/etc/shadow",
        "~/.ssh",
        "/dev/sd",
        "/dev/hd",
    }
)


class BashSecurityChecker:
    """Bash 命令安全检查器。

    检测潜在的恶意命令，包括：
    - 黑名单命令（curl、wget、sudo 等）
    - 危险模式（命令替换、变量展开等）
    - 转义绕过尝试

    Example:
        >>> checker = BashSecurityChecker()
        >>> checker.check("ls -la")
        (True, '')
        >>> checker.check("curl http://example.com")
        (False, 'blocked command: curl')
        >>> checker.check("cu\\rl http://example.com")
        (False, 'blocked command: curl')
    """

    def __init__(self, extra_tokens: frozenset[str] | None = None):
        """初始化安全检查器。

        :param extra_tokens: 额外的黑名单命令集合。
        """
        self._blocked_tokens = BLOCKED_TOKENS | (extra_tokens or frozenset())

    def check(self, cmd: str) -> tuple[bool, str]:
        """检查命令是否安全。

        :param cmd: 待检查的 Bash 命令。
        :return: (is_safe, reason) 元组。is_safe 为 True 表示安全，
                 reason 在不安全时说明原因。
        """
        if not cmd or not cmd.strip():
            return True, ""

        # 1. 使用 shlex 解析实际命令（处理转义）
        try:
            tokens = shlex.split(cmd)
        except ValueError as e:
            # 解析失败可能是恶意构造，保守拒绝
            return False, f"invalid shell syntax: {e}"

        # 2. 检查黑名单命令
        for token in tokens:
            # 提取命令名（去掉路径前缀）
            base = token.split("/")[-1].lower()
            if base in self._blocked_tokens:
                return False, f"blocked command: {base}"

        # 3. 检查危险模式
        for pattern in BLOCKED_PATTERNS:
            match = pattern.search(cmd)
            if match:
                return False, f"blocked pattern: {match.group()}"

        # 4. 检查危险子串（敏感路径、设备、密钥等）
        cmd_lower = cmd.lower()
        for s in BLOCKED_SUBSTRINGS:
            if s in cmd_lower:
                return False, f"blocked substring: {s}"

        return True, ""

    def is_safe(self, cmd: str) -> bool:
        """检查命令是否安全（简化接口）。

        :param cmd: 待检查的 Bash 命令。
        :return: True 表示安全，False 表示不安全。
        """
        is_safe, _ = self.check(cmd)
        return is_safe
