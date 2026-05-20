"""
Agent Skills API 路由

提供 agent skill 的列表、启用/禁用、扫描自定义 skill、导入/创建/上传 skill 的 API 端点。

关联文件：
- @packages/agentsociety2/agentsociety2/agent/skills/__init__.py - Skill 注册表
- @extension/src/apiClient.ts - VSCode 扩展 API 客户端
- @frontend/src/pages/Skills/index.tsx - Web 前端 Skill 管理页

API 端点：
- GET  /api/v1/agent-skills/list       — 列出所有 agent skill
- POST /api/v1/agent-skills/enable     — 启用 skill（进入可选目录）
- POST /api/v1/agent-skills/disable    — 禁用 skill
- POST /api/v1/agent-skills/scan       — 扫描 workspace/custom/skills/ 下的自定义 skill
- POST /api/v1/agent-skills/import     — 从路径导入 skill 目录
- POST /api/v1/agent-skills/create     — 在线创建新 skill（SKILL.md + 可选脚本）
- POST /api/v1/agent-skills/upload     — 上传 zip 包导入 skill
- POST /api/v1/agent-skills/reload     — 热重载指定 skill
- GET  /api/v1/agent-skills/{name}/info — 获取 SKILL.md 内容
- POST /api/v1/agent-skills/remove     — 移除自定义 skill
"""

from __future__ import annotations

import io
import os
import shutil
import zipfile
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from agentsociety2.agent.skills import get_skill_registry
from agentsociety2.backend.path_security import (
    custom_skills_root,
    extract_zip_under,
    require_safe_skill_name,
    resolve_existing_directory,
    resolve_path_under_directory,
    resolve_skill_relative,
    resolve_under_root,
    skill_install_dir,
)
from agentsociety2.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/api/v1/agent-skills", tags=["agent-skills"])


# ── 请求/响应模型 ──


class SkillItem(BaseModel):
    name: str
    description: str
    source: str
    enabled: bool
    path: str
    has_skill_md: bool
    script: str = ""


class ListResponse(BaseModel):
    success: bool
    skills: list[SkillItem]
    total: int


class NameRequest(BaseModel):
    name: str = Field(..., description="skill 名称")


class ScanRequest(BaseModel):
    workspace_path: str | None = Field(None, description="工作区路径")


class ScanResponse(BaseModel):
    success: bool
    new_skills: list[str]
    total: int
    message: str


class ImportRequest(BaseModel):
    source_path: str = Field(..., description="skill 目录的绝对路径")
    workspace_path: str | None = Field(None, description="工作区路径")


class ImportResponse(BaseModel):
    success: bool
    name: str
    message: str


class CreateRequest(BaseModel):
    name: str = Field(..., description="skill 名称（也作为目录名）")
    description: str = Field("", description="skill 描述")
    script: str = Field(
        "", description="subprocess 脚本相对路径（留空则为 prompt-only）"
    )
    body: str = Field("", description="SKILL.md 正文（frontmatter 之后的内容）")
    script_content: str = Field("", description="脚本文件内容（当 script 非空时使用）")
    workspace_path: str | None = Field(None, description="工作区路径")


class SimpleResponse(BaseModel):
    success: bool
    message: str


def _skill_has_skill_md(path_str: str) -> bool:
    try:
        root = resolve_existing_directory(path_str)
    except HTTPException:
        return False
    return resolve_under_root(root, "SKILL.md").is_file()


def _require_workspace(workspace_path: str | None) -> str:
    workspace = workspace_path or os.getenv("WORKSPACE_PATH")
    if not workspace:
        raise HTTPException(
            400, "workspace_path not provided and WORKSPACE_PATH not set"
        )
    return workspace


# ── API 端点 ──


@router.get("/list", response_model=ListResponse)
async def list_skills():
    """列出所有已发现的 Agent Skill（builtin + custom + env）。"""
    reg = get_skill_registry()
    _ensure_custom_scanned(reg)
    _ensure_env_skills_scanned(reg)

    items = [
        SkillItem(
            name=s.name,
            description=s.description,
            source=s.source,
            enabled=s.enabled,
            path=s.path,
            has_skill_md=_skill_has_skill_md(s.path),
            script=s.script,
        )
        for s in reg.list_all()
    ]
    return ListResponse(success=True, skills=items, total=len(items))


