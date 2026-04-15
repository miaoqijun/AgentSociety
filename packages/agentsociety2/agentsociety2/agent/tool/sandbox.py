"""轻量级工作区隔离模块。

提供进程级别的安全隔离，包括：
- 工作目录限制
- 资源使用限制
- 命令安全检查
"""

from __future__ import annotations

import os
import resource
import shlex
from pathlib import Path
from typing import Optional


class SecurityError(Exception):
    """安全相关错误。"""
    pass


class WorkspaceSandbox:
    """轻量级工作区隔离。
    
    限制进程只能访问指定的工作目录，并设置资源使用限制。
    
    Example:
        sandbox = WorkspaceSandbox(workspace)
        
        # 验证路径
        safe_path = sandbox.validate_path("state/test.json")
        
        # 验证命令
        if sandbox.is_command_safe("ls -la"):
            ...
    """
    
    # 危险命令黑名单
    BLOCKED_COMMANDS = {
        "rm -rf /",
        "rm -rf /*",
        ":(){ :|:& };:",  # fork bomb
        "mkfs",
        "dd if=/dev/zero",
        "> /dev/sda",
        "> /dev/hda",
    }
    
    # 危险命令前缀
    BLOCKED_PREFIXES = {
        "sudo ",
        "su ",
        "chmod 777",
        "chmod -R 777",
        "chown root",
    }
    
    # 危险命令包含
    BLOCKED_CONTAINS = {
        "/dev/sd",
        "/dev/hd",
        "/etc/passwd",
        "/etc/shadow",
        "~/.ssh",
        "curl | bash",
        "wget | bash",
    }
    
    def __init__(
        self,
        workspace: Path,
        allowed_paths: Optional[list[Path]] = None,
    ):
        """初始化工作区沙箱。
        
        :param workspace: 工作区根目录。
        :param allowed_paths: 额外允许访问的路径列表。
        """
        self.workspace = workspace.resolve()
        self.allowed_paths = [p.resolve() for p in (allowed_paths or [])]
    
    def validate_path(self, path: str) -> Path:
        """验证路径是否在工作区内。
        
        :param path: 相对或绝对路径。
        :return: 解析后的绝对路径。
        :raises SecurityError: 如果路径逃逸工作区。
        """
        # 处理相对路径
        if path.startswith("/"):
            target = Path(path).resolve()
        else:
            target = (self.workspace / path).resolve()
        
        # 检查是否在工作区内
        if self._is_path_allowed(target):
            return target
        
        raise SecurityError(f"Path escapes workspace: {path}")
    
    def _is_path_allowed(self, target: Path) -> bool:
        """检查路径是否在允许列表中。"""
        target_str = str(target)
        
        # 检查工作区
        if target_str.startswith(str(self.workspace)):
            return True
        
        # 检查额外允许的路径
        for allowed in self.allowed_paths:
            if target_str.startswith(str(allowed)):
                return True
        
        return False
    
    def is_command_safe(self, command: str) -> bool:
        """检查命令是否安全。
        
        :param command: 要检查的命令。
        :return: 如果命令安全返回 True。
        """
        cmd_lower = command.lower().strip()
        
        # 检查完全匹配的黑名单
        for blocked in self.BLOCKED_COMMANDS:
            if blocked.lower() in cmd_lower:
                return False
        
        # 检查危险前缀
        for prefix in self.BLOCKED_PREFIXES:
            if cmd_lower.startswith(prefix.lower()):
                return False
        
        # 检查危险内容
        for dangerous in self.BLOCKED_CONTAINS:
            if dangerous.lower() in cmd_lower:
                return False
        
        return True
    
    def validate_command(self, command: str) -> str:
        """验证命令安全性并返回安全的命令。
        
        :param command: 要验证的命令。
        :return: 通过验证的命令。
        :raises SecurityError: 如果命令不安全。
        """
        if not self.is_command_safe(command):
            raise SecurityError(f"Blocked command: {command[:50]}...")
        return command


def set_process_limits(
    cpu_seconds: int = 30,
    memory_mb: int = 512,
    max_files: int = 100,
) -> None:
    """设置当前进程的资源限制。
    
    用于在子进程执行前限制资源使用。
    
    :param cpu_seconds: CPU 时间限制（秒）。
    :param memory_mb: 内存限制（MB）。
    :param max_files: 最大打开文件数。
    """
    # CPU 时间限制
    resource.setrlimit(
        resource.RLIMIT_CPU,
        (cpu_seconds, cpu_seconds),
    )
    
    # 内存限制（虚拟内存）
    memory_bytes = memory_mb * 1024 * 1024
    resource.setrlimit(
        resource.RLIMIT_AS,
        (memory_bytes, memory_bytes),
    )
    
    # 文件描述符限制
    resource.setrlimit(
        resource.RLIMIT_NOFILE,
        (max_files, max_files),
    )


def get_safe_env(base_env: dict[str, str], allowed: set[str]) -> dict[str, str]:
    """从环境变量中过滤出允许的变量。
    
    :param base_env: 原始环境变量字典。
    :param allowed: 允许的环境变量名集合。
    :return: 过滤后的环境变量字典。
    """
    return {
        k: v for k, v in base_env.items()
        if k in allowed
    }
