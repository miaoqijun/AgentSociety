# -*- coding: utf-8 -*-

"""
列出可用的模型列表
"""

import os
import json
import requests
from typing import List, Optional, Dict

__all__ = ["get_available_models"]


def get_available_models(
    api_base: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 20
) -> List[Dict[str, str]]:
    """
    获取当前可用的模型列表，输出 JSON 结构，仅包含关键的 'id' 字段。

    :param api_base: OpenAI 兼容 API 基础 URL，通常以 ``/v1`` 结尾。
    :param api_key: API 密钥；未提供则读 ``AGENTSOCIETY_LLM_API_KEY``（需由调用方加载 ``.env``）。
    :param timeout: 请求超时时间（秒）。

    :returns: 模型列表，格式如下（``id`` 以服务商返回为准）：
        [
            {"id": "gpt-5.4"},
            {"id": "gpt-5.4-nano"}
        ]

    :raises ValueError: 当缺少必要的 API key 时。
    :raises RuntimeError: 当网络请求失败或响应格式异常时。
    """
    # 与 Config.LLM_* 一致：入参 > AGENTSOCIETY_* > 与 config 相同的默认 base
    base = (api_base or os.getenv("AGENTSOCIETY_LLM_API_BASE", "").strip()) or (
        "https://api.openai.com/v1"
    )
    key = (api_key or os.getenv("AGENTSOCIETY_LLM_API_KEY", "").strip()) or ""

    if not key:
        raise ValueError(
            "缺少 API key，请通过入参或环境变量 AGENTSOCIETY_LLM_API_KEY 提供"
        )

    base = base.rstrip("/")
    if base.endswith("/models"):
        url = base
    elif base.endswith("/v1") or base.endswith("/maas/v1"):
        url = f"{base}/models"
    else:
        url = f"{base}/models"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {key}",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise RuntimeError(f"网络请求异常：{e}") from e

    if resp.status_code != 200:
        raise RuntimeError(f"请求失败：HTTP {resp.status_code} - {resp.text}")

    try:
        body = resp.json()
    except ValueError as e:
        raise RuntimeError(f"响应非 JSON：{resp.text}") from e

    if (
        not isinstance(body, dict)
        or body.get("object") != "list"
        or not isinstance(body.get("data"), list)
    ):
        raise RuntimeError(f"返回结构异常：{body}")

    models: List[Dict[str, str]] = []
    for item in body["data"]:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            models.append({"id": item["id"]})

    return models


if __name__ == "__main__":
    from dotenv import load_dotenv

    # 入口脚本负责加载环境变量
    load_dotenv()

    try:
        # 获取模型列表
        models_data = get_available_models()

        # 输出 JSON 格式
        print(json.dumps(models_data, indent=2, ensure_ascii=False))
    except Exception as e:
        # 发生错误
        error_response = {"error": str(e)}
        print(json.dumps(error_response, indent=2, ensure_ascii=False))
