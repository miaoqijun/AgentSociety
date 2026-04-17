# Agent Examples

Reference implementations in this repo (paths relative to the **agentsociety repo root**; Python imports remain `agentsociety2....`).

## SimpleAgent

`packages/agentsociety2/agentsociety2/custom/agents/examples/simple_agent.py`

- Basic `ask()` with profile prompts
- Simple `step()` with environment observation
- Minimal `dump()`/`load()`

**Use as template**: Simple decision-making agents

## AdvancedAgent

`packages/agentsociety2/agentsociety2/custom/agents/examples/advanced_agent.py`

- Memory system (`_memories` list)
- Mood tracking (`_mood` state)
- Memory integration in prompts

**Use as template**: Agents with internal states

## PublicGoodsAgent

`packages/agentsociety2/agentsociety2/contrib/agent/public_goods_agent.py`

- Complex `ask_env()` with template mode
- History tracking
- Structured decision parsing

**Use as template**: Game agents, complex environment interaction

## Key Pattern: Memory

```python
def __init__(self, ...):
    self._memories: list[dict] = []

async def ask(self, message, readonly=True):
    memory_text = "\n".join(m["content"] for m in self._memories[-5:])
    prompt = f"...memory context...\n{memory_text}\n\nQuestion: {message}"
    # ...
    self._memories.append({"content": f"Q: {message}", "type": "qa"})
```

## Key Pattern: Environment Action

```python
async def step(self, tick, t):
    # Get state
    _, state = await self.ask_env({}, "Get game state", readonly=True)
    
    # Submit action
    _, result = await self.ask_env(
        {"variables": {"action": decision}},
        "Submit {action}",
        readonly=False,
        template_mode=True
    )
```
