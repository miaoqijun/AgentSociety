"""Skill discovery, metadata, and execution.

- ``SKILL.md`` YAML frontmatter: ``name``, ``description``, optional ``script``
- Optional subprocess script: frontmatter ``script`` or ``scripts/<skill_name>.py``
- Catalog shows name + description; full ``SKILL.md`` loads after ``activate_skill``.
- ``enabled`` is toggled only via management API / UI (not in SKILL.md); catalog lists enabled skills only.
- Built-in skills (``source`` is ``builtin``) are always enabled and cannot be disabled.

Module Structure
================

- :class:`SkillInfo`: Skill metadata container
- :class:`SkillRegistry`: Skill registry for discovery, management, and execution

Skill Metadata
==============

Frontmatter uses ``name`` and ``description`` for the selection catalog.
If ``script`` is present, it points to the subprocess script relative to the skill
directory; otherwise ``scripts/<skill_name>.py`` is detected by convention.

Example
=======

SKILL.md::

    ---
    name: cognition
    description: Generate emotion, needs, and intention
    ---

Usage::

    from agentsociety2.agent.skills import SkillRegistry, get_skill_registry

    registry = get_skill_registry()

    # List available skills
    for info in registry.list_all():
        print(f"{info.name}: {info.description}")

    # Activate skill
    content = registry.activate("cognition")

    # Execute skill script
    result = await registry.execute(
        skill_name="memory",
        args={"observation": "..."},
        agent_work_dir=workspace,
    )

Built-in Skills
===============

| Skill | Function |
|-------|----------|
| observation | Fetch environment perception |
| cognition | Generate emotion, needs, intention |
| memory | Long-term event memory |
| plan | Execute intentions via environment |
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentsociety2.agent.config import ALLOWED_ENV_VARS
from agentsociety2.logger import get_logger

logger = get_logger()
_BUILTIN_ROOT = Path(__file__).resolve().parent


@dataclass
class SkillInfo:
    """Skill metadata from SKILL.md (name + description) plus runtime fields."""

    name: str
    description: str = ""
    script: str = ""
    source: str = ""  # builtin | custom | env:<name>
    path: str = ""
    enabled: bool = True
    skill_md: str = ""
    skill_md_loaded: bool = field(default=False, repr=False)

    def copy(self) -> "SkillInfo":
        return SkillInfo(
            name=self.name,
            description=self.description,
            script=self.script,
            source=self.source,
            path=self.path,
            enabled=self.enabled,
            skill_md=self.skill_md,
            skill_md_loaded=self.skill_md_loaded,
        )


# 全局子进程并发限制：所有 agent 的 registry 共享同一个 semaphore，
# 避免 N 个 agent 各自拥有 16 个配额导致 N×16 个子进程。
# 使用懒初始化确保在 asyncio 事件循环启动后才创建。
_global_subprocess_semaphore: asyncio.Semaphore | None = None


def _get_global_subprocess_semaphore() -> asyncio.Semaphore:
    global _global_subprocess_semaphore
    if _global_subprocess_semaphore is None:
        max_workers_str = os.getenv("AGENT_SKILL_SUBPROCESS_MAX_WORKERS", "16")
        try:
            max_workers = max(1, int(max_workers_str))
        except ValueError:
            max_workers = 16
        _global_subprocess_semaphore = asyncio.Semaphore(max_workers)
    return _global_subprocess_semaphore


class SkillRegistry:
    """Registry for skill discovery, management, and execution.

    The SkillRegistry provides:
    - Discovery: Scan skills from builtin, custom, and environment directories
    - Listing: List skills with metadata for model selection
    - Activation: Load and activate skill content on demand
    - Execution: Run skill scripts with argument passing

    Example usage::

        registry = SkillRegistry()
        registry.scan_builtin()

        # List available skills
        for info in registry.list_all():
            print(f"{info.name}: {info.description}")

        # Activate and get skill content
        content = registry.activate("needs")
    """

    def __init__(self) -> None:
        """Initialize a skill registry with built-in skills loaded."""
        self._skills: dict[str, SkillInfo] = {}
        self._builtin_scanned = False
        self.scan_builtin()

    def copy_from(self, other: "SkillRegistry") -> None:
        """从另一个 registry 复制所有技能。

        :param other: 源 registry。
        """
        self._skills = {name: info.copy() for name, info in other._skills.items()}
        self._builtin_scanned = other._builtin_scanned
        self._ensure_builtin_skills_enabled()

    # ---------- discover ----------
    def scan_builtin(self, root: Path = _BUILTIN_ROOT) -> None:
        """Scan built-in skills from the agent/skills directory.

        Built-in skills are always available and cannot be overridden by
        custom or environment skills with the same name.
        """
        if self._builtin_scanned:
            return
        for info in _discover_skills(root, source="builtin"):
            self._skills[info.name] = info
        self._builtin_scanned = True

    def scan_custom(self, workspace_path: str | Path) -> list[str]:
        """Scan custom skills from a workspace directory.

        Looks for skills in `<workspace_path>/custom/skills/`.
        Custom skills can override environment skills but not built-in skills.

        :param workspace_path: Root path containing ``custom/skills/`` directory.
        :returns: List of skill names that were added.
        """
        from agentsociety2.backend.path_security import custom_skills_root

        custom_root = custom_skills_root(str(workspace_path))
        if not custom_root.is_dir():
            return []
        new_names: list[str] = []
        for info in _discover_skills(custom_root, source="custom"):
            # Built-in skills cannot be overridden.
            if (
                info.name in self._skills
                and self._skills[info.name].source == "builtin"
            ):
                continue
            if info.name in self._skills:
                info.enabled = self._skills[info.name].enabled
            self._skills[info.name] = info
            new_names.append(info.name)
        return new_names

    def scan_env_skills(self, skills_dir: Path, env_name: str) -> list[str]:
        """Scan skills from an environment module's skill directory.

        Environment modules can bundle specialized skills via `get_agent_skills_dirs()`.
        These skills are automatically discovered when PersonAgent initializes.

        Environment skills can override other environment skills and custom skills,
        but not built-in skills.

        :param skills_dir: Directory containing skill subdirectories with ``SKILL.md`` files.
        :param env_name: Name of the environment module (for source tracking).
        :returns: List of skill names that were added.

        .. seealso::
           :meth:`agentsociety2.env.base.EnvBase.get_agent_skills_dirs`
        """
        if not skills_dir.is_dir():
            return []
        source = f"env:{env_name}"
        new_names: list[str] = []
        for info in _discover_skills(skills_dir, source=source):
            # Built-in skills cannot be overridden
            if (
                info.name in self._skills
                and self._skills[info.name].source == "builtin"
            ):
                continue
            if info.name in self._skills:
                info.enabled = self._skills[info.name].enabled
            self._skills[info.name] = info
            new_names.append(info.name)
        return new_names

    # ---------- list ----------
    def list_all(self) -> list[SkillInfo]:
        return sorted(self._skills.values(), key=lambda s: s.name)

    def list_enabled(self) -> list[SkillInfo]:
        return [s for s in self.list_all() if s.enabled]

    def list_selection_metadata(
        self, names: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Return minimal catalog entries for model selection.

        Only enabled skills; name and description only; full SKILL.md loads on activation.
        """
        name_set = set(names) if names is not None else None
        result: list[dict[str, Any]] = []
        for info in self.list_enabled():
            if name_set is not None and info.name not in name_set:
                continue
            result.append({"name": info.name, "description": info.description})
        return result

    # ---------- read ----------
    def activate(self, name: str) -> str:
        info = self._skills.get(name)
        if not info:
            return ""
        return _ensure_skill_md_loaded(info)

    def read(self, name: str, relative_path: str) -> str:
        info = self._skills.get(name)
        if not info:
            return ""
        skill_root = Path(info.path).resolve()
        target = (skill_root / relative_path).resolve()
        if not target.exists() or not target.is_file():
            return ""
        if skill_root != target and skill_root not in target.parents:
            return ""
        return target.read_text(encoding="utf-8")

    # ---------- state ----------
    def enable(self, name: str) -> bool:
        info = self._skills.get(name)
        if not info:
            return False
        info.enabled = True
        return True

    def disable(self, name: str) -> bool:
        info = self._skills.get(name)
        if not info:
            return False
        if info.source == "builtin":
            return False
        info.enabled = False
        return True

    def sync_enabled_from(self, source: "SkillRegistry") -> None:
        """将 ``source`` 中同名技能的 ``enabled`` 同步到本注册表。

        仅更新双方均存在的技能；用于 PersonAgent 每步与进程内全局注册表对齐（API 启停技能）。
        内置技能始终启用，不同步为关闭。
        """
        for name, info in self._skills.items():
            if info.source == "builtin":
                info.enabled = True
                continue
            src = source._skills.get(name)
            if src is not None:
                info.enabled = src.enabled

    def _ensure_builtin_skills_enabled(self) -> None:
        for info in self._skills.values():
            if info.source == "builtin":
                info.enabled = True

    def remove_custom(self, name: str) -> bool:
        """Remove a custom skill from registry only.

        NOTE: This does not delete files on disk. Callers (e.g. API layer) should
        handle filesystem removal, then call this method to drop it from memory.
        """
        info = self._skills.get(name)
        if not info:
            return False
        if info.source != "custom":
            return False
        del self._skills[name]
        return True

    def reload_skill(self, name: str) -> bool:
        """Hot-reload a skill's metadata and clear cached SKILL.md content.

        This is designed for the current skills-first architecture:
        - skills are discovered from SKILL.md frontmatter (+ optional script path)
        - activation lazily loads full SKILL.md into memory
        """
        info = self._skills.get(name)
        if not info:
            return False

        skill_root = Path(info.path)
        skill_md = skill_root / "SKILL.md"
        if not skill_md.exists():
            return False

        meta = _parse_frontmatter_from_file(skill_md)
        new_name = str(meta.get("name", info.name)).strip() or info.name
        if new_name != name:
            if new_name in self._skills:
                return False
            del self._skills[name]
            self._skills[new_name] = info

        info.name = new_name
        info.description = str(meta.get("description", info.description))
        info.script = _script_from_meta_or_convention(skill_root, new_name, meta)
        info.skill_md_loaded = False
        info.skill_md = ""
        return True

    def get_skill_info(self, name: str, load_content: bool = True) -> SkillInfo | None:
        info = self._skills.get(name)
        if info and load_content:
            _ensure_skill_md_loaded(info)
        return info

    # ---------- execute ----------
    async def execute(
        self,
        skill_name: str,
        args: dict[str, Any],
        agent_work_dir: str | Path,
        timeout_sec: int = 30,
    ) -> dict[str, Any]:
        """执行指定技能。

        有 ``script`` 则子进程执行；否则返回空成功。环境交互用 ``codegen`` 工具，不经本方法。

        :param skill_name: 技能名称。
        :param args: 传递给技能的参数。
        :param agent_work_dir: Agent 工作目录。
        :param timeout_sec: 执行超时秒数。
        :return: 执行结果字典，包含 ok、exit_code、stdout、stderr、artifacts 等字段。
        :rtype: dict[str, Any]
        """
        info = self._skills.get(skill_name)
        if not info:
            return _error("validation", f"Skill not found: {skill_name}")

        if not info.script:
            return {
                "ok": True,
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
                "error_type": "none",
                "artifacts": [],
            }

        skill_root = Path(info.path).resolve()
        script_path = (skill_root / info.script).resolve()
        if not script_path.exists() or not script_path.is_file():
            return _error("validation", f"Script not found: {info.script}")
        if skill_root not in script_path.parents:
            return _error("validation", "Script path escapes skill directory")

        work_dir = Path(agent_work_dir).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        before_files = {
            str(p.relative_to(work_dir)) for p in work_dir.rglob("*") if p.is_file()
        }

        # 使用环境变量白名单，避免泄露敏感信息
        env = {k: v for k, v in os.environ.items() if k in ALLOWED_ENV_VARS}
        env["SKILL_NAME"] = skill_name
        env["SKILL_DIR"] = str(skill_root)
        env["AGENT_WORK_DIR"] = str(work_dir)

        async with _get_global_subprocess_semaphore():
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script_path),
                "--args-json",
                json.dumps(args, ensure_ascii=False),
                cwd=str(work_dir),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_sec
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return _error(
                    "timeout", f"Skill execution timed out after {timeout_sec}s"
                )

        stdout = (stdout_b or b"").decode("utf-8", errors="replace")
        stderr = (stderr_b or b"").decode("utf-8", errors="replace")
        exit_code = int(proc.returncode or 0)
        after_files = {
            str(p.relative_to(work_dir)) for p in work_dir.rglob("*") if p.is_file()
        }
        artifacts = sorted(after_files - before_files)
        return {
            "ok": exit_code == 0,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "error_type": "none" if exit_code == 0 else "runtime",
            "artifacts": artifacts,
        }


