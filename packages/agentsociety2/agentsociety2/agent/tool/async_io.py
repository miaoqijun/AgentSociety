"""异步文件 I/O 操作。

提供 :class:`~agentsociety2.agent.tool.async_io.AsyncWorkspaceIO`，用于异步读写文件，
避免阻塞事件循环。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

from agentsociety2.logger import get_logger
from agentsociety2.agent.tool.utils import json_parse

logger = get_logger()

# 尝试导入 aiofiles，如果不可用则使用线程池回退
try:
    import aiofiles
    import aiofiles.os

    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False
    logger.warning("aiofiles not available, async I/O will use thread pool fallback")


class AsyncWorkspaceIO:
    """异步文件 I/O 操作器。

    提供异步的文件读写操作，避免阻塞事件循环。
    优先使用 aiofiles，不可用时回退到线程池执行。

    :param workspace_root: workspace 根目录路径。
    """

    def __init__(self, workspace_root: Path) -> None:
        self._root = workspace_root
        self._executor: Optional[asyncio.Executor] = None

    def _resolve(self, path: str) -> Path:
        """解析相对路径并做越界保护。"""
        target = (self._root / path).resolve()
        if target != self._root and self._root not in target.parents:
            raise ValueError(f"Path escapes workspace: {path}")
        return target

    async def read(self, relative_path: str) -> str:
        """异步读取文件内容。"""
        target = self._resolve(relative_path)

        if HAS_AIOFILES:
            if not await aiofiles.os.path.exists(target):
                return ""
            if await aiofiles.os.path.isdir(target):
                return ""
            async with aiofiles.open(target, mode="r", encoding="utf-8") as f:
                return await f.read()
        else:
            # 回退到线程池
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(self._executor, self._sync_read, target)

    def _sync_read(self, path: Path) -> str:
        """同步读取文件（用于线程池回退）。"""
        if not path.exists() or path.is_dir():
            return ""
        return path.read_text(encoding="utf-8")

    async def write(self, relative_path: str, content: str) -> str:
        """异步写入文件。"""
        target = self._resolve(relative_path)

        if HAS_AIOFILES:
            # 确保父目录存在
            parent = target.parent
            if not await aiofiles.os.path.exists(parent):
                await asyncio.to_thread(parent.mkdir, parents=True, exist_ok=True)

            async with aiofiles.open(target, mode="w", encoding="utf-8") as f:
                await f.write(content)
            return str(target)
        else:
            # 回退到线程池
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._executor, self._sync_write, target, content
            )

    def _sync_write(self, path: Path, content: str) -> str:
        """同步写入文件（用于线程池回退）。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    async def append(self, relative_path: str, content: str) -> str:
        """异步追加内容到文件。"""
        target = self._resolve(relative_path)

        if HAS_AIOFILES:
            parent = target.parent
            if not await aiofiles.os.path.exists(parent):
                await asyncio.to_thread(parent.mkdir, parents=True, exist_ok=True)

            async with aiofiles.open(target, mode="a", encoding="utf-8") as f:
                await f.write(content)
            return str(target)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._executor, self._sync_append, target, content
            )

    def _sync_append(self, path: Path, content: str) -> str:
        """同步追加文件（用于线程池回退）。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open(mode="a", encoding="utf-8") as f:
            f.write(content)
        return str(path)

    async def append_jsonl(self, relative_path: str, obj: dict[str, Any]) -> str:
        """异步追加 JSON 行到文件。"""
        line = json.dumps(obj, ensure_ascii=False, default=str) + "\n"
        return await self.append(relative_path, line)

    async def exists(self, relative_path: str) -> bool:
        """异步检查文件是否存在。"""
        target = self._resolve(relative_path)

        if HAS_AIOFILES:
            return await aiofiles.os.path.exists(target)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(self._executor, target.exists)

    async def is_file(self, relative_path: str) -> bool:
        """异步检查是否为文件。"""
        target = self._resolve(relative_path)

        if HAS_AIOFILES:
            exists = await aiofiles.os.path.exists(target)
            if not exists:
                return False
            return not await aiofiles.os.path.isdir(target)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(self._executor, target.is_file)

    async def list_files(self, relative_path: str = ".") -> list[str]:
        """异步列出文件（递归）。"""
        root = self._resolve(relative_path)

        if HAS_AIOFILES:
            if not await aiofiles.os.path.exists(root):
                return []
            # aiofiles 不支持 rglob，使用线程池
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._executor, self._sync_list_files, root
            )
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._executor, self._sync_list_files, root
            )

    def _sync_list_files(self, root: Path) -> list[str]:
        """同步列出文件（用于线程池）。"""
        if not root.exists():
            return []
        if root.is_file():
            return [str(root.relative_to(self._root))]
        return sorted(
            str(p.relative_to(self._root)) for p in root.rglob("*") if p.is_file()
        )

    async def read_json(self, relative_path: str, default: Any = None) -> Any:
        """异步读取 JSON 文件。"""
        content = await self.read(relative_path)
        if not content:
            return default
        try:
            return json_parse(content)
        except Exception:
            return default

    async def write_json(
        self, relative_path: str, obj: Any, indent: int | None = 2
    ) -> str:
        """异步写入 JSON 文件。"""
        content = json.dumps(obj, ensure_ascii=False, indent=indent, default=str)
        return await self.write(relative_path, content)

    async def delete(self, relative_path: str) -> bool:
        """异步删除文件。"""
        target = self._resolve(relative_path)

        if HAS_AIOFILES:
            if not await aiofiles.os.path.exists(target):
                return False
            if await aiofiles.os.path.isdir(target):
                return False
            await aiofiles.os.remove(target)
            return True
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(self._executor, self._sync_delete, target)

    def _sync_delete(self, path: Path) -> bool:
        """同步删除文件（用于线程池回退）。"""
        if not path.exists() or path.is_dir():
            return False
        path.unlink()
        return True

    async def ensure_dir(self, relative_path: str) -> None:
        """异步确保目录存在。"""
        target = self._resolve(relative_path)

        if HAS_AIOFILES:
            if not await aiofiles.os.path.exists(target):
                await asyncio.to_thread(target.mkdir, parents=True, exist_ok=True)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self._executor, lambda: target.mkdir(parents=True, exist_ok=True)
            )