@router.post("/enable", response_model=SimpleResponse)
async def enable_skill(req: NameRequest):
    """启用指定 skill（全局注册表；PersonAgent 在下一仿真步会与全局对齐）。"""
    reg = get_skill_registry()
    if reg.enable(req.name):
        logger.info(f"[Skills] Enabled: {req.name}")
        return SimpleResponse(success=True, message=f"Skill '{req.name}' enabled")
    raise HTTPException(404, f"Skill '{req.name}' not found")


@router.post("/disable", response_model=SimpleResponse)
async def disable_skill(req: NameRequest):
    """禁用指定 skill（内置技能不可关闭）。"""
    reg = get_skill_registry()
    info = reg.get_skill_info(req.name, load_content=False)
    if not info:
        raise HTTPException(404, f"Skill '{req.name}' not found")
    if info.source == "builtin":
        raise HTTPException(400, "Built-in skills cannot be disabled")
    if reg.disable(req.name):
        logger.info(f"[Skills] Disabled: {req.name}")
        return SimpleResponse(success=True, message=f"Skill '{req.name}' disabled")
    raise HTTPException(404, f"Skill '{req.name}' not found")


@router.post("/scan", response_model=ScanResponse)
async def scan_custom_skills(req: ScanRequest):
    """扫描工作区的自定义 Agent Skill（{workspace}/custom/skills/）。"""
    workspace = _require_workspace(req.workspace_path)
    reg = get_skill_registry()
    new_names = reg.scan_custom(workspace)

    return ScanResponse(
        success=True,
        new_skills=new_names,
        total=len(reg.list_all()),
        message=f"发现 {len(new_names)} 个新 skill" if new_names else "未发现新 skill",
    )


@router.post("/import", response_model=ImportResponse)
async def import_skill(req: ImportRequest):
    """从外部路径导入 Agent Skill（复制到 custom/skills/）。"""
    source = resolve_existing_directory(req.source_path)
    skill_md = resolve_under_root(source, "SKILL.md")
    scripts_dir = resolve_under_root(source, "scripts")
    if not skill_md.is_file() and not scripts_dir.is_dir():
        raise HTTPException(
            400, "Directory does not look like a skill (missing SKILL.md and scripts/)"
        )

    workspace = _require_workspace(req.workspace_path)
    skill_name = require_safe_skill_name(source.name)
    dest = skill_install_dir(workspace, skill_name)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(source), str(dest))

    reg = get_skill_registry()
    reg.scan_custom(workspace)

    logger.info(f"[Skills] Imported skill '{skill_name}' from {source} → {dest}")
    return ImportResponse(
        success=True,
        name=skill_name,
        message=f"Skill '{skill_name}' imported to {dest}",
    )


@router.post("/create", response_model=ImportResponse)
async def create_skill(req: CreateRequest):
    """在线创建新的自定义 Skill。

    在 custom/skills/{name}/ 下生成 SKILL.md（+ 可选脚本文件）。
    """
    workspace = _require_workspace(req.workspace_path)

    safe_name = require_safe_skill_name(
        req.name.strip().replace("/", "_").replace("\\", "_").replace("..", "_")
    )

    dest = skill_install_dir(workspace, safe_name)
    if dest.exists():
        raise HTTPException(
            400,
            f"Skill '{safe_name}' already exists. Remove it first or use a different name.",
        )
    dest.mkdir(parents=True, exist_ok=True)

    frontmatter_lines = ["---", f"name: {safe_name}", f"description: {req.description}"]
    if req.script:
        frontmatter_lines.append(f"script: {req.script}")
    frontmatter_lines.append("---")

    body = req.body.strip() or f"# {safe_name}\n\nCustom skill."
    skill_md_content = "\n".join(frontmatter_lines) + "\n\n" + body + "\n"
    resolve_under_root(dest, "SKILL.md").write_text(skill_md_content, encoding="utf-8")

    if req.script and req.script_content:
        script_path = resolve_skill_relative(dest, req.script)
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(req.script_content, encoding="utf-8")

    reg = get_skill_registry()
    reg.scan_custom(workspace)

    logger.info(f"[Skills] Created skill '{safe_name}' at {dest}")
    return ImportResponse(
        success=True, name=safe_name, message=f"Skill '{safe_name}' created"
    )


