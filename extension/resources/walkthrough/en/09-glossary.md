## Glossary

This appendix explains common terms used by AI Social Scientist and AgentSociety², grouped alphabetically. You do not need to memorize them before starting; come back here when a concept feels unclear.

Quick index: [A](#a) · [B-C](#b-c) · [D-E](#d-e) · [F-I](#f-i) · [L-M](#l-m) · [P-R](#p-r) · [S-T](#s-t) · [V-W](#v-w)

### A

| Term | Meaning |
|------|---------|
| **Agent** | An entity that can observe an environment, plan actions, call tools, and keep state toward a goal. |
| **Agent runtime skill** | A skill installed under `custom/skills/`, mainly used by agents during simulations. |
| **AgentSociety²** | An LLM-native agentic research framework for turning social science questions into runnable and inspectable computational experiments. |
| **AGENTS.md** | Project instructions for general coding assistants, including structure, commands, and collaboration conventions. |
| **AI Chat** | The extension's chat entry point for asking research questions, generating configs, checking results, or operating on the project. |
| **AI Social Scientist** | The VS Code extension and research workbench for project management, configuration, skills, replay, and help pages. |
| **API Base** | The service endpoint for model calls, such as `https://api.openai.com/v1`. |
| **API Key** | The secret key used to call a model provider. Keep it local and do not commit it to a public repository. |

### B-C

| Term | Meaning |
|------|---------|
| **Backend** | The local Python service behind the extension. The UI handles interaction; the backend handles model calls, experiment runs, and data services. |
| **Claude Code skill** | A skill installed under `.claude/skills/`, mainly used by Claude Code or similar coding assistants in the IDE. |
| **CLAUDE.md** | Project instructions for Claude Code, used to explain how the coding assistant should understand and work with this project. |
| **Command Palette** | VS Code's quick command launcher, opened with `Ctrl+Shift+P` or `Cmd+Shift+P`. |
| **Computational paradigm** | Instantiating mechanisms with agents, environments, and rules, then testing them through simulation. |
| **Custom Module** | User-provided extension code for adding environment mechanisms, tools, or experiment logic. |

### D-E

| Term | Meaning |
|------|---------|
| **Data-intensive paradigm** | Understanding large-scale data through retrieval, processing, statistics, visualization, and pattern discovery. |
| **Embedding Model** | A model that converts text into vectors, often used for semantic search and literature retrieval. |
| **Empirical paradigm** | Obtaining evidence through observations, surveys, experiments, or behavioral data. |
| **Environment** | The simulated setting in which agents act, such as space, resources, economic rules, social relations, or custom mechanisms. |
| **`.env`** | A local workspace configuration file commonly used for API endpoints, keys, model names, and runtime settings. |
| **Experiment Config** | The configuration files that define how an experiment is initialized, executed, and saved. |

### F-I

| Term | Meaning |
|------|---------|
| **FastAPI backend** | The local Python service that handles LLM calls, experiment execution, skill management, and APIs. |
| **Integrated Research Environment** | A unified research environment that connects literature, hypotheses, experiments, simulations, analysis, and writing in one workflow. |

### L-M

| Term | Meaning |
|------|---------|
| **Literature Library** | The project area for paper PDFs, Markdown notes, literature indexes, and research materials. |
| **LLM** | A large language model such as GPT, Claude, DeepSeek, or Qwen. |
| **MCP** | Model Context Protocol, which lets coding assistants such as Claude Code connect to external tools, remote HTTP/SSE services, or local backends. |
| **Model** | The model name used for requests. Model names differ across providers. |

### P-R

| Term | Meaning |
|------|---------|
| **PersonAgent** | The default human-like agent in AgentSociety², used to simulate individuals with profiles, memory, intentions, and actions. |
| **Profile** | An agent's descriptive information, such as identity, background, goals, preferences, or role. |
| **Replay** | Recorded experiment traces used to inspect agent behavior, environment changes, and results. |
| **Research workflow** | A connected sequence from literature, hypotheses, experiment design, simulation, and analysis to writing. |
| **Run Directory** | The output directory for one experiment run, usually containing logs, config snapshots, results, and replay data. |

### S-T

| Term | Meaning |
|------|---------|
| **Silicon Scientist** | A paper-style term for an agent that assists hypothesis generation, experiment design, data analysis, and writing. In the welcome page, this is called a "research assistant." |
| **Silicon Subject** | A paper-style term for an agent simulated and observed as an experimental subject. In the welcome page, this is called a "research subject." |
| **Skill** | An installable capability module that tells an agent or coding assistant when to use a capability, what files to read, and what outputs to produce. |
| **Skill Marketplace** | The extension page for browsing, installing, enabling, archiving, or deleting skills. |
| **Steps Config** | A configuration file that describes what an experiment should do, such as ask, intervene, run simulation steps, and save artifacts. |
| **Theoretical paradigm** | Developing concepts, hypotheses, mechanisms, and explanatory frames. |
| **Token** | The unit of text processed by a model, often used for pricing and context limits. |

### V-W

| Term | Meaning |
|------|---------|
| **VS Code workspace** | The project folder currently open in VS Code. The extension reads and writes `.env`, configs, results, skills, and replay data here. |
