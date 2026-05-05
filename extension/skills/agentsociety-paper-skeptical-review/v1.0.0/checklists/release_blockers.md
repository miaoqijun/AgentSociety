# Release Blockers Checklist

This checklist is applied after a review round closes with `accept`
verdict. All items must pass before the manuscript can advance to
release-gate.

## Checklist

### 1. Claim-Evidence Integrity

- [ ] No claim in `claim_ledger.json` has both `evidence_support == []`
      AND `unsupported_gaps != []`
- [ ] Every central claim has `evidence_strength` in {strong, moderate}
- [ ] No claim uses mechanism wording when evidence only shows pattern

### 2. Figure-Argument Completeness

- [ ] Every figure in `figure_argument_map.json` has at least one
      `claim_supported` entry
- [ ] Every figure has a clear argumentative role from the taxonomy
- [ ] No decorative figures (figures without argumentative purpose)

### 3. Structure Compliance

- [ ] Abstract follows the pressure curve (why → gap → what → find →
      follows)
- [ ] Introduction builds pressure and narrows to one gap
- [ ] Results sections are ordered by argumentative strength, not
      chronology
- [ ] Discussion states what was learned before enlarging meaning

### 4. Significance Calibration

- [ ] No inflation words (transformative, novel, powerful, reveals)
      without specific justification
- [ ] Implication is proportional to finding
- [ ] Discussion is ambitious in implication but conservative in
      inference

### 5. Citation and Figure Sentinels

- [ ] All citation sentinels use `[CITE:key]` format (no `\cite{}`)
- [ ] All figure references use `[FIG:id]` format
- [ ] All referenced cite keys exist in the bibliography
- [ ] All referenced figure IDs exist in figure_argument_map

## Resolution

- If any blocker fails: route to revision-router with the failed
  blocker as the issue.
- If all blockers pass: advance to release-gate.