@router.post("/upload", response_model=ImportResponse)
async def upload_skill(
    file: UploadFile = File(..., description="skill 目录的 zip 包"),
    workspace_path: str | None = None,
):
    """上传 zip 包导入 Skill。

    zip 包应包含一个顶层目录，内含 SKILL.md。
    """
    workspace = _require_workspace(workspace_path)

    data = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise HTTPException(400, "Invalid zip file") from e

    top_dirs = {n.split("/")[0] for n in zf.namelist() if "/" in n}
    if len(top_dirs) != 1:
        raise HTTPException(400, "Zip should contain exactly one top-level directory")
    skill_dir_name = require_safe_skill_name(top_dirs.pop())

    has_skill_md = any(
        n == f"{skill_dir_name}/SKILL.md" or n.endswith("/SKILL.md")
        for n in zf.namelist()
    )
    if not has_skill_md:
        raise HTTPException(400, "Zip does not contain a SKILL.md file")

    skills_dir = custom_skills_root(workspace)
    dest = skill_install_dir(workspace, skill_dir_name)
    if dest.exists():
        shutil.rmtree(dest)
    extract_zip_under(skills_dir, zf)
    zf.close()

    reg = get_skill_registry()
    reg.scan_custom(workspace)

    logger.info(f"[Skills] Uploaded skill '{skill_dir_name}' to {dest}")
    return ImportResponse(
        success=True,
        name=skill_dir_name,
        message=f"Skill '{skill_dir_name}' uploaded",
    )


@router.post("/reload", response_model=SimpleResponse)
async def reload_skill(req: NameRequest):
    """热重载指定 Skill 的 SKILL.md 元数据。"""
    reg = get_skill_registry()
    if reg.reload_skill(req.name):
        logger.info(f"[Skills] Reloaded: {req.name}")
        return SimpleResponse(success=True, message=f"Skill '{req.name}' reloaded")
    raise HTTPException(404, f"Skill '{req.name}' not found or reload failed")


@router.get("/{name}/info")
async def get_skill_info(name: str) -> dict[str, Any]:
    """获取 Skill 的详细信息（含 SKILL.md 内容）。"""
    reg = get_skill_registry()
    info = reg.get_skill_info(name)

    if not info:
        raise HTTPException(404, f"Skill '{name}' not found")

    return {
        "success": True,
        "name": info.name,
        "description": info.description,
        "source": info.source,
        "enabled": info.enabled,
        "path": info.path,
        "script": info.script,
        "skill_md": info.skill_md,
    }


@router.post("/remove", response_model=SimpleResponse)
async def remove_custom_skill(req: NameRequest):
    """移除自定义 Skill（删除目录 + 注册表记录）。仅限 source=custom。"""
    reg = get_skill_registry()
    info_dict = {s.name: s for s in reg.list_all()}
    info = info_dict.get(req.name)

    if not info:
        raise HTTPException(404, f"Skill '{req.name}' not found")
    if info.source != "custom":
        raise HTTPException(400, f"Cannot remove builtin skill '{req.name}'")

    workspace = _require_workspace(None)
    skill_path = resolve_path_under_directory(custom_skills_root(workspace), info.path)
    if skill_path.exists():
        shutil.rmtree(skill_path)

    reg.remove_custom(req.name)
    logger.info(f"[Skills] Removed custom skill: {req.name}")
    return SimpleResponse(success=True, message=f"Custom skill '{req.name}' removed")


# ── 辅助函数 ──


def _ensure_custom_scanned(reg) -> None:
    """确保 custom skills 已扫描"""
    workspace = os.getenv("WORKSPACE_PATH")
    if workspace:
        reg.scan_custom(workspace)


def _ensure_env_skills_scanned(reg) -> None:
    """扫描已注册环境模块附带的 agent skill 到全局 registry。"""
    from agentsociety2.registry import get_registered_env_modules

    for _module_type, env_class in get_registered_env_modules():
        for skills_dir in env_class.get_agent_skills_dirs():
            if skills_dir.is_dir():
                reg.scan_env_skills(skills_dir, env_class.__name__)
