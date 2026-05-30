## 配置 LLM API

AI Social Scientist 需要一个大语言模型（LLM）API 来驱动文献理解、实验规划、Agent 推理和分析写作。配置会写入当前工作区的 `.env`，不会自动上传到云端。

---

### 🔧 什么是 API Key？

**API Key** 就像一把"钥匙"，让你的插件能调用 AI 服务。每个服务商都会给你一个唯一的 Key。

**API Base URL** 是服务商的"地址"，告诉插件去哪里调用 AI。

### 必填项

在配置页面中填写两项即可：

![API 配置与后端状态示例](../images/backend-running-config.png)

| 编号 | 含义                                                                 |
| ---- | -------------------------------------------------------------------- |
| 1    | 配置状态概览：快速确认后端、LLM 配置和 Python 环境是否可用。         |
| 2    | 底部状态栏：显示当前后端端口，点击可打开启动、停止、重启和日志菜单。 |

| 配置项       | 说明             | 示例                        |
| ------------ | ---------------- | --------------------------- |
| **API Key**  | 服务商给你的密钥 | `sk-xxx` 或 `sk-ant-xxx`    |
| **API Base** | API 服务地址     | `https://api.openai.com/v1` |

建议先只填必填项并点击验证。能连通之后，再按需要调整模型名称、Embedding 或代码生成模型。

---

### 💡 还没有 API Key？选择一个服务商

点击下方链接，注册账号并获取 API Key：

#### 国际服务商

| 服务商                                         | 获取 Key              | API Base URL                | 特点                    |
| ---------------------------------------------- | --------------------- | --------------------------- | ----------------------- |
| [OpenAI](https://platform.openai.com/api-keys) | platform.openai.com   | `https://api.openai.com/v1` | GPT 系列，能力强        |
| [Anthropic](https://console.anthropic.com/)    | console.anthropic.com | `https://api.anthropic.com` | Claude 系列，擅长长文本 |

#### 国内服务商（推荐国内用户）

| 服务商                                                                               | 获取 Key              | API Base URL                                        | 特点                     |
| ------------------------------------------------------------------------------------ | --------------------- | --------------------------------------------------- | ------------------------ |
| [通义千问](https://bailian.console.aliyun.com/)                                      | 阿里云百炼平台        | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 免费额度多，国内访问快   |
| [DeepSeek](https://platform.deepseek.com/api_keys)                                   | platform.deepseek.com | `https://api.deepseek.com`                          | 性价比高，推理能力强     |
| [智谱 GLM](https://bigmodel.cn/usercenter/proj-mgmt/apikeys)                         | bigmodel.cn           | `https://open.bigmodel.cn/api/paas/v4`              | 国产模型，有 Coding Plan |
| [Kimi](https://platform.moonshot.cn/console/api-keys)                                | platform.moonshot.cn  | `https://api.moonshot.cn/v1`                        | 长文本处理出色           |
| [MiniMax](https://platform.minimaxi.com/user-center/basic-information/interface-key) | platform.minimaxi.com | `https://api.minimax.chat/v1`                       | 多模态能力               |

> 💡 **新手建议**：先选择一个兼容 OpenAI 格式的服务商，填入 `API Base` 和 `API Key` 后验证连接。不同服务商的模型名称不同，填写前请以服务商控制台为准。

---

### 高级配置

| 配置项          | 说明                         | 默认值                   |
| --------------- | ---------------------------- | ------------------------ |
| Model           | 默认使用的模型名称           | `gpt-5.5`                |
| Coder Model     | 代码生成用的模型             | 与默认相同               |
| Nano Model      | 高频操作用的轻量模型         | 与默认相同               |
| Embedding Model | 向量嵌入模型（用于语义搜索） | `text-embedding-3-large` |

> 💡 留空项将沿用默认配置。熟悉流程后再按需调整即可。

### 常见检查

| 现象                 | 优先检查                                                                                          |
| -------------------- | ------------------------------------------------------------------------------------------------- |
| 验证失败             | API Key 是否复制完整，API Base 是否包含 `/v1`                                                     |
| 模型不存在           | Model 名称是否与服务商控制台一致                                                                  |
| 后端启动失败         | `.env` 是否保存成功，是否需要重启后端                                                             |
| 文献/分析很慢        | 是否需要配置更快的 Nano/Coder 模型                                                                |
| 学术文献检索验证失败 | `LITERATURE_SEARCH_MCP_URL` 是否为 `https://llmapi.fiblab.net/mcp/`；Key 是否具备学术文献检索权限 |

### 学术文献检索

在配置页「高级」中填写 MCP 网关地址与 API Key（与 `.env` 同步，保存后生效）：

| 配置项  | 示例                                         |
| ------- | -------------------------------------------- |
| MCP URL | `https://llmapi.fiblab.net/mcp/`             |
| API Key | 与 LLM 相同、且已开通学术文献检索的 `sk-...` |

只需写入工作区 `.env` 即可，**不必**再单独配置 Claude 的 `mcp.json`。文献技能仅调用 MCP 上的 `literature_*` 工具，不会误用网关上的其他 MCP 服务。

[打开配置页面](command:aiSocialScientist.openConfigPage)
