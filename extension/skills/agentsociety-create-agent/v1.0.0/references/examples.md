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
    # Get state (readonly query — template_mode=True is safe)
    _, state = await self.ask_env(
        {"variables": {"agent_id": self.id}},
        "Please call get_state() using agent_id from ctx['variables'].",
        readonly=True,
        template_mode=True,
    )

    # Submit action (stateful write — default template_mode=False unless the
    # env tool is verified idempotent AND no other write tool shares argument
    # names. See references/pitfalls.md P3.)
    _, result = await self.ask_env(
        {"variables": {"agent_id": self.id, "action": decision}},
        "Please call submit_action() using agent_id and action "
        "from ctx['variables'] to submit my decision.",
        readonly=False,
        template_mode=False,
    )
```
