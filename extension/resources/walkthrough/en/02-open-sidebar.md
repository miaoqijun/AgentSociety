## Meet the Sidebar

The core operations of AI Social Scientist live in the **left activity bar**.

### How to Open

1. Find the **left activity bar** (leftmost icon column in VS Code)
2. Click the **AI Social Scientist** icon
3. The sidebar shows the **Project Structure** view

![VS Code layout overview](../images/vscode-layout-overview.png)

| Number | Area | What it does |
|--------|------|--------------|
| 1 | Activity Bar | Switches between Explorer, Search, Git, Extensions, AI Social Scientist, and other main views. |
| 2 | Sidebar | Shows the content of the selected view, such as the file tree or AI Social Scientist project structure. |
| 3 | Editor Area | Opens welcome pages, configuration pages, experiment files, AI Chat, or replay views. |

> 💡 The sidebar requires a workspace folder to be open before showing project content.

---

### Sidebar Quick Actions

At the top of the sidebar, you'll see four icon buttons:

| Button | Function | When to Use |
|--------|----------|-------------|
| 🔄 **Refresh** | Reload the project file tree | When files were added/deleted but the view didn't update |
| 🧩 **Skills** | Open the Skill Marketplace | When you want to install or manage agent skills |
| ⚙️ **Config** | Open the API configuration page | First-time setup or when you need to change your API Key |
| 📖 **Help** | Open the user guide | When you want to see the full documentation |

### Project Structure View

The sidebar displays your research project as a tree:

![AI Social Scientist project structure sidebar](../images/project-structure-sidebar.png)

```
📂 your-project/
├── 📄 TOPIC.md           → Research topic (click to preview, right-click to edit)
├── 📂 papers/            → Literature
│   ├── 📂 pdf/           → PDF papers
│   └── 📂 md/            → Markdown notes
├── 📂 hypothesis_xxx/    → Research hypothesis
│   └── 📂 experiment_xxx/ → Experiment (click to replay)
└── 📂 custom/skills/     → Installed skills
```

> 💡 Right-click files for more actions: copy path, open in file explorer, format JSON, etc.

[Open Sidebar](command:projectStructureView.focus)
