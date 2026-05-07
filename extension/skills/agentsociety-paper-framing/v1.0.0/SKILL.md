---
name: agentsociety-paper-framing
version: 1.0.0
description: Use when `paper_state.current_phase` is `framing`, or when a paper angle and `storyline_map` must be produced or revised from the current research pack.
---

# Paper Framing

Translate the raw research pack into a **storyline_map**: one sharp
question, one defensible angle, one honest contribution type, and
explicit kill criteria that future reviewers can test. Framing is the
single highest-leverage step — errors here propagate through every
downstream artifact.

## When to Use

- `paper_state.current_phase = framing`
- `storyline_map.json` is missing, OR
- Latest review round targets `framing` with verdict >= `revise_structural`

**Do NOT use when:**

- `research_pack.json` does not exist (run `build-pack` first)
- The phase is `manuscript-build` or later (re-frame only through the revision-router)

## Quick Reference

| Action | CLI |
|--------|-----|
| Persist storyline_map | `$PYTHON_PATH .agentsociety/bin/ags.py paper-orchestrator framing --workspace <ws> --payload '<storyline_map JSON>'` |
| Persist review round | `$PYTHON_PATH .agentsociety/bin/ags.py paper-orchestrator review --workspace <ws> --payload '<Review JSON>' --round <N>` |

Aliases: `paper-framing`, `paper_framing`.

## Workflow

```dot
digraph paper_framing_flow {
    rankdir=LR;
    node [shape=box, style=filled, fillcolor="#E8F4FD"];
    producer [label="producer\nbuild storyline_map"];
    persist [label="persist storyline_map"];
    critic [label="angle-critic"];
    auditor [label="contribution-auditor\nconditional"];
    route [label="revision-router"];
    advance [label="advance phase"];

    producer -> persist -> critic;
    critic -> auditor [label="producer concerns\nor critic != accept"];
    critic -> advance [label="accept"];
    auditor -> route [label="pivot_conceptual\nor pivot_major"];
    auditor -> advance [label="accept or local revise"];
}
```

## Subagent Delegation

| Role | Prompt file | Writes? |
|------|-------------|---------|
| producer | `subagent-prompts/producer.md` | No — orchestrator persists |
| angle-critic | `subagent-prompts/angle-critic.md` | No — read-only reviewer |
| contribution-auditor | `subagent-prompts/contribution-auditor.md` | No — read-only reviewer |

## Pipeline Position

- **Predecessors:** `agentsociety-paper-adapter` (must produce `research_pack.json`)
- **Successors:** `agentsociety-paper-architecture` (Phase 3 short path) or `agentsociety-paper-evidence-expansion` (Phase 4 full path)

## Common Mistakes

1. **Running framing without research_pack** — the producer needs hypotheses, analysis summaries, and literature. Run `build-pack` first.
2. **Skipping angle-critic** — the producer's own angle always looks reasonable to itself. Always run the critic.
3. **Accepting a diffuse question** — "how does X affect Y" is not a question. It must be specific enough to kill.
4. **Allowing multiple contribution types** — one dominant type. Others are supporting.
5. **Empty kill_criteria** — if you cannot state what would falsify the angle, the angle is not sharp enough.