def _error(error_type: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "exit_code": -1,
        "stdout": "",
        "stderr": message,
        "error_type": error_type,
        "artifacts": [],
    }


def _discover_skills(root: Path, source: str) -> list[SkillInfo]:
    """发现指定目录下的所有技能。

    扫描目录中的子目录，查找 SKILL.md 文件并解析 frontmatter。

    :param root: 要扫描的根目录。
    :param source: 技能来源标识（"builtin"、"custom" 或 "env:<name>"）。
    :return: 发现的 SkillInfo 列表。
    :rtype: list[SkillInfo]
    """
    result: list[SkillInfo] = []
    if not root.is_dir():
        return result
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith(("_", ".")):
            continue
        # 新架构要求必须有 SKILL.md
        skill_md = child / "SKILL.md"
        if not skill_md.exists():
            continue
        meta = _parse_frontmatter_from_file(skill_md)
        name = str(meta.get("name", child.name))
        info = SkillInfo(
            name=name,
            description=str(meta.get("description", "")),
            script=_script_from_meta_or_convention(child, name, meta),
            source=source,
            path=str(child.resolve()),
            skill_md_loaded=False,
        )
        result.append(info)
    return result


def _script_from_meta_or_convention(
    skill_root: Path, name: str, meta: dict[str, Any]
) -> str:
    raw = str(meta.get("script", "") or "").strip()
    if raw:
        candidate = (skill_root / raw).resolve()
        root = skill_root.resolve()
        if candidate.is_file() and (candidate == root or root in candidate.parents):
            return raw.replace("\\", "/")
        logger.warning("Ignoring invalid script path for skill '%s': %s", name, raw)
    conventional = skill_root / "scripts" / f"{name}.py"
    if conventional.is_file():
        return f"scripts/{name}.py"
    return ""


def _ensure_skill_md_loaded(info: SkillInfo) -> str:
    if info.skill_md_loaded:
        return info.skill_md
    path = Path(info.path) / "SKILL.md"
    if path.exists():
        info.skill_md = path.read_text(encoding="utf-8")
    info.skill_md_loaded = True
    return info.skill_md


def _parse_frontmatter_from_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}
    data: dict[str, Any] = {}
    key: str | None = None
    list_acc: list[str] | None = None
    for line in lines[1:]:
        s = line.rstrip("\n")
        stripped = s.strip()
        if stripped == "---":
            break
        if not stripped:
            continue
        if stripped.startswith("- ") and key is not None and list_acc is not None:
            list_acc.append(stripped[2:].strip())
            continue
        if key is not None and list_acc is not None:
            data[key] = list_acc
            key, list_acc = None, None
        if ":" not in stripped:
            continue
        k, _, v = stripped.partition(":")
        k = k.strip()
        v = v.strip()
        if not v:
            key = k
            list_acc = []
        else:
            data[k] = v
    if key is not None and list_acc is not None:
        data[key] = list_acc
    return data


_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
        _registry.scan_builtin()
    return _registry
