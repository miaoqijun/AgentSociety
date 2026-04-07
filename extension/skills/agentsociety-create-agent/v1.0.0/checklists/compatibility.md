# Agent Compatibility Checklist

Verify the generated Agent meets all requirements.

## Required Methods

- [ ] `async def ask(self, message: str, readonly: bool = True) -> str`
- [ ] `async def step(self, tick: int, t: datetime) -> str`
- [ ] `async def dump(self) -> dict`
- [ ] `async def load(self, dump_data: dict)`

## Recommended Methods

- [ ] Override `@classmethod def mcp_description(cls) -> str` (base class has a generic default; override for profile/schema docs in the module picker)
- [ ] `async def init(self, env: RouterBase) -> None`

## Inheritance

- [ ] Class inherits from `AgentBase` or `PersonAgent` (latter fits tools/skills/heavier workspace agents). Runtime registration accepts **any** `AgentBase` subclass in the file; this skill’s `validate.py` only recognizes **direct** bases named `AgentBase` or `PersonAgent` in the AST.
- [ ] Class is not abstract
- [ ] `super().__init__(...)` matches the **immediate** base: `AgentBase` uses `(id, profile, name=None)`; `PersonAgent` adds `init_state` and `**capability_kwargs` (see `agentsociety2.agent.person.PersonAgent`)

## Code Quality

- [ ] All required methods are `async`
- [ ] `dump()` returns JSON-serializable dict
- [ ] `load()` restores all state from dump
- [ ] Profile accessed via `.get(key, default)`
- [ ] Clear policy for `ask_env` / env failures (retry, default, or re-raise)—avoid silent swallowing

## Registration

- [ ] File lives under workspace `custom/agents/` (not under an `examples/` path if you want it scanned)
- [ ] The agent **class is defined in that file** (`cls.__module__` must match the loaded file); importing a ready-made class from another module without re-declaring it here will not register
- [ ] File name matches class concept
- [ ] Overridden `mcp_description()` documents profile fields when behavior is non-trivial
