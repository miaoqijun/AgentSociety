## Welcome to AI Social Scientist

**AI Social Scientist** is a VS Code workspace for next-generation computational social science. It brings project management, LLM configuration, AgentSociety² simulation, skill management, replay, analysis, and writing into one place.

![Evolution from AgentSociety-1 to AgentSociety2](../images/agentsociety2-dual-role-loop.png)

_AgentSociety² extends AgentSociety-1 from a simulation-focused system into an integrated research system: agents can serve both as research subjects and as research assistants._

### What AgentSociety is for

AgentSociety² is not just a chat interface. It organizes social science research as a runnable, inspectable, and extensible research environment. Agents play two complementary roles:

| Role | Meaning | Typical use |
|------|---------|-------------|
| **Research subjects** | Simulated social actors that can be observed and evaluated | Behavioral games, social interaction, urban activity, network diffusion |
| **Research assistants** | Agents that help design, execute, and analyze studies | Literature synthesis, hypothesis generation, experiment configuration, data analysis, paper writing |

Together, the two roles form a closed loop: scientist agents propose hypotheses, design experiments, and organize analysis; subject agents act in environments and generate data; human researchers retain theoretical judgment, research choices, and final interpretation.

![AgentSociety2 integrated research paradigms](../images/agentsociety2-integrated-framework.png)

_AgentSociety² integrates empirical inquiry, theoretical hypothesis development, computational simulation, and data-intensive analysis in one research workspace._

### How the four research paradigms fit together

| Paradigm | What it maps to in AgentSociety² |
|----------|----------------------------------|
| **Empirical** | Observations, surveys, behavioral experiments, and reproducible protocols |
| **Theoretical** | Concepts, hypotheses, mechanisms, and explanatory frames |
| **Computational** | Agent, environment, and rule-based mechanism instantiation |
| **Data-intensive** | Retrieval, processing, pattern discovery, visualization, and evaluation |

This extension brings those capabilities into VS Code, so you do not have to jump between terminals, config files, and result folders.

### What you can do with it

| Research stage | How the extension helps |
|----------------|-------------------------|
| Literature review | Search papers, maintain literature indexes, and keep Markdown notes |
| Hypothesis generation | Turn research questions and papers into testable hypotheses |
| Experiment design | Generate AgentSociety2 initialization configs and experiment steps |
| Agent simulation | Start a local backend and run multi-agent simulations and mechanism experiments |
| Replay and analysis | Inspect experiment traces, agent behavior, environment changes, and result data |
| Paper writing | Organize results, charts, and arguments into manuscript material |

### Fastest setup path

1. Open the **AI Social Scientist** sidebar.
2. Initialize a research project, or open an existing one.
3. Fill in your LLM `API Key` and `API Base`.
4. Start the local backend service.
5. Install the research skills you need for your task.

The next steps walk you through this setup in order.

### What needs to be configured

| Configuration | Purpose | When you need it |
|---------------|---------|------------------|
| LLM API | Powers literature work, planning, analysis, and agent reasoning | Required for first use |
| Backend service | Runs simulations, skills, and local API services | Needed for experiments, replay, and skills |
| Skill marketplace | Installs research and development skills | Choose based on your task |
| Claude Code / MCP | Lets a coding assistant access project skills and the local backend | Recommended as the default research collaboration entry point |

### How AgentSociety and this extension fit together

[AgentSociety](https://github.com/tsinghua-fib-lab/agentsociety) is an LLM-native agentic research platform developed by Tsinghua FibLab. This VS Code extension is its research workbench:

- **VS Code extension**: project tree, configuration page, skill management, replay, and help pages.
- **FastAPI backend**: runs locally and handles LLM calls, experiment management, and API services.
- **AgentSociety2 core**: provides PersonAgent, environment modules, experiment execution, and replay data.
- **Skills**: package literature, experiment, analysis, and writing capabilities into installable modules.

You do not need to memorize every term now. Start with the setup flow; if a concept feels unfamiliar, use the glossary appendix later in this walkthrough.
