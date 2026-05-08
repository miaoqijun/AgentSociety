## 连接 Claude Code

**Claude Code** 是 AI Social Scientist 推荐的默认编码与研究协作入口。连接后，它可以读取本项目的研究技能，并通过 MCP 访问本地后端，帮助你生成配置、检查实验、分析结果或修改自定义模块。

> 💡 如果你主要使用图形界面，也可以先完成基础配置；但建议保留 Claude Code 连接，后续排查实验和扩展技能时会更顺手。

---

### Claude Code 会读取哪些内容？

初始化项目后，插件会把内置开发技能同步到工作区：

```text
your-project/
├── .claude/skills/      # Claude Code 使用的开发技能
├── CLAUDE.md            # 面向 Claude Code 的项目说明
└── AGENTS.md            # 面向通用编码助手的项目说明
```

这些文件是项目级配置，适合随项目一起维护。涉及个人密钥的配置建议放在用户目录或本地忽略文件中。

![Claude 技能管理页面示例](../images/claude-skill-management.png)

[打开 Claude 技能源设置](command:aiSocialScientist.openClaudeSkillSourcesSettings)

---

### 配置 Claude Code 使用的模型服务

Claude Code 默认使用 Anthropic 服务。若你需要通过代理或兼容网关访问其他模型，可以在 `~/.claude/settings.json` 中配置环境变量：

![Claude Code 配置文件示例](../images/claude-settings-json.png)

编辑 `~/.claude/settings.json`（Mac/Linux）或 `用户目录/.claude/settings.json`（Windows）：

如果这个文件还不存在，可以先创建 `.claude` 文件夹和 `settings.json`：

![创建 Claude 设置文件示例](../images/gif/create-claude-settings-json.gif)

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://your-api-endpoint.com",
    "ANTHROPIC_AUTH_TOKEN": "your-api-key",
    "ANTHROPIC_MODEL": "your-model-name"
  }
}
```

> 💡 `ANTHROPIC_AUTH_TOKEN` 会作为 Bearer Token 发送；如果你的服务使用 `x-api-key`，也可以使用 `ANTHROPIC_API_KEY`。不同网关的兼容程度不同，请以服务商文档为准。

如果想让 Claude Code 在 `/model` 里发现网关提供的模型，并且网关支持 Anthropic Messages 格式，可以追加：

```json
{
  "env": {
    "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1"
  }
}
```

启动 Claude Code 后，使用 `/status` 查看连接状态，使用 `/model` 切换模型。

---

### 配置 MCP 连接外部服务

**MCP**（Model Context Protocol）让 Claude Code 能连接外部工具、数据库、知识库和远程服务。推荐优先接入远程 HTTP MCP 服务；如果服务商只提供 SSE 端点，也可以使用 SSE。只有在开发本地工具或需要访问本机资源时，才使用本地 stdio 服务。

常见接入方式：

| 类型 | 适合场景 | 配置方式 |
|------|----------|----------|
| 远程 HTTP | 云端 MCP、团队共享服务、外部平台集成 | `claude mcp add --transport http ...` |
| 远程 SSE | 旧版或特定服务只提供 SSE 端点 | `claude mcp add --transport sse ...` |
| 本地 stdio | 本地脚本、开发调试、需要访问本机文件或内网资源 | `claude mcp add --transport stdio ...` |

推荐用命令添加远程 MCP，而不是手写配置：

```bash
# 个人当前项目使用，默认写入本地 Claude Code 配置
claude mcp add --transport http agentsociety https://your-mcp-server.example.com/mcp

# 团队共享，写入项目根目录 .mcp.json
claude mcp add --transport http agentsociety --scope project https://your-mcp-server.example.com/mcp

# 如果服务商只提供 SSE 端点
claude mcp add --transport sse agentsociety-sse https://your-mcp-server.example.com/sse
```

如果远程 MCP 需要 Token，可以通过 header 传入：

```bash
claude mcp add --transport http agentsociety https://your-mcp-server.example.com/mcp \
  --header "Authorization: Bearer YOUR_TOKEN"
```

如果你希望把团队共享配置提交到仓库，也可以在项目根目录创建或编辑 `.mcp.json`。适合共享的配置里不要写死个人密钥，使用环境变量：

```json
{
  "mcpServers": {
    "agentsociety": {
      "type": "http",
      "url": "${AGENTSOCIETY_MCP_URL:-https://your-mcp-server.example.com/mcp}",
      "headers": {
        "Authorization": "Bearer ${AGENTSOCIETY_MCP_TOKEN}"
      }
    }
  }
}
```

本地后端开发时，也可以保留 stdio 方式。确保后端服务已启动，然后在项目根目录创建或编辑 `.mcp.json`：

```json
{
  "mcpServers": {
    "agentsociety": {
      "command": "uv",
      "args": ["run", "python", "-m", "agentsociety2.mcp"],
      "env": {
        "AGENTSOCIETY_BACKEND_URL": "http://localhost:8001"
      }
    }
  }
}
```

> 💡 `.mcp.json` 是项目级 MCP 配置，适合团队共享；个人密钥建议放到环境变量或用户级配置中。Claude Code 会在首次使用项目级 MCP 时要求确认，这是正常的安全检查。

---

### 验证连接

![编辑 Claude 设置示例](../images/gif/edit-claude-settings-json.gif)

1. 在项目根目录启动 `claude`。
2. 输入 `/status` 检查模型连接。
3. 输入 `/mcp` 检查 `agentsociety` MCP 服务状态。
4. 如果连接失败，先确认远程 MCP URL、认证 header 或本地后端端口是否正确。

配置完成后，重新打开终端或重启 Claude Code 会话即可生效。

[打开 Claude 技能源设置](command:aiSocialScientist.openClaudeSkillSourcesSettings)
