# Severity Rubric

This reference defines the severity levels used across all reviewer
profiles and the escalation rules.

## Severity Levels

### minor

Local problems that do not affect the paper's argumentative structure.

**Examples:**
- Word-level inflation in a non-central paragraph
- Decorative transition between two well-argued sections
- Missing comma or minor grammatical issue
- Slightly awkward paragraph that is still logically sound

**Action:** Log in the review round. No blocking. May be addressed in a
future `revise_local` pass.

---

### major

Problems that weaken interpretation, structure, or evidentiary support,
but do not invalidate the paper's core argument.

**Examples:**
- Central claim uses strong verbs on moderate evidence
- Qualification missing where it materially affects interpretation
- Paragraph with multiple competing argumentative functions
- Hidden logical leap from result to implication
- Figure without a clear argumentative role
- Section ordered by workflow chronology instead of persuasive logic

**Action:** Must be addressed before the round can close with `accept`.
Routed via revision-router to the appropriate layer.

---

### fatal

Problems that invalidate the paper's core argument, break the paper
angle, or require re-running a major phase.

**Examples:**
- Mechanism claim with only correlational evidence
- Central claim has no evidence support
- Paper angle is contradicted by the data
- Significance inflation that misrepresents the contribution type
- Fatal flaw in experimental design that undermines all results

**Action:** Blocks the round immediately. Routed via revision-router to
`framing`, `evidence`, or `human_gate`. The round cannot close until
all fatal issues are resolved.

## Escalation Rules

1. **Same issue across 2 rounds:** escalate severity by one level
   (minor → major, major → fatal).
2. **Same issue across 3 rounds:** open `human_gate` regardless of
   severity.
3. **3 consecutive non-accept rounds:** open `human_gate` for human
   decision on whether to continue.

## Reroute Targets

| Target layer | When to use |
|-------------|-------------|
| `wording` | Word-level precision issues |
| `paragraph` | Paragraph logic, function, congestion |
| `section` | Section-level structure, order, scope |
| `figure-plan` | Figure role, placement, argumentative weight |
| `evidence` | Claim-evidence alignment, missing qualifications |
| `framing` | Paper angle, contribution type, question sharpness |

**Lowest-layer principle:** When an issue spans multiple layers, route
to the lowest layer sufficient to resolve it. A wording fix that
requires a new claim is a `section` issue, not a `wording` issue.
