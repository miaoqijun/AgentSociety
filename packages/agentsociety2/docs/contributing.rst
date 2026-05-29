为 AgentSociety 2 贡献
===============================

感谢您对贡献 AgentSociety 2 的兴趣！

活跃维护范围
------------------

``packages/agentsociety2/``、``extension/``、``frontend/``。

Legacy 包（v1、community、benchmark）不在活跃 CI / 安全扫描范围内。详见仓库根目录 ``CONTRIBUTING.md`` 与 ``.github/agentsociety2-scope.yml``。

贡献方式
------------------

* **报告错误**: 使用可重现的示例提交 Issue
* **建议功能**: 分享您的改进想法
* **提交代码**: 提交 Pull Request
* **改进文档**: 帮助使文档更清晰
* **分享示例**: 向集合添加有用的示例

报告错误
--------------

报告错误时，请包括：

* Python 版本
* AgentSociety 2 版本
* 最小的可重现示例
* 预期行为与实际行为
* 任何错误消息或回溯

有关详情，请参阅错误报告模板。

建议功能
-------------------

欢迎功能建议！请：

* 清楚地描述用例
* 解释为什么它有用
* 考虑它是否适合项目范围
* 愿意接受讨论

提交 Pull Request
-------------------------

提交 PR 之前：

1. 检查现有 Issue 以获取相关讨论
2. 从 ``main`` 创建分支
3. 使用清晰的 Conventional Commits 提交
4. 如需要，更新文档与 CHANGELOG
5. 确保相关 CI 通过（Python / extension / frontend）

PR 指南
~~~~~~~~~~~~~

* 保持更改专注
* 遵循现有代码风格
* 更新相关文档
* 确保 CI 通过

开发设置
------------------

.. code-block:: bash

   # 安装依赖（工作区根目录）
   uv sync
   cd packages/agentsociety2 && uv sync --extra dev

   # Python 检查
   uv run ruff check .
   uv run pytest -q

   # 扩展
   cd extension && npm ci && npm run lint && npm run build

   # 前端
   cd frontend && npm ci && npm run lint && npm run build

发版
------

在 ``main`` 上打标签 ``agentsociety2-vX.Y.Z`` 并推送，自动触发 PyPI、VSIX 与 GitHub Release。详见 ``CONTRIBUTING.md``。

文档标准
------------------------

Python 文档字符串统一采用 Sphinx/reST 写法（``:param:``、``:returns:``、``:raises:``、``:ivar:`` 等），与 autodoc 生成的 API 参考保持一致；新增或修改代码时请沿用同一约定。

.. code-block:: python

   def example_function(param1: str, param2: int) -> bool:
       """Brief description of the function.

       :param param1: Description of param1.
       :param param2: Description of param2.
       :returns: Description of return value.
       :raises ValueError: If something goes wrong.
       """
       pass

获取帮助
------------

* **GitHub Issues**: 错误与功能请求
* **GitHub Discussions**: 问题与讨论
* **SECURITY.md**: 安全漏洞报告
* **Documentation**: https://agentsociety2.readthedocs.io/

许可证
-------

通过贡献 AgentSociety 2，您同意您的贡献将根据 Apache License 2.0 获得许可。
