## 启动后端服务

后端服务是 AI Social Scientist 的本地引擎，负责运行 Agent 模拟、管理技能、调用 LLM、生成回放数据和提供 API。

---

### 🔧 什么是后端服务？

本插件采用**前后端分离**架构：
- **前端** = VS Code 插件界面（你现在看到的）
- **后端** = 一个运行在本地的 Python 服务（基于 FastAPI），处理 AI 调用和模拟计算

你需要先启动后端，插件的大部分功能才能正常使用。

后端启动时会读取当前工作区 `.env`。如果你刚修改过 API 配置，推荐重启后端让配置立即生效。

### 启动方式

![启动后端服务示例](../images/gif/start-backend.gif)

| 方式 | 操作 | 推荐 |
|------|------|------|
| ⭐ 状态栏 | 点击底部状态栏的 AI Social Scientist 状态 → **Start** | ✅ 最方便 |
| 命令面板 | `Ctrl+Shift+P` → 搜索 `Start Backend` | |
| 自动启动 | 在设置中开启 `aiSocialScientist.backend.autoStart` | 适合日常使用 |

### 状态栏说明

启动后，VS Code **底部状态栏**会显示后端状态：

![后端运行状态示例](../images/backend-running-config.png)

| 编号 | 含义 |
|------|------|
| 1 | 页面顶部的状态卡片：用于确认后端服务、LLM 配置和 Python 环境是否都已就绪。 |
| 2 | VS Code 底部状态栏：显示后端是否运行以及当前端口，点击可以打开后端管理菜单。 |

| 状态 | 含义 | 你需要做什么 |
|------|------|-------------|
| 🟢 **Running** | 后端正常运行 | 无，可以开始使用 |
| 🟡 **Starting** | 正在启动中 | 等待几秒 |
| 🔴 **Error** | 启动失败 | 点击查看日志，检查 API 配置 |
| ⚪ **Stopped** | 后端未运行 | 点击启动 |

点击状态栏的后端状态，可以打开**后端管理菜单**：

| 菜单选项 | 功能 |
|---------|------|
| Start | 启动后端 |
| Stop | 停止后端 |
| Restart | 重启后端（修改配置后推荐用这个） |
| Show Logs | 查看后端日志（排查问题时很有用） |
| Open API Docs | 在浏览器中打开 API 文档 |
| Copy URL | 复制后端地址到剪贴板 |

### 遇到问题？

1. 🔴 **启动失败** → 点击 [查看日志](command:aiSocialScientist.showBackendLogs) 查看错误
2. ❌ **API 验证失败** → 回到 [配置页面](command:aiSocialScientist.openConfigPage) 检查 Key 和 URL
3. ⚠️ **端口被占用** → 重启后端会自动切换可用端口

> 💡 后端默认运行在 `localhost:8001`。所有数据都存在本地，不会上传到云端。

### 启动成功后可以做什么

| 下一步 | 入口 |
|--------|------|
| 检查 API 是否可用 | 状态栏 → Open API Docs |
| 安装研究技能 | 侧边栏 → 技能市场 |
| 运行实验 | 项目中的实验配置或 AI Chat |
| 查看结果 | 实验目录右键打开回放 |

[启动后端](command:aiSocialScientist.startBackend) | [查看日志](command:aiSocialScientist.showBackendLogs) | [查看后端状态](command:aiSocialScientist.showBackendStatus)
