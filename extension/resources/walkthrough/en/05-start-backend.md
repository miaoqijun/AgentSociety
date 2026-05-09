## Start the Backend Service

The backend is the local API service for AI Social Scientist. You should normally start it so agent skill management, module discovery, prefill parameters, custom module tests, replay APIs, and API documentation are ready to use.

---

### 🔧 What is the Backend?

This plugin uses a **client-server architecture**:
- **Frontend** = The VS Code plugin UI (what you see now)
- **Backend** = A local Python service (based on FastAPI) that serves extension APIs

Most interactive management features use the backend, especially agent runtime skill management, module discovery, prefill parameters, custom module scan/test, the replay webview, and API docs. If the backend is not running yet, you can still edit experiment configs, browse the project tree, open PDFs/CSVs/images, view the literature index, or run experiments through the CLI / Claude Code.

The backend reads the current workspace `.env` on startup. If you just changed API settings, restart the backend so the new configuration takes effect.

### How to Start

![Start backend example](../images/gif/start-backend.gif)

| Method | Action | Recommended |
|--------|--------|-------------|
| ⭐ Status Bar | Click the AI Social Scientist status in the bottom bar → **Start** | ✅ Easiest |
| Command Palette | `Ctrl+Shift+P` → search `Start Backend` | |
| Auto Start | Enable `aiSocialScientist.backend.autoStart` in settings | Good for daily use |

### Status Bar Guide

After starting, the VS Code **bottom status bar** shows the backend status:

![Backend running status example](../images/backend-running-config.png)

| Number | Meaning |
|--------|---------|
| 1 | Status cards at the top of the page: show backend, LLM, and Python status. |
| 2 | VS Code bottom status bar: shows whether the backend is running and which port it uses; click it to open backend management. |

| Status | Meaning | What to Do |
|--------|---------|------------|
| 🟢 **Running** | Backend is running normally | You can use the full extension experience |
| 🟡 **Starting** | Currently starting | Wait a few seconds |
| 🔴 **Error** | Failed to start | Click to check logs, verify API config |
| ⚪ **Stopped** | Backend is not running | Starting is recommended; local file editing and CLI/Claude Code experiment runs can still continue |

Click the backend status in the status bar to open the **backend management menu**:

| Menu Option | Function |
|------------|----------|
| Start | Start the backend |
| Stop | Stop the backend |
| Restart | Restart (recommended after changing config) |
| Show Logs | View backend logs (useful for troubleshooting) |
| Open API Docs | Open API documentation in browser |
| Copy URL | Copy backend URL to clipboard |

### Troubleshooting

1. 🔴 **Won't start** → Click [Show Logs](command:aiSocialScientist.showBackendLogs) to see the error
2. ❌ **API auth failed** → Go back to [Config Page](command:aiSocialScientist.openConfigPage) and verify Key & URL
3. ⚠️ **Port in use** → Restarting the backend will auto-switch to an available port

> 💡 The backend runs on `localhost:8001` by default. All data is stored locally — nothing is uploaded to the cloud.

### What you can do after it starts

| Next step | Entry point |
|-----------|-------------|
| Check whether APIs are available | Status bar → Open API Docs |
| Manage agent runtime skills | Sidebar → Skill Marketplace → Agent skills |
| Scan/test custom modules | Project tree → Custom modules |
| Inspect results | Right-click an experiment folder and open replay |

[Start Backend](command:aiSocialScientist.startBackend) | [Show Logs](command:aiSocialScientist.showBackendLogs) | [Show Backend Status](command:aiSocialScientist.showBackendStatus)
