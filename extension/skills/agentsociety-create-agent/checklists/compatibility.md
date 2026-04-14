# Agent Compatibility Checklist

Verify the generated Agent meets all requirements.

## Required Methods

- [ ] `async def ask(self, message: str, readonly: bool = True) -> str`
- [ ] `async def step(self, tick: int, t: datetime) -> str`
- [ ] `async def dump(self) -> dict`
- [ ] `async def load(self, dump_data: dict)`

## Recommended Methods

- [ ] `@classmethod def mcp_description(cls) -> str`
- [ ] `async def init(self, env: RouterBase) -> None`

## Inheritance

- [ ] Class inherits from `AgentBase`
- [ ] Class is not abstract
- [ ] `super().__init__()` is called in `__init__`

## Code Quality

- [ ] All required methods are `async`
- [ ] `dump()` returns JSON-serializable dict
- [ ] `load()` restores all state from dump
- [ ] Profile accessed via `.get(key, default)`
- [ ] Environment calls wrapped in try/except

## Registration

- [ ] File is in `custom/agents/` (not `examples/`)
- [ ] File name matches class concept
- [ ] `mcp_description()` documents profile fields
