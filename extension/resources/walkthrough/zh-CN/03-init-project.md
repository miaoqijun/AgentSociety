## 初始化研究项目

在开始使用前，你需要一个研究项目目录。

---

### 方式一：初始化新项目

在空白工作区中运行 **Initialize Research Project** 命令，自动创建完整的目录结构：

![初始化工作区示例](../images/gif/initialize-workspace.gif)

```
your-project/
├── custom/skills/          # Agent 运行时技能（从技能市场安装）
├── .claude/skills/         # Claude Code 技能
├── papers/                 # 文献资料
│   ├── pdf/               # PDF 原文
│   └── md/                # Markdown 笔记
├── experiment/             # 实验配置与结果
├── output/                 # 输出文件
├── TOPIC.md               # 研究话题描述
└── init/
    └── init_config.json   # 项目初始化配置
```

### 方式二：打开已有项目

直接用 VS Code 打开一个已有的研究工作区文件夹即可，插件会自动识别目录结构。

如果还没有项目目录，可以先新建一个空文件夹，再用 VS Code 打开：

![新建项目文件夹示例](../images/gif/create-project-folder.gif)

---

### 🔧 什么是命令面板？

VS Code 的**命令面板**是执行各种操作的快捷入口：

- 按 `Ctrl+Shift+P`（Mac: `Cmd+Shift+P`）打开
- 输入 `AI Social Scientist` 可以看到所有插件命令
- 常用命令也可以通过侧边栏按钮或状态栏直接触发

> 💡 推荐记住这个快捷键，很多操作都从这里发起。

[初始化项目](command:aiSocialScientist.initProject)
