"""工具实用函数。

JSON 处理、字符串截断、分页、重试逻辑。

JSON 容错策略：
- 解析：使用 json_repair 自动修复常见 JSON 错误（缺少引号、尾随逗号等）
- 序列化：自动处理 Pydantic 模型、datetime、set、bytes 等类型
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any

import json_repair

# BLOCKED_TOKENS 已移至 agentsociety2.agent.tool.security


def truncate(text: str, max_len: int) -> str:
    """截断文本到指定长度。

    :param text: 原始文本。
    :param max_len: 最大长度。
    :return: 截断后的文本。
    :rtype: str
    """
    if len(text) <= max_len:
        return text
    return text[:max_len] + "...<truncated>"


#: 截断函数别名
trunc_str = truncate


def _serialize_for_json(obj: Any) -> Any:
    """递归转换对象为 JSON 可序列化格式。

    处理 Pydantic 模型、datetime、set、bytes 等类型。
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_for_json(item) for item in obj]
    # set, frozenset 转为 list
    if isinstance(obj, (set, frozenset)):
        return [_serialize_for_json(item) for item in obj]
    # bytes 转为字符串
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    # Pydantic 模型
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(mode="json")
        except TypeError:
            return obj.model_dump()
    # datetime 类型
    if hasattr(obj, "isoformat"):
        try:
            return obj.isoformat()
        except TypeError:
            pass
    # Mapping 类型
    if isinstance(obj, Mapping):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    # 其他类型转为字符串
    return str(obj)


def json_dumps(obj: Any, indent: int | None = 2) -> str:
    """JSON 序列化（带容错处理）。

    自动处理不可序列化类型，确保输出有效 JSON。

    :param obj: 要序列化的对象。
    :param indent: 缩进级别。
    :return: JSON 字符串。
    :rtype: str
    """
    serialized = _serialize_for_json(obj)
    result = json.dumps(serialized, ensure_ascii=False, indent=indent)
    # 使用 json_repair 验证并修复输出
    try:
        json_repair.loads(result)
        return result
    except Exception:
        # 如果仍有问题，重新序列化
        return json_repair.dumps(serialized, indent=indent, ensure_ascii=False)


#: JSON 序列化别名
jr_dumps = json_dumps


def json_parse(text: str) -> Any:
    """容错 JSON 解析。

    自动修复常见 JSON 错误：
    - 缺少引号的键名
    - 尾随逗号
    - 单引号代替双引号
    - 注释

    :param text: JSON 文本。
    :return: 解析后的对象。
    :rtype: Any
    """
    if not text or not text.strip():
        return None
    return json_repair.loads(text)


#: JSON 解析别名
jr_parse = json_parse


def paginate(items: list[Any], page: int, size: int) -> dict[str, Any]:
    """列表分页。

    :param items: 完整列表。
    :param page: 页码（1-indexed）。
    :param size: 每页数量。
    :return: 分页结果字典。
    :rtype: dict[str, Any]
    """
    total = len(items)
    total_pages = max(1, (total + size - 1) // size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * size
    return {
        "items": items[start : start + size],
        "page": page,
        "size": size,
        "total_pages": total_pages,
        "total": total,
    }


def pagination_from_args(args: dict[str, Any], default_limit: int) -> tuple[int, int]:
    """从工具参数提取分页参数。

    :param args: 工具参数字典。
    :param default_limit: 默认限制。
    :return: (offset, limit) 元组。
    :rtype: tuple[int, int]
    """
    offset = max(0, int(args.get("offset", 0)))
    limit = max(1, min(default_limit, int(args.get("limit", default_limit))))
    return offset, limit


def slice_text_page(text: str, offset: int, limit: int) -> dict[str, Any]:
    """文本分页切片。

    :param text: 完整文本。
    :param offset: 字符偏移。
    :param limit: 字符限制。
    :return: 分页结果字典。
    :rtype: dict[str, Any]
    """
    total = len(text)
    if offset >= total:
        return {
            "content": "",
            "total_chars": total,
            "offset": offset,
            "limit_applied": limit,
            "returned_chars": 0,
            "next_offset": None,
            "has_more": False,
        }
    end = min(offset + limit, total)
    content = text[offset:end]
    next_offset = end if end < total else None
    return {
        "content": content,
        "total_chars": total,
        "offset": offset,
        "limit_applied": limit,
        "returned_chars": len(content),
        "next_offset": next_offset,
        "has_more": next_offset is not None,
    }


def json_dumps_tool_result_for_thread(
    result: dict[str, Any], budget: int = 65536
) -> str:
    """序列化工具结果用于 thread。

    :param result: 工具结果字典。
    :param budget: 字符预算。
    :return: 预算内的 JSON 字符串。
    :rtype: str
    """
    s = json_dumps(result, indent=None)
    if len(s) <= budget:
        return s
    truncated = {}
    for k, v in result.items():
        if isinstance(v, str) and len(v) > budget // 4:
            truncated[k] = truncate(v, budget // 4)
        else:
            truncated[k] = v
    return json_dumps(truncated, indent=None)


async def async_retry_on_transient(
    fn: Any, max_retries: int = 2, log_prefix: str = ""
) -> Any:
    """瞬时错误重试。

    :param fn: 要调用的异步函数。
    :param max_retries: 最大重试次数。
    :param log_prefix: 日志前缀。
    :return: 函数结果。
    :rtype: Any
    """
    from agentsociety2.logger import get_logger

    logger = get_logger()

    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            is_transient = any(
                x in err_str for x in ("rate limit", "429", "timeout", "connection")
            )
            if not is_transient or attempt >= max_retries:
                raise
            delay = 0.5 * (2**attempt)
            if log_prefix:
                logger.warning(
                    f"{log_prefix}transient error (attempt {attempt + 1}/{max_retries + 1}): {e}; retry in {delay}s"
                )
            await asyncio.sleep(delay)
    raise last_err or RuntimeError("Unexpected error in async_retry_on_transient")
