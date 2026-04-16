# Design

Make key architectural decisions.

## Decision Checklist

### 1. Base Class

- [ ] `AgentBase` — simple behavior, you own state, no built-in skill loop
- [ ] `PersonAgent` — skills / tool loop / built-in workspace and persistence

### 2. Workspace

- [ ] None - Game/benchmark agents
- [ ] Simple (`state.json`) - Basic state persistence
- [ ] Full (`state/`, `memory/`, `logs/`) - Complex agents

### 3. Profile Fields

List required fields:
- [ ] Standard: name, age, gender...
- [ ] Custom: ________________

### 4. State Variables

List internal states:
- [ ] ________________
- [ ] ________________

### 5. Environment Interactions

List queries/actions:
- [ ] Query: ________________
- [ ] Action: ________________
